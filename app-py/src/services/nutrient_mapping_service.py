"""
Map USDA nutrient data to domain NutrientAmount list.

Uses config (USDA_NUTRIENT_MAPPING) so IDs can change without touching this logic.
"""

import logging
from typing import Dict, List, Optional

from ..config import USDA_NUTRIENT_MAPPING
from ..domain import FoodNutrient, NutrientAmount


class NutrientMappingService:
    """
    Converts USDA nutrient_id -> amount data into domain NutrientAmount list.
    """

    def map_usda_to_food_nutrients(
        self,
        usda_amounts: Dict[int, float],
        mapping: Optional[Dict[int, str]] = None,
    ) -> List[NutrientAmount]:
        """
        Return a list of NutrientAmount for the four nutrients we expose
        (calories, protein, carbs, fat). Any nutrient_id not in the mapping
        is omitted. Pass `mapping` to override (e.g. in tests).
        """
        if mapping is None:
            mapping = USDA_NUTRIENT_MAPPING
        result: List[NutrientAmount] = []
        for nutrient_id, amount in usda_amounts.items():
            api_key: Optional[str] = mapping.get(nutrient_id)
            if api_key is None:
                continue
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
