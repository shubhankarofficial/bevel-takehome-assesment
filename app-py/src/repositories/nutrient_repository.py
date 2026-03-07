"""
Repository for the nutrients table in Postgres.
Uses SQLAlchemy async engine; same public API as before (dict returns, same method names).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.models import Nutrient

logger = logging.getLogger(__name__)


class NutrientRepository:
    """
    Repository for nutrient reference data (id, name, unit_name).
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def _session(self) -> AsyncSession:
        return AsyncSession(self._engine, expire_on_commit=False)

    async def bulk_insert(
        self,
        rows: List[Tuple[int, Optional[str], Optional[str]]],
    ) -> int:
        """
        Insert many rows into nutrients. Each row is (id, name, unit_name).
        Returns the number of rows inserted.
        """
        if not rows:
            return 0
        try:
            values = [
                {"id": r[0], "name": r[1], "unit_name": r[2]}
                for r in rows
            ]
            ins = pg_insert(Nutrient).values(values)
            stmt = ins.on_conflict_do_update(
                index_elements=["id"],
                set_={"name": ins.excluded.name, "unit_name": ins.excluded.unit_name},
            )
            async with self._session() as session:
                await session.execute(stmt)
                await session.commit()
            logger.info("NutrientRepository.bulk_insert completed: inserted %s rows", len(rows))
            return len(rows)
        except Exception as e:
            logger.exception(
                "NutrientRepository.bulk_insert failed: %s rows, error=%s",
                len(rows),
                e,
            )
            raise

    async def get_by_id(self, nutrient_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single nutrient row by id."""
        try:
            async with self._session() as session:
                result = await session.execute(
                    select(Nutrient).where(Nutrient.id == nutrient_id)
                )
                row = result.scalar_one_or_none()
            if row is not None:
                logger.debug("NutrientRepository.get_by_id found: nutrient_id=%s", nutrient_id)
            return (
                {"id": row.id, "name": row.name, "unit_name": row.unit_name}
                if row is not None
                else None
            )
        except Exception as e:
            logger.exception(
                "NutrientRepository.get_by_id failed: nutrient_id=%s, error=%s",
                nutrient_id,
                e,
            )
            raise

    async def count(self) -> int:
        """Return total number of rows in nutrients (for logging/observability)."""
        try:
            from sqlalchemy import func

            async with self._session() as session:
                result = await session.execute(select(func.count()).select_from(Nutrient))
                n = result.scalar_one()
            count = int(n)
            logger.debug("NutrientRepository.count: %s", count)
            return count
        except Exception as e:
            logger.exception("NutrientRepository.count failed: error=%s", e)
            raise
