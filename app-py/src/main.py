import logging
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from pydantic import BaseModel

from .db import get_pool, close_pool
from .es_client import es_client, close_es_client
from .repositories.food_nutrient_repository import FoodNutrientRepository
from .repositories.food_repository import FoodRepository
from .responses import ErrorResponse, FoodSearchResponse
from .search.phrase_prefix_fuzzy_search_strategy import PhrasePrefixFuzzySearchStrategy
from .services import (
    FoodNutrientService,
    FoodSearchResponseService,
    FoodService,
    SearchService,
)

load_dotenv()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    print(f"Server starting on port {os.getenv('PORT', 3000)}")
    strategy = PhrasePrefixFuzzySearchStrategy(es_client)
    app.state.search_service = SearchService(strategy)
    app.state.food_search_response_service = FoodSearchResponseService()
    pool = await get_pool()
    app.state.food_repo = FoodRepository(pool)
    app.state.food_nutrient_repo = FoodNutrientRepository(pool)
    app.state.food_service = FoodService(app.state.food_repo)
    app.state.food_nutrient_service = FoodNutrientService(
        app.state.food_nutrient_repo, app.state.food_repo
    )
    yield
    await close_pool()
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
        # Check database connection
        pool = await get_pool()
        async with pool.acquire() as connection:
            db_time = await connection.fetchval("SELECT NOW()")

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


class AddFoodBody(BaseModel):
    fdc_id: int
    data_type: str = "foundation_food"
    description: Optional[str] = None
    publication_date: Optional[str] = None


class UpdateFoodBody(BaseModel):
    data_type: Optional[str] = None
    description: Optional[str] = None
    publication_date: Optional[str] = None


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


class AddFoodNutrientBody(BaseModel):
    fdc_id: int
    nutrient_id: int
    amount: float


class UpdateFoodNutrientBody(BaseModel):
    fdc_id: Optional[int] = None
    nutrient_id: Optional[int] = None
    amount: Optional[float] = None


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