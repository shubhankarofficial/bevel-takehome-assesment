"""
Repository for food_nutrients table in Postgres.
Uses SQLAlchemy async engine; same public API as before (dict/list returns, same method names).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.models import FoodNutrient

logger = logging.getLogger(__name__)


class FoodNutrientRepository:
    """
    Repository for accessing nutrient amounts per food from Postgres.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def _session(self) -> AsyncSession:
        return AsyncSession(self._engine, expire_on_commit=False)

    async def get_usda_nutrient_amounts_for_food(self, fdc_id: int) -> Dict[int, float]:
        """Return a mapping of USDA nutrient_id -> amount for the given food."""
        try:
            async with self._session() as session:
                result = await session.execute(
                    select(FoodNutrient.nutrient_id, FoodNutrient.amount).where(
                        FoodNutrient.fdc_id == fdc_id
                    )
                )
                rows = result.all()
            out = {int(r[0]): float(r[1]) for r in rows}
            logger.debug(
                "FoodNutrientRepository.get_usda_nutrient_amounts_for_food: fdc_id=%s, nutrients=%s",
                fdc_id,
                len(out),
            )
            return out
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
        """
        if not fdc_ids:
            return {}
        try:
            async with self._session() as session:
                result = await session.execute(
                    select(FoodNutrient.fdc_id, FoodNutrient.nutrient_id, FoodNutrient.amount).where(
                        FoodNutrient.fdc_id.in_(fdc_ids)
                    )
                )
                rows = result.all()
            by_food: Dict[int, Dict[int, float]] = {}
            for r in rows:
                food_id = int(r[0])
                nutrient_id = int(r[1])
                amount = float(r[2])
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
            values = [
                {"id": r[0], "fdc_id": r[1], "nutrient_id": r[2], "amount": r[3]}
                for r in rows
            ]
            ins = pg_insert(FoodNutrient).values(values)
            stmt = ins.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "fdc_id": ins.excluded.fdc_id,
                    "nutrient_id": ins.excluded.nutrient_id,
                    "amount": ins.excluded.amount,
                },
            )
            async with self._session() as session:
                await session.execute(stmt)
                await session.commit()
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
            from sqlalchemy import func

            async with self._session() as session:
                result = await session.execute(
                    select(func.count())
                    .select_from(FoodNutrient)
                    .where(FoodNutrient.fdc_id == fdc_id)
                )
                n = result.scalar_one()
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
            async with self._session() as session:
                if id is not None:
                    session.add(
                        FoodNutrient(
                            id=id,
                            fdc_id=fdc_id,
                            nutrient_id=nutrient_id,
                            amount=amount,
                        )
                    )
                    await session.commit()
                    return id
                # Use raw SQL to match original COALESCE(MAX(id),0)+1 behavior
                r = await session.execute(
                    text("""
                        INSERT INTO food_nutrients (id, fdc_id, nutrient_id, amount)
                        SELECT COALESCE(MAX(fn.id), 0) + 1, :fdc_id, :nutrient_id, :amount
                        FROM food_nutrients fn
                        RETURNING id
                    """),
                    {"fdc_id": fdc_id, "nutrient_id": nutrient_id, "amount": amount},
                )
                row = r.mappings().first()
                await session.commit()
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
            updates: Dict[str, Any] = {}
            if fdc_id is not None:
                updates["fdc_id"] = fdc_id
            if nutrient_id is not None:
                updates["nutrient_id"] = nutrient_id
            if amount is not None:
                updates["amount"] = amount
            if not updates:
                return False
            async with self._session() as session:
                result = await session.execute(
                    update(FoodNutrient).where(FoodNutrient.id == id).values(**updates)
                )
                await session.commit()
            updated = result.rowcount == 1
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
        """
        try:
            async with self._session() as session:
                # Fetch fdc_id first (same as original)
                result = await session.execute(
                    select(FoodNutrient.fdc_id).where(FoodNutrient.id == id)
                )
                row = result.first()
                if row is None:
                    return (False, None)
                fdc_id = int(row[0])
                del_result = await session.execute(delete(FoodNutrient).where(FoodNutrient.id == id))
                await session.commit()
            deleted = del_result.rowcount == 1
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
