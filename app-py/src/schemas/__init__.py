"""
Request body schemas for API endpoints (Pydantic models).

Used for validation and OpenAPI; main.py imports these for demo food/food_nutrient endpoints.
"""

from typing import Optional

from pydantic import BaseModel


class AddFoodBody(BaseModel):
    fdc_id: int
    data_type: str = "foundation_food"
    description: Optional[str] = None
    publication_date: Optional[str] = None


class UpdateFoodBody(BaseModel):
    data_type: Optional[str] = None
    description: Optional[str] = None
    publication_date: Optional[str] = None


class AddFoodNutrientBody(BaseModel):
    fdc_id: int
    nutrient_id: int
    amount: float


class UpdateFoodNutrientBody(BaseModel):
    fdc_id: Optional[int] = None
    nutrient_id: Optional[int] = None
    amount: Optional[float] = None


__all__ = [
    "AddFoodBody",
    "AddFoodNutrientBody",
    "UpdateFoodBody",
    "UpdateFoodNutrientBody",
]
