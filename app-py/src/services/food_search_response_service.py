"""
Build FoodSearchResponse (API response shape) from domain Food list.
"""

from ..domain import Food
from ..responses import FoodResponse, FoodSearchResponse, NutrientAmountResponse


class FoodSearchResponseService:
    """
    Converts domain Food list to the Pydantic response shape for /search.
    """

    def from_domain_foods(self, foods: list[Food]) -> FoodSearchResponse:
        """Build FoodSearchResponse from a list of domain Food objects."""
        out: list[FoodResponse] = []
        for f in foods:
            nutrients = [
                NutrientAmountResponse(type=na.type, amount=na.amount)
                for na in f.nutrients
            ]
            out.append(FoodResponse(name=f.name, nutrients=nutrients))
        return FoodSearchResponse(foods=out)
