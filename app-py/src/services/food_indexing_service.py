"""
Service that reads foods from Postgres and indexes them into Elasticsearch.

Uses repositories, NutrientMappingService, and FoodSearchIndex to build one
document per food so that foods can be searched by name.
"""

import logging
from typing import Any, Dict, List

from ..config import INDEX_BULK_BATCH_SIZE
from ..elastic_search import FoodSearchIndex
from ..repositories.food_nutrient_repository import FoodNutrientRepository
from ..repositories.food_repository import FoodRepository
from .nutrient_mapping_service import NutrientMappingService

logger = logging.getLogger(__name__)


class FoodIndexingService:
    """
    Index foods from Postgres into Elasticsearch.

    Intended to be called by the ingest pipeline after CSV load has populated
    the database tables.
    """

    def __init__(
        self,
        food_repo: FoodRepository,
        food_nutrient_repo: FoodNutrientRepository,
        search_index: FoodSearchIndex,
        batch_size: int = INDEX_BULK_BATCH_SIZE,
    ) -> None:
        self._food_repo = food_repo
        self._food_nutrient_repo = food_nutrient_repo
        self._search_index = search_index
        self._batch_size = batch_size
        self._nutrient_mapping = NutrientMappingService()

    async def reindex_all(self) -> None:
        """
        Rebuild the Elasticsearch index from the current database contents.

        Reads foundation_food rows from Postgres in batches, fetches their
        nutrient amounts in a single query per batch, maps them to the
        domain NutrientAmount list, and bulk indexes documents into ES.
        """
        logger.info("FoodIndexingService: starting full reindex")
        await self._search_index.ensure_index()

        offset = 0
        total_indexed = 0

        while True:
            foods = await self._food_repo.list_foundation_foods_batch(
                offset=offset, limit=self._batch_size
            )
            if not foods:
                break

            fdc_ids: List[int] = []
            docs: List[Dict[str, Any]] = []

            for row in foods:
                try:
                    fdc_id = int(row["fdc_id"])
                except (KeyError, TypeError, ValueError):
                    logger.warning("FoodIndexingService: skipping row with invalid fdc_id: %r", row)
                    continue
                fdc_ids.append(fdc_id)

            nutrient_amounts_by_food = await self._food_nutrient_repo.get_usda_nutrient_amounts_for_foods(
                fdc_ids
            )

            for row in foods:
                try:
                    fdc_id = int(row["fdc_id"])
                except (KeyError, TypeError, ValueError):
                    # Already logged above; skip
                    continue

                name = (row.get("description") or "").strip()
                usda_amounts = nutrient_amounts_by_food.get(fdc_id, {})
                nutrient_amounts = self._nutrient_mapping.map_usda_to_food_nutrients(usda_amounts)
                nutrients_payload = [
                    {"type": na.type.value, "amount": float(na.amount)} for na in nutrient_amounts
                ]

                doc: Dict[str, Any] = {
                    "fdc_id": fdc_id,
                    "name": name,
                    "nutrients": nutrients_payload,
                }
                docs.append(doc)

            if docs:
                await self._search_index.bulk_index_foods(docs)
                total_indexed += len(docs)
                logger.info(
                    "FoodIndexingService: indexed %s foods in this batch (offset=%s)",
                    len(docs),
                    offset,
                )

            offset += self._batch_size

        logger.info("FoodIndexingService: full reindex complete, total_indexed=%s", total_indexed)

    async def upsert_food_by_fdc_id(self, fdc_id: int) -> None:
        """
        Load one foundation_food by fdc_id and upsert its document into the search index.
        If the food does not exist or is not foundation_food, remove it from the index if present.
        Used by the NOTIFY listener for dynamic index updates (Phase 2).
        Used to delete stale data from the index.
        """
        await self._search_index.ensure_index()

        row = await self._food_repo.get_food_by_fdc_id(fdc_id)
        if row is None or (row.get("data_type") or "").strip() != "foundation_food":
            await self._search_index.delete_food(fdc_id)
            logger.debug(
                "FoodIndexingService.upsert_food_by_fdc_id: fdc_id=%s not foundation_food or missing, removed from index",
                fdc_id,
            )
            return

        name = (row.get("description") or "").strip()
        usda_amounts = await self._food_nutrient_repo.get_usda_nutrient_amounts_for_food(fdc_id)
        nutrient_amounts = self._nutrient_mapping.map_usda_to_food_nutrients(usda_amounts)
        nutrients_payload = [
            {"type": na.type.value, "amount": float(na.amount)} for na in nutrient_amounts
        ]

        # If the food is in our foods DB, include it in ES (with whatever nutrients it has, possibly empty).
        doc: Dict[str, Any] = {
            "fdc_id": fdc_id,
            "name": name,
            "nutrients": nutrients_payload,
        }
        await self._search_index.index_food(fdc_id, doc)
        logger.debug("FoodIndexingService.upsert_food_by_fdc_id: indexed fdc_id=%s", fdc_id)

    async def delete_food_from_index(self, fdc_id: int) -> None:
        """
        Remove the food document for fdc_id from the search index (idempotent).
        Used by the NOTIFY listener when a foundation_food row is deleted.
        """
        await self._search_index.delete_food(fdc_id)
        logger.debug("FoodIndexingService.delete_food_from_index: removed fdc_id=%s", fdc_id)

