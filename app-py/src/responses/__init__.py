"""
API response shapes (Pydantic models).

Used by FastAPI for validation, serialization, and OpenAPI schema.
Conversion from domain to response is in services (FoodSearchResponseService).
"""

from .error_response import ErrorResponse
from .food_search_response import (
    FoodResponse,
    FoodSearchResponse,
    NutrientAmountResponse,
)

__all__ = [
    "ErrorResponse",
    "FoodResponse",
    "FoodSearchResponse",
    "NutrientAmountResponse",
]
