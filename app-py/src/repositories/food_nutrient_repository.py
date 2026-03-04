from typing import Dict

import asyncpg


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
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT nutrient_id, amount
                FROM food_nutrients
                WHERE fdc_id = $1
                """,
                fdc_id,
            )
        return {int(row["nutrient_id"]): float(row["amount"]) for row in rows}

