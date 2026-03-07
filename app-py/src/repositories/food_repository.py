"""
Repository for food data in Postgres.
Uses SQLAlchemy async engine; same public API as before (dict returns, same method names).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.models import Food

logger = logging.getLogger(__name__)


class FoodRepository:
    """
    Repository responsible for accessing food data in Postgres.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def _session(self) -> AsyncSession:
        return AsyncSession(self._engine, expire_on_commit=False)

    def _row_to_dict(self, row: Food) -> Dict[str, Any]:
        return {
            "fdc_id": row.fdc_id,
            "data_type": row.data_type,
            "description": row.description,
            "publication_date": row.publication_date,
        }

    async def get_food_by_fdc_id(self, fdc_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single food row by its USDA fdc_id."""
        try:
            async with self._session() as session:
                result = await session.execute(select(Food).where(Food.fdc_id == fdc_id))
                row = result.scalar_one_or_none()
            if row is not None:
                logger.debug("FoodRepository.get_food_by_fdc_id found: fdc_id=%s", fdc_id)
            return self._row_to_dict(row) if row is not None else None
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
        """Return a batch of foundation foods for bulk processing (e.g. indexing)."""
        try:
            async with self._session() as session:
                result = await session.execute(
                    select(Food)
                    .where(Food.data_type == "foundation_food")
                    .order_by(Food.fdc_id)
                    .offset(offset)
                    .limit(limit)
                )
                rows = result.scalars().all()
            return [self._row_to_dict(r) for r in rows]
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
            values = [
                {
                    "fdc_id": r[0],
                    "data_type": r[1],
                    "description": r[2],
                    "publication_date": r[3],
                }
                for r in rows
            ]
            ins = pg_insert(Food).values(values)
            stmt = ins.on_conflict_do_update(
                index_elements=["fdc_id"],
                set_={
                    "data_type": ins.excluded.data_type,
                    "description": ins.excluded.description,
                    "publication_date": ins.excluded.publication_date,
                },
            )
            async with self._session() as session:
                await session.execute(stmt)
                await session.commit()
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
            from sqlalchemy import func

            async with self._session() as session:
                result = await session.execute(
                    select(func.count())
                    .select_from(Food)
                    .where(Food.data_type == "foundation_food")
                )
                n = result.scalar_one()
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
            async with self._session() as session:
                session.add(
                    Food(
                        fdc_id=fdc_id,
                        data_type=data_type,
                        description=description,
                        publication_date=publication_date,
                    )
                )
                await session.commit()
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
            updates: Dict[str, Any] = {}
            if data_type is not None:
                updates["data_type"] = data_type
            if description is not None:
                updates["description"] = description
            if publication_date is not None:
                updates["publication_date"] = publication_date
            if not updates:
                return False
            async with self._session() as session:
                result = await session.execute(
                    update(Food).where(Food.fdc_id == fdc_id).values(**updates)
                )
                await session.commit()
            updated = result.rowcount == 1
            if updated:
                logger.info("FoodRepository.update_food: fdc_id=%s", fdc_id)
            return updated
        except Exception as e:
            logger.exception("FoodRepository.update_food failed: fdc_id=%s, error=%s", fdc_id, e)
            raise

    async def delete_food(self, fdc_id: int) -> bool:
        """Delete a food row by fdc_id. Returns True if a row was deleted."""
        try:
            from sqlalchemy import delete

            async with self._session() as session:
                result = await session.execute(delete(Food).where(Food.fdc_id == fdc_id))
                await session.commit()
            deleted = result.rowcount == 1
            if deleted:
                logger.info("FoodRepository.delete_food: fdc_id=%s", fdc_id)
            return deleted
        except Exception as e:
            logger.exception("FoodRepository.delete_food failed: fdc_id=%s, error=%s", fdc_id, e)
            raise
