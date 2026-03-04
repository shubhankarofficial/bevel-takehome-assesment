"""
Ingestion pipeline skeleton.

This module will orchestrate:
- Parsing USDA CSV files.
- Inserting data into Postgres via repositories.
- Triggering Elasticsearch indexing via the FoodSearchIndex facade.
"""

from typing import Any

import asyncpg

from ..config import (
    FOOD_CSV_PATH,
    FOOD_NUTRIENT_CSV_PATH,
    NUTRIENT_CSV_PATH,
    INGEST_DB_BATCH_SIZE,
)
from ..es_client import es_client
from ..repositories.food_repository import FoodRepository
from ..repositories.food_nutrient_repository import FoodNutrientRepository
from ..search.food_search_index import FoodSearchIndex


class IngestPipeline:
    """
    High-level orchestrator for one-time or repeated data ingestion.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._food_repo = FoodRepository(pool)
        self._food_nutrient_repo = FoodNutrientRepository(pool)
        self._search_index = FoodSearchIndex(es_client)

    async def run(self) -> None:
        """
        Entry point for the ingestion pipeline.

        Implementation details (schema creation, CSV parsing, DB writes, indexing)
        will be filled in in subsequent steps.
        """
        # Placeholder to establish structure. Logic will follow.
        pass

