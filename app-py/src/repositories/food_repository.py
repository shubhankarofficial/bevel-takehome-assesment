from typing import Any, Dict, List, Optional

import asyncpg


class FoodRepository:
    """
    Repository responsible for accessing food data in Postgres.

    This class hides SQL details from the rest of the application.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_food_by_fdc_id(self, fdc_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a single food row by its USDA fdc_id.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM foods
                WHERE fdc_id = $1
                """,
                fdc_id,
            )
        return dict(row) if row is not None else None

    async def list_foundation_foods_batch(
        self, offset: int, limit: int
    ) -> List[Dict[str, Any]]:
        """
        Return a batch of foundation foods for bulk processing (e.g. indexing).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM foods
                WHERE data_type = 'foundation_food'
                ORDER BY fdc_id
                OFFSET $1
                LIMIT $2
                """,
                offset,
                limit,
            )
        return [dict(r) for r in rows]

