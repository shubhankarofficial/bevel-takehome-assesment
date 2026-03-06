"""
FoodSearchResponse and nested types for the /search endpoint.

Matches the assignment contract: FoodSearchResponse { foods: Food[] },
Food { name, nutrients: NutrientAmount[] }, NutrientAmount { type, amount }.
Uses domain FoodNutrient enum so allowed values are defined in one place.
"""

from pydantic import BaseModel

from ..domain import FoodNutrient


class NutrientAmountResponse(BaseModel):
    """Nutrient amount in API response. Type is one of calories, protein, carbs, fat."""

    type: FoodNutrient
    amount: float


class FoodResponse(BaseModel):
    """Single food in API response."""

    name: str
    nutrients: list[NutrientAmountResponse]


class FoodSearchResponse(BaseModel):
    """Response body for GET /search?query= ."""

    foods: list[FoodResponse]
