"""
Run the full ingest pipeline (migrations, CSV load, ES index).

Usage from repo root:
  cd app-py && python -m src.run_ingest

Or with env loaded:
  cd app-py && python -m src.run_ingest
"""

import asyncio
import logging
import sys

from .db import close_pool, get_pool
from .es_client import close_es_client
from .services import IngestService


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)
    try:
        pool = await get_pool()
        ingest = IngestService(pool)
        await ingest.run()
        logger.info("Ingest completed successfully.")
    except Exception as e:
        logger.exception("Ingest failed: %s", e)
        sys.exit(1)
    finally:
        await close_pool()
        await close_es_client()


if __name__ == "__main__":
    asyncio.run(main())
