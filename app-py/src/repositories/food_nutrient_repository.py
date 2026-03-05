import logging
from typing import Any, Dict, List, Tuple

import asyncpg

logger = logging.getLogger(__name__)


class FoodNutrientRepository:
    """
    Repository for accessing nutrient amounts per food from Postgres.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_usda_nutrient_amounts_for_food(self, fdc_id: int) -> Dict[int, float]:
        """
        Return a mapping of USDA nutrient_id -> amount for the given food.
        """
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT nutrient_id, amount
                    FROM food_nutrients
                    WHERE fdc_id = $1
                    """,
                    fdc_id,
                )
            result = {int(row["nutrient_id"]): float(row["amount"]) for row in rows}
            logger.debug(
                "FoodNutrientRepository.get_usda_nutrient_amounts_for_food: fdc_id=%s, nutrients=%s",
                fdc_id,
                len(result),
            )
            return result
        except Exception as e:
            logger.exception(
                "FoodNutrientRepository.get_usda_nutrient_amounts_for_food failed: fdc_id=%s, error=%s",
                fdc_id,
                e,
            )
            raise

    async def get_usda_nutrient_amounts_for_foods(
        self, fdc_ids: List[int]
    ) -> Dict[int, Dict[int, float]]:
        """
        Return a mapping of fdc_id -> {USDA nutrient_id -> amount} for all given foods.

        Used by indexing to fetch nutrient amounts for a batch of foods in a single query.
        """
        if not fdc_ids:
            return {}
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT fdc_id, nutrient_id, amount
                    FROM food_nutrients
                    WHERE fdc_id = ANY($1::bigint[])
                    """,
                    fdc_ids,
                )
            by_food: Dict[int, Dict[int, float]] = {}
            for row in rows:
                food_id = int(row["fdc_id"])
                nutrient_id = int(row["nutrient_id"])
                amount = float(row["amount"])
                if food_id not in by_food:
                    by_food[food_id] = {}
                by_food[food_id][nutrient_id] = amount
            logger.debug(
                "FoodNutrientRepository.get_usda_nutrient_amounts_for_foods: foods=%s, with_nutrients=%s",
                len(fdc_ids),
                len(by_food),
            )
            return by_food
        except Exception as e:
            logger.exception(
                "FoodNutrientRepository.get_usda_nutrient_amounts_for_foods failed: foods=%s, error=%s",
                len(fdc_ids),
                e,
            )
            raise

    async def bulk_insert(
        self,
        rows: List[Tuple[int, int, int, Any]],
    ) -> int:
        """
        Insert many rows into food_nutrients. Each row is (id, fdc_id, nutrient_id, amount).
        Returns the number of rows inserted.
        """
        if not rows:
            return 0
        try:
            async with self._pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO food_nutrients (id, fdc_id, nutrient_id, amount)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (id) DO UPDATE SET
                        fdc_id = EXCLUDED.fdc_id,
                        nutrient_id = EXCLUDED.nutrient_id,
                        amount = EXCLUDED.amount
                    """,
                    rows,
                )
            return len(rows)
        except Exception as e:
            logger.exception(
                "FoodNutrientRepository.bulk_insert failed: %s rows, error=%s",
                len(rows),
                e,
            )
            raise

    async def count_for_food(self, fdc_id: int) -> int:
        """Return number of nutrient rows for a food (for logging/observability)."""
        try:
            async with self._pool.acquire() as conn:
                n = await conn.fetchval(
                    "SELECT COUNT(*) FROM food_nutrients WHERE fdc_id = $1",
                    fdc_id,
                )
            count = int(n)
            logger.debug(
                "FoodNutrientRepository.count_for_food: fdc_id=%s, count=%s",
                fdc_id,
                count,
            )
            return count
        except Exception as e:
            logger.exception(
                "FoodNutrientRepository.count_for_food failed: fdc_id=%s, error=%s",
                fdc_id,
                e,
            )
            raise

