"""
Shared ingest and listener startup for use by both the CLI script and the FastAPI app.

- run_ingest_once(pool, engine): run migrations, CSV load, ES reindex (single entrypoint).
- start_listener_background(engine): create NOTIFY listener and start it as a task; return
  (listener, listen_conn, task) so the caller can stop and clean up.
"""

import asyncio
import logging
from typing import Tuple

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine

from ..config import (
    FOOD_INDEX_NAME,
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)
from ..elastic_search import FoodSearchIndex
from ..es_client import es_client
from ..listener import FoodIndexNotifyListener
from ..repositories.food_nutrient_repository import FoodNutrientRepository
from ..repositories.food_repository import FoodRepository
from ..services import FoodIndexingService, IngestService

logger = logging.getLogger(__name__)


def _pg_config() -> dict:
    return {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "database": POSTGRES_DB,
    }


async def run_ingest_once(pool: asyncpg.Pool, engine: AsyncEngine) -> None:
    """
    Run the full ingest pipeline once: migrations, CSV load, ES reindex.
    Used by both the ingest script and the FastAPI app on startup.
    """
    ingest = IngestService(pool, engine)
    await ingest.run()


async def start_listener_background(
    engine: AsyncEngine,
) -> Tuple[FoodIndexNotifyListener, asyncpg.Connection, asyncio.Task]:
    """
    Create the food index NOTIFY listener and start it as a background task.
    Returns (listener, listen_conn, task). Caller must call listener.stop() on shutdown,
    then await the task, then await listen_conn.close().
    """
    listen_conn = await asyncpg.connect(**_pg_config())
    search_index = FoodSearchIndex(es_client, index_name=FOOD_INDEX_NAME)
    food_repo = FoodRepository(engine)
    food_nutrient_repo = FoodNutrientRepository(engine)
    indexing_service = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    listener = FoodIndexNotifyListener(indexing_service, listen_conn)
    task = asyncio.create_task(listener.run())
    return (listener, listen_conn, task)
