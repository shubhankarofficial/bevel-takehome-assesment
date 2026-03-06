import logging
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

logger = logging.getLogger(__name__)


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
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT *
                    FROM foods
                    WHERE fdc_id = $1
                    """,
                    fdc_id,
                )
            if row is not None:
                logger.debug("FoodRepository.get_food_by_fdc_id found: fdc_id=%s", fdc_id)
            return dict(row) if row is not None else None
        except Exception as e:
            logger.exception(
                "FoodRepository.get_food_by_fdc_id failed: fdc_id=%s, error=%s",
                fdc_id,
                e,
            )
            raise

    async def list_foundation_foods_batch(
        self, offset: int, limit: int
    ) -> List[Dict[str, Any]]:
        """
        Return a batch of foundation foods for bulk processing (e.g. indexing).
        """
        try:
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
        except Exception as e:
            logger.exception(
                "FoodRepository.list_foundation_foods_batch failed: offset=%s, limit=%s, error=%s",
                offset,
                limit,
                e,
            )
            raise

    async def bulk_insert(
        self,
        rows: List[Tuple[int, Optional[str], Optional[str], Optional[Any]]],
    ) -> int:
        """
        Insert many rows into foods. Each row is (fdc_id, data_type, description, publication_date).
        Returns the number of rows inserted.
        """
        if not rows:
            return 0
        try:
            async with self._pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO foods (fdc_id, data_type, description, publication_date)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (fdc_id) DO UPDATE SET
                        data_type = EXCLUDED.data_type,
                        description = EXCLUDED.description,
                        publication_date = EXCLUDED.publication_date
                    """,
                    rows,
                )
            logger.info("FoodRepository.bulk_insert completed: inserted %s rows", len(rows))
            return len(rows)
        except Exception as e:
            logger.exception(
                "FoodRepository.bulk_insert failed: %s rows, error=%s",
                len(rows),
                e,
            )
            raise

    async def count_foundation_foods(self) -> int:
        """Return count of foundation_food rows (for logging/observability)."""
        try:
            async with self._pool.acquire() as conn:
                n = await conn.fetchval(
                    "SELECT COUNT(*) FROM foods WHERE data_type = $1",
                    "foundation_food",
                )
            count = int(n)
            logger.debug("FoodRepository.count_foundation_foods: %s", count)
            return count
        except Exception as e:
            logger.exception("FoodRepository.count_foundation_foods failed: error=%s", e)
            raise

    async def insert_food(
        self,
        fdc_id: int,
        data_type: str,
        description: Optional[str] = None,
        publication_date: Optional[Any] = None,
    ) -> None:
        """Insert a single food row. Raises if fdc_id already exists (use update for that)."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO foods (fdc_id, data_type, description, publication_date)
                    VALUES ($1, $2, $3, $4)
                    """,
                    fdc_id,
                    data_type,
                    description,
                    publication_date,
                )
            logger.info("FoodRepository.insert_food: fdc_id=%s", fdc_id)
        except Exception as e:
            logger.exception("FoodRepository.insert_food failed: fdc_id=%s, error=%s", fdc_id, e)
            raise

    async def update_food(
        self,
        fdc_id: int,
        *,
        data_type: Optional[str] = None,
        description: Optional[str] = None,
        publication_date: Optional[Any] = None,
    ) -> bool:
        """Update a food row by fdc_id. Only non-None fields are updated. Returns True if a row was updated."""
        try:
            async with self._pool.acquire() as conn:
                # Build dynamic update to only set provided fields
                updates: List[str] = []
                values: List[Any] = []
                i = 1
                if data_type is not None:
                    updates.append(f"data_type = ${i}")
                    values.append(data_type)
                    i += 1
                if description is not None:
                    updates.append(f"description = ${i}")
                    values.append(description)
                    i += 1
                if publication_date is not None:
                    updates.append(f"publication_date = ${i}")
                    values.append(publication_date)
                    i += 1
                if not updates:
                    return False
                values.append(fdc_id)
                result = await conn.execute(
                    f"UPDATE foods SET {', '.join(updates)} WHERE fdc_id = ${i}",
                    *values,
                )
            updated = result.strip() == "UPDATE 1"
            if updated:
                logger.info("FoodRepository.update_food: fdc_id=%s", fdc_id)
            return updated
        except Exception as e:
            logger.exception("FoodRepository.update_food failed: fdc_id=%s, error=%s", fdc_id, e)
            raise

    async def delete_food(self, fdc_id: int) -> bool:
        """Delete a food row by fdc_id. Returns True if a row was deleted."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM foods WHERE fdc_id = $1",
                    fdc_id,
                )
            deleted = result.strip() == "DELETE 1"
            if deleted:
                logger.info("FoodRepository.delete_food: fdc_id=%s", fdc_id)
            return deleted
        except Exception as e:
            logger.exception("FoodRepository.delete_food failed: fdc_id=%s, error=%s", fdc_id, e)
            raise

