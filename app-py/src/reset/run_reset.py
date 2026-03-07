"""
Reset Postgres ingest tables and the Elasticsearch food index, then run the full ingest pipeline.

Usage (from app-py directory):
  python -m src.reset.run_reset

This truncates Postgres tables, deletes the ES index, then runs migrations, CSV load, and ES reindex.
The NOTIFY listener is not started — start the FastAPI app to have ingest + listener.
"""

import asyncio
import logging
import sys

from ..config import FOOD_INDEX_NAME
from ..db import close_engine, close_pool, get_engine, get_pool
from ..elastic_search import FoodSearchIndex
from ..es_client import close_es_client, es_client
from ..ingest.runner import run_ingest_once


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)
    try:
        # 1. Truncate Postgres tables (child table first due to FK)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("TRUNCATE TABLE food_nutrients, foods, nutrients RESTART IDENTITY CASCADE")
        logger.info("Postgres: truncated food_nutrients, foods, nutrients")

        # 2. Delete ES index so reindex starts fresh
        index = FoodSearchIndex(es_client, index_name=FOOD_INDEX_NAME)
        await index.delete_index()
        logger.info("Elasticsearch: deleted food index")

        # 3. Run full ingest (migrations, CSV load, ES reindex)
        engine = get_engine()
        await run_ingest_once(pool, engine)
        logger.info("Reset and ingest complete.")
    except Exception as e:
        logger.exception("Reset or ingest failed: %s", e)
        sys.exit(1)
    finally:
        await close_pool()
        await close_engine()
        await close_es_client()


if __name__ == "__main__":
    asyncio.run(main())
