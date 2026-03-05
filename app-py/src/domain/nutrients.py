"""
Domain types for nutrients.

FoodNutrient enum and NutrientAmount dataclass. Mapping from USDA data
lives in services (nutrient_mapping_service).
"""

from dataclasses import dataclass
from enum import Enum


class FoodNutrient(str, Enum):
    CALORIES = "calories"  # kilocalories
    PROTEIN = "protein"  # grams
    CARBS = "carbs"  # grams
    FAT = "fat"  # grams


@dataclass
class NutrientAmount:
    type: FoodNutrient
    amount: float
