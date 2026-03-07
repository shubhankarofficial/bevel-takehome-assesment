"""
Ingest use-case: run the ingestion pipeline (schema, CSV load, index to ES).
"""

from typing import Optional

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine

from ..ingest.pipeline import IngestPipeline


class IngestService:
    """
    Entrypoint for the ingest use case.

    API or CLI calls this; it runs the ingest pipeline (repositories, ES index).
    """

    def __init__(self, pool: asyncpg.Pool, engine: AsyncEngine) -> None:
        self._pool = pool
        self._engine = engine
        self._pipeline: Optional[IngestPipeline] = None

    def _get_pipeline(self) -> IngestPipeline:
        if self._pipeline is None:
            self._pipeline = IngestPipeline(self._pool, self._engine)
        return self._pipeline

    async def run(self) -> None:
        """Run the full ingest: schema (if any), load CSVs into DB, index to ES."""
        pipeline = self._get_pipeline()
        await pipeline.run()
