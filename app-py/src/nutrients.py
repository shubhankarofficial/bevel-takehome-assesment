"""
Nutrient mapping utilities.

Maps USDA nutrient data to the four nutrients required by the API (calories, protein, carbs, fat).
The mapping from USDA nutrient IDs to these keys lives in config (config.nutrient_mapping)
so it can be changed or extended without touching this module.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

# Import mapping from config; no hardcoded IDs here
from .config import USDA_NUTRIENT_MAPPING


class FoodNutrient(str, Enum):
    CALORIES = "calories"  # kilocalories
    PROTEIN = "protein"  # grams
    CARBS = "carbs"  # grams
    FAT = "fat"  # grams


@dataclass
class NutrientAmount:
    type: FoodNutrient
    amount: float


def map_usda_nutrients_to_food_nutrients(
    usda_amounts: Dict[int, float],
    mapping: Optional[Dict[int, str]] = None,
) -> List[NutrientAmount]:
    """
    Convert a mapping of USDA nutrient_id -> amount into a list of NutrientAmount
    for the nutrients defined in config (USDA_NUTRIENT_MAPPING).

    Any nutrient_id not in the mapping is omitted. Pass `mapping` to override
    (e.g. in tests); otherwise config.USDA_NUTRIENT_MAPPING is used.
    """
    if mapping is None:
        mapping = USDA_NUTRIENT_MAPPING
    result: List[NutrientAmount] = []
    for nutrient_id, amount in usda_amounts.items():
        api_key: Optional[str] = mapping.get(nutrient_id) # Handling of no nutrient_id found in mapping
        if api_key is None:
            continue         # Not nutrient that we are interested in
        try:
            food_nutrient = FoodNutrient(api_key)
        except ValueError:
            logging.warning(
                "Unknown nutrient key %r for nutrient_id %s; skipping",
                api_key,
                nutrient_id,
            )
            continue
        try:
            value = float(amount)
        except (TypeError, ValueError):
            logging.warning(
                "Invalid amount %r for nutrient_id %s (api_key %r); skipping",
                amount,
                nutrient_id,
                api_key,
            )
            continue
        result.append(NutrientAmount(type=food_nutrient, amount=value))
    return result
