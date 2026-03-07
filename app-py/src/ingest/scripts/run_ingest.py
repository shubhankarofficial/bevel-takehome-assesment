"""
Run the full ingest pipeline (migrations, CSV load, ES index) only.

Use this when you want to (re)load data without starting the API or the NOTIFY listener.
The FastAPI app on startup runs the same pipeline and then starts the listener.

  cd app-py && python -m src.ingest.scripts.run_ingest
"""

import asyncio
import logging
import sys

from ...db import close_engine, close_pool, get_engine, get_pool
from ...es_client import close_es_client
from ..runner import run_ingest_once


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)
    try:
        pool = await get_pool()
        engine = get_engine()
        await run_ingest_once(pool, engine)
        logger.info("Ingest completed.")
    except Exception as e:
        logger.exception("Ingest failed: %s", e)
        sys.exit(1)
    finally:
        await close_pool()
        await close_engine()
        await close_es_client()


if __name__ == "__main__":
    asyncio.run(main())
