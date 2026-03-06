"""
Service for food (foods table) add/update/delete.

Uses FoodRepository. DB trigger will fire NOTIFY on changes so the listener can sync the index.
"""

import logging
from typing import Any, Optional

from ..repositories.food_repository import FoodRepository

logger = logging.getLogger(__name__)


class FoodService:
    """Orchestrates food CRUD via FoodRepository (foods table)."""

    def __init__(self, food_repo: FoodRepository) -> None:
        self._repo = food_repo

    async def add_food(
        self,
        fdc_id: int,
        data_type: str,
        description: Optional[str] = None,
        publication_date: Optional[Any] = None,
    ) -> None:
        """Insert a food. Raises if fdc_id already exists."""
        await self._repo.insert_food(
            fdc_id=fdc_id,
            data_type=data_type,
            description=description,
            publication_date=publication_date,
        )

    async def update_food(
        self,
        fdc_id: int,
        *,
        data_type: Optional[str] = None,
        description: Optional[str] = None,
        publication_date: Optional[Any] = None,
    ) -> bool:
        """Update a food by fdc_id. Returns True if a row was updated."""
        return await self._repo.update_food(
            fdc_id,
            data_type=data_type,
            description=description,
            publication_date=publication_date,
        )

    async def delete_food(self, fdc_id: int) -> bool:
        """Delete a food by fdc_id. Returns True if a row was deleted."""
        return await self._repo.delete_food(fdc_id)
