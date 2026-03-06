"""
Clear Postgres ingest tables and the Elasticsearch food index so you can rerun ingest from scratch.

Usage (from app-py directory):
  python -m src.run_reset

Then run the full ingest:
  python -m src.run_ingest

You do not need to rerun migrations separately — run_ingest runs migrations first (idempotent),
then CSV load, then ES index.
"""

import asyncio
import logging
import sys

from .db import close_pool, get_pool
from .elastic_search import FoodSearchIndex
from .es_client import close_es_client, es_client
from .config import FOOD_INDEX_NAME


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

        logger.info("Reset complete. Run: python -m src.run_ingest")
    except Exception as e:
        logger.exception("Reset failed: %s", e)
        sys.exit(1)
    finally:
        await close_pool()
        await close_es_client()


if __name__ == "__main__":
    asyncio.run(main())
