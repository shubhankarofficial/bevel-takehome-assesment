"""
Service for food_nutrient (food_nutrients table) add/update/delete.

Uses FoodNutrientRepository and FoodRepository. Food stays in foods even when it has no
nutrient rows; we do not delete the food when the last food_nutrient is removed (so it
remains in the search index with empty nutrients).
"""

import logging
from typing import Optional

from ..repositories.food_nutrient_repository import FoodNutrientRepository
from ..repositories.food_repository import FoodRepository

logger = logging.getLogger(__name__)


class FoodNutrientService:
    """Orchestrates food_nutrient CRUD. Food remains in foods table when last nutrient is deleted."""

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
        Delete a food_nutrient by id. The food stays in foods even if this was its last nutrient;
        listener will reindex the food with empty nutrients (food remains in ES).
        Returns True if a food_nutrient row was deleted.
        """
        deleted, _fdc_id = await self._repo.delete_food_nutrient(id)
        return deleted
