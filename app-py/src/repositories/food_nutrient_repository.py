import logging
from typing import Any, Dict, List, Optional, Tuple

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

    async def insert_food_nutrient(
        self,
        fdc_id: int,
        nutrient_id: int,
        amount: float,
        *,
        id: Optional[int] = None,
    ) -> int:
        """
        Insert a single food_nutrient row. If id is not provided, uses COALESCE(MAX(id),0)+1.
        Returns the id of the inserted row.
        """
        try:
            async with self._pool.acquire() as conn:
                if id is not None:
                    await conn.execute(
                        """
                        INSERT INTO food_nutrients (id, fdc_id, nutrient_id, amount)
                        VALUES ($1, $2, $3, $4)
                        """,
                        id,
                        fdc_id,
                        nutrient_id,
                        amount,
                    )
                    return id
                row = await conn.fetchrow(
                    """
                    INSERT INTO food_nutrients (id, fdc_id, nutrient_id, amount)
                    SELECT COALESCE(MAX(fn.id), 0) + 1, $1, $2, $3
                    FROM food_nutrients fn
                    RETURNING id
                    """,
                    fdc_id,
                    nutrient_id,
                    amount,
                )
            inserted_id = int(row["id"])
            logger.info(
                "FoodNutrientRepository.insert_food_nutrient: id=%s, fdc_id=%s",
                inserted_id,
                fdc_id,
            )
            return inserted_id
        except Exception as e:
            logger.exception(
                "FoodNutrientRepository.insert_food_nutrient failed: fdc_id=%s, error=%s",
                fdc_id,
                e,
            )
            raise

    async def update_food_nutrient(
        self,
        id: int,
        *,
        fdc_id: Optional[int] = None,
        nutrient_id: Optional[int] = None,
        amount: Optional[float] = None,
    ) -> bool:
        """Update a food_nutrient row by id. Only non-None fields are updated. Returns True if a row was updated."""
        try:
            async with self._pool.acquire() as conn:
                updates: List[str] = []
                values: List[Any] = []
                i = 1
                if fdc_id is not None:
                    updates.append(f"fdc_id = ${i}")
                    values.append(fdc_id)
                    i += 1
                if nutrient_id is not None:
                    updates.append(f"nutrient_id = ${i}")
                    values.append(nutrient_id)
                    i += 1
                if amount is not None:
                    updates.append(f"amount = ${i}")
                    values.append(amount)
                    i += 1
                if not updates:
                    return False
                values.append(id)
                result = await conn.execute(
                    f"UPDATE food_nutrients SET {', '.join(updates)} WHERE id = ${i}",
                    *values,
                )
            updated = result.strip() == "UPDATE 1"
            if updated:
                logger.info("FoodNutrientRepository.update_food_nutrient: id=%s", id)
            return updated
        except Exception as e:
            logger.exception(
                "FoodNutrientRepository.update_food_nutrient failed: id=%s, error=%s",
                id,
                e,
            )
            raise

    async def delete_food_nutrient(self, id: int) -> tuple[bool, Optional[int]]:
        """
        Delete a food_nutrient row by id.
        Returns (deleted, fdc_id): True and the food's fdc_id if a row was deleted, else (False, None).
        Caller can use fdc_id to check if the food has no nutrients left and delete the food if needed.
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT fdc_id FROM food_nutrients WHERE id = $1",
                    id,
                )
                if row is None:
                    return (False, None)
                fdc_id = int(row["fdc_id"])
                result = await conn.execute(
                    "DELETE FROM food_nutrients WHERE id = $1",
                    id,
                )
            deleted = result.strip() == "DELETE 1"
            if deleted:
                logger.info("FoodNutrientRepository.delete_food_nutrient: id=%s, fdc_id=%s", id, fdc_id)
            return (deleted, fdc_id if deleted else None)
        except Exception as e:
            logger.exception(
                "FoodNutrientRepository.delete_food_nutrient failed: id=%s, error=%s",
                id,
                e,
            )
            raise

