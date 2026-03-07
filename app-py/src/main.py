import asyncio
import logging
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from .db import close_engine, close_pool, get_engine, get_pool
from .es_client import es_client, close_es_client
from .ingest.runner import run_ingest_once, start_listener_background
from .repositories.food_nutrient_repository import FoodNutrientRepository
from .repositories.food_repository import FoodRepository
from .responses import ErrorResponse, FoodSearchResponse
from .schemas import (
    AddFoodBody,
    AddFoodNutrientBody,
    UpdateFoodBody,
    UpdateFoodNutrientBody,
)
from .search.concrete_search_strategies.phrase_prefix_fuzzy_search_strategy import PhrasePrefixFuzzySearchStrategy
from .services import (
    FoodNutrientService,
    FoodSearchResponseService,
    FoodService,
    SearchService,
)

load_dotenv()
logger = logging.getLogger(__name__)

# So ingest and listener logs show when running via uvicorn
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run ingest once on startup, start NOTIFY listener in background, then serve API."""
    print(f"Server starting on port {os.getenv('PORT', 3000)}")

    pool = await get_pool()
    engine = get_engine()

    logger.info("Running ingest pipeline...")
    await run_ingest_once(pool, engine)
    logger.info("Ingest completed. Starting NOTIFY listener...")

    listener, listen_conn, listener_task = await start_listener_background(engine)
    app.state._listener = listener
    app.state._listen_conn = listen_conn
    app.state._listener_task = listener_task

    # API state
    strategy = PhrasePrefixFuzzySearchStrategy(es_client)
    app.state.search_service = SearchService(strategy)
    app.state.food_search_response_service = FoodSearchResponseService()
    app.state.food_repo = FoodRepository(engine)
    app.state.food_nutrient_repo = FoodNutrientRepository(engine)
    app.state.food_service = FoodService(app.state.food_repo)
    app.state.food_nutrient_service = FoodNutrientService(
        app.state.food_nutrient_repo, app.state.food_repo
    )

    yield

    logger.info("Shutting down listener...")
    app.state._listener.stop()
    try:
        await asyncio.wait_for(app.state._listener_task, timeout=5.0)
    except asyncio.TimeoutError:
        app.state._listener_task.cancel()
        try:
            await app.state._listener_task
        except asyncio.CancelledError:
            pass
    await app.state._listen_conn.close()
    await close_pool()
    await close_engine()
    await close_es_client()


# Create FastAPI application
app = FastAPI(
    title="Python Backend Boilerplate",
    description="Python/FastAPI boilerplate for backend take-home assessment",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """
    Health check endpoint that verifies database and Elasticsearch connections.
    """
    try:
        from sqlalchemy import text

        # Check database connection
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT NOW()"))
            db_time = result.scalar_one()

        # Check Elasticsearch connection
        es_info = await es_client.info()

        return {
            "status": "ok",
            "dbTime": str(db_time),
            "esVersion": es_info["version"]
        }
    except Exception as e:
        print(f"Error in /health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search", response_model=FoodSearchResponse)
async def search(
    query: Optional[str] = Query(default=None, description="Search query (required)"),
    size: int = Query(default=20, description="Max number of results (1-100)"),
):
    """
    Search foods by name. Returns matching foods with their nutrients.
    """
    if query is None or (isinstance(query, str) and not query.strip()):
        return JSONResponse(
            status_code=400,
            content=ErrorResponse.query_required().model_dump(),
        )
    if size < 1 or size > 100:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse.invalid_size().model_dump(),
        )
    try:
        foods = await app.state.search_service.search_foods(query=query.strip(), size=size)
        response = app.state.food_search_response_service.from_domain_foods(foods)
        return response
    except Exception as e:
        if _is_search_failure(e):
            logger.exception("Search failed: %s", e)
            return JSONResponse(
                status_code=503,
                content=ErrorResponse.search_unavailable().model_dump(),
            )
        logger.exception("Unexpected error in /search: %s", e)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse.internal_error().model_dump(),
        )


def _is_search_failure(e: Exception) -> bool:
    """True if the exception is due to search/ES (e.g. connection, timeout)."""
    return "elasticsearch" in type(e).__module__.lower() or "connection" in str(e).lower()


# --- Demo endpoints: add/update/delete foods and food_nutrients (different DBs → different services) ---


@app.post("/demo/foods")
async def demo_add_food(body: AddFoodBody):
    """Add a food row (foods table). Trigger will NOTIFY; listener will sync index if running."""
    try:
        await app.state.food_service.add_food(
            fdc_id=body.fdc_id,
            data_type=body.data_type,
            description=body.description,
            publication_date=body.publication_date,
        )
        return {"ok": True, "fdc_id": body.fdc_id}
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Food fdc_id={body.fdc_id} already exists")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/demo/foods/{fdc_id}")
async def demo_update_food(
    fdc_id: int = Path(..., description="Food fdc_id"),
    body: UpdateFoodBody = ...,
):
    """Update a food row (foods table). Trigger will NOTIFY; listener will sync index if running."""
    updated = await app.state.food_service.update_food(
        fdc_id,
        data_type=body.data_type,
        description=body.description,
        publication_date=body.publication_date,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"No food found for fdc_id={fdc_id}")
    return {"ok": True, "fdc_id": fdc_id}


@app.delete("/demo/foods/{fdc_id}")
async def demo_delete_food(fdc_id: int = Path(..., description="Food fdc_id")):
    """Delete a food row (foods table). Trigger will NOTIFY; listener will remove from index if running."""
    deleted = await app.state.food_service.delete_food(fdc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No food found for fdc_id={fdc_id}")
    return {"ok": True, "fdc_id": fdc_id}


@app.post("/demo/food-nutrients")
async def demo_add_food_nutrient(body: AddFoodNutrientBody):
    """Add a food_nutrient row (food_nutrients table). Trigger will NOTIFY; listener will sync index if running."""
    try:
        id = await app.state.food_nutrient_service.add_food_nutrient(
            fdc_id=body.fdc_id,
            nutrient_id=body.nutrient_id,
            amount=body.amount,
        )
        return {"ok": True, "id": id, "fdc_id": body.fdc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/demo/food-nutrients/{id}")
async def demo_update_food_nutrient(
    id: int = Path(..., description="Food nutrient row id"),
    body: UpdateFoodNutrientBody = ...,
):
    """Update a food_nutrient row (food_nutrients table). Trigger will NOTIFY; listener will sync index if running."""
    updated = await app.state.food_nutrient_service.update_food_nutrient(
        id,
        fdc_id=body.fdc_id,
        nutrient_id=body.nutrient_id,
        amount=body.amount,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"No food_nutrient found for id={id}")
    return {"ok": True, "id": id}


@app.delete("/demo/food-nutrients/{id}")
async def demo_delete_food_nutrient(id: int = Path(..., description="Food nutrient row id")):
    """Delete a food_nutrient row (food_nutrients table). Trigger will NOTIFY; listener will sync index if running."""
    deleted = await app.state.food_nutrient_service.delete_food_nutrient(id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No food_nutrient found for id={id}")
    return {"ok": True, "id": id}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 3000))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)