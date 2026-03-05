"""
Domain layer: core types (dataclasses / enums).

No I/O here; used by services, ingest, and API.
"""

from .food import Food
from .nutrients import FoodNutrient, NutrientAmount

__all__ = [
    "Food",
    "FoodNutrient",
    "NutrientAmount",
]
