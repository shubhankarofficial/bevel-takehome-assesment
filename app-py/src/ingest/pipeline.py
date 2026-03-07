"""
Ingestion pipeline: CSV load into DB, then index foods into Elasticsearch.

Orchestrates CsvLoadService (parse CSVs → repositories) and FoodIndexingService
(read from Postgres → build ES documents). Schema is applied separately via
MigrationService.
"""

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine

from ..elastic_search import FoodSearchIndex
from ..es_client import es_client
from ..repositories.food_nutrient_repository import FoodNutrientRepository
from ..repositories.food_repository import FoodRepository
from ..repositories.nutrient_repository import NutrientRepository
from ..services.csv_load_service import CsvLoadService
from ..services.food_indexing_service import FoodIndexingService
from ..services.migration_service import MigrationService


class IngestPipeline:
    """
    High-level orchestrator for data ingestion:
    - Load CSVs into Postgres via CsvLoadService.
    - Index foods into Elasticsearch via FoodIndexingService.
    """

    def __init__(self, pool: asyncpg.Pool, engine: AsyncEngine) -> None:
        self._pool = pool
        self._engine = engine
        self._migrations = MigrationService(pool)
        self._nutrient_repo = NutrientRepository(engine)
        self._food_repo = FoodRepository(engine)
        self._food_nutrient_repo = FoodNutrientRepository(engine)
        self._csv_load = CsvLoadService(
            self._nutrient_repo,
            self._food_repo,
            self._food_nutrient_repo,
        )
        self._search_index = FoodSearchIndex(es_client)
        self._food_indexing = FoodIndexingService(
            food_repo=self._food_repo,
            food_nutrient_repo=self._food_nutrient_repo,
            search_index=self._search_index,
        )

    async def run(self) -> None:
        """
        Run the full ingest:
        - run database migrations (idempotent; safe to re-run)
        - load CSVs into Postgres (nutrients → foods → food_nutrients)
        - index foods into Elasticsearch for search by name.
        """
        await self._migrations.run()
        await self._csv_load.load_all()
        await self._food_indexing.reindex_all()

