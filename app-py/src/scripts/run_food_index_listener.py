"""
Phase 3: Run the food index NOTIFY listener as a separate process.

LISTENs on food_index_events, updates Elasticsearch per notification (upsert or delete by fdc_id).
Failures are retried up to 3 times, then logged and dropped.

  From app-py with venv active:
    python -m src.scripts.run_food_index_listener

  Optional env: POSTGRES_*, ELASTICSEARCH_URL, FOOD_INDEX_NAME (see .env.example).
  Stop with Ctrl+C.
"""
import asyncio
import logging
import signal
import sys

from dotenv import load_dotenv

load_dotenv()

import asyncpg
from elasticsearch import AsyncElasticsearch

from ..config import (
    ELASTICSEARCH_URL,
    FOOD_INDEX_NAME,
    NOTIFY_CHANNEL_FOOD_INDEX,
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)
from ..db import close_engine, get_engine
from ..elastic_search import FoodSearchIndex
from ..listener import FoodIndexNotifyListener
from ..repositories.food_nutrient_repository import FoodNutrientRepository
from ..repositories.food_repository import FoodRepository
from ..services.food_indexing_service import FoodIndexingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _pg_config() -> dict:
    return {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "database": POSTGRES_DB,
    }


async def main() -> None:
    engine = get_engine()
    # Dedicated connection for LISTEN (asyncpg: don't use it for other queries)
    listen_conn = await asyncpg.connect(**_pg_config())

    es = AsyncElasticsearch(
        hosts=[ELASTICSEARCH_URL],
        verify_certs=False,
        ssl_show_warn=False,
    )
    search_index = FoodSearchIndex(es, index_name=FOOD_INDEX_NAME)
    food_repo = FoodRepository(engine)
    food_nutrient_repo = FoodNutrientRepository(engine)
    indexing_service = FoodIndexingService(
        food_repo=food_repo,
        food_nutrient_repo=food_nutrient_repo,
        search_index=search_index,
    )
    listener = FoodIndexNotifyListener(indexing_service, listen_conn)

    def do_stop(*args):  # type: ignore
        logger.info("Shutting down listener...")
        listener.stop()

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, do_stop)
            except NotImplementedError:
                pass  # e.g. Windows
    except RuntimeError:
        pass

    try:
        logger.info("Starting food index listener (channel=%s). Ctrl+C to stop.", NOTIFY_CHANNEL_FOOD_INDEX)
        await listener.run()
    finally:
        await listen_conn.close()
        await close_engine()
        await es.close()


if __name__ == "__main__":
    asyncio.run(main())
