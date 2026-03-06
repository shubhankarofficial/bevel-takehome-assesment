"""
Service for food_nutrient (food_nutrients table) add/update/delete.

Uses FoodNutrientRepository and FoodRepository. When deleting a food_nutrient, if that was
the last nutrient for the food, the food is also deleted from foods (and NOTIFY removes it from ES).
"""

import logging
from typing import Optional

from ..repositories.food_nutrient_repository import FoodNutrientRepository
from ..repositories.food_repository import FoodRepository

logger = logging.getLogger(__name__)


class FoodNutrientService:
    """Orchestrates food_nutrient CRUD. Deletes the food from foods when its last nutrient is removed."""

    def __init__(
        self,
        food_nutrient_repo: FoodNutrientRepository,
        food_repo: FoodRepository,
    ) -> None:
        self._repo = food_nutrient_repo
        self._food_repo = food_repo

    async def add_food_nutrient(
        self,
        fdc_id: int,
        nutrient_id: int,
        amount: float,
        *,
        id: Optional[int] = None,
    ) -> int:
        """Insert a food_nutrient row. Returns the id of the inserted row."""
        return await self._repo.insert_food_nutrient(
            fdc_id=fdc_id,
            nutrient_id=nutrient_id,
            amount=amount,
            id=id,
        )

    async def update_food_nutrient(
        self,
        id: int,
        *,
        fdc_id: Optional[int] = None,
        nutrient_id: Optional[int] = None,
        amount: Optional[float] = None,
    ) -> bool:
        """Update a food_nutrient by id. Returns True if a row was updated."""
        return await self._repo.update_food_nutrient(
            id,
            fdc_id=fdc_id,
            nutrient_id=nutrient_id,
            amount=amount,
        )

    async def delete_food_nutrient(self, id: int) -> bool:
        """
        Delete a food_nutrient by id. If that was the last nutrient for the food,
        also delete the food from foods (trigger NOTIFYs so listener removes from ES).
        Returns True if a food_nutrient row was deleted.
        """
        deleted, fdc_id = await self._repo.delete_food_nutrient(id)
        if deleted and fdc_id is not None:
            remaining = await self._repo.count_for_food(fdc_id)
            if remaining == 0:
                await self._food_repo.delete_food(fdc_id)
                logger.info(
                    "FoodNutrientService: deleted last nutrient for fdc_id=%s, removed food from foods",
                    fdc_id,
                )
        return deleted
