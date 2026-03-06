"""
USDA nutrient ID -> API nutrient key mapping.

This is the single place that defines which USDA nutrient IDs (from nutrient.csv)
map to the nutrients we expose in the API. Keeping it in config allows:
- Changing IDs without touching business logic (e.g. if USDA dataset changes).
- Adding new nutrients later by extending the mapping (and the API enum).
- Overriding via env or a config file in the future if needed.

Mapping (from nutrient.csv):
- 1008 = Energy -> calories
- 1003 = Protein, G -> protein
- 2039 = Carb -> carbs
- 1085 = Total Fat (NLEA) -> fat
"""

from typing import Dict

# USDA nutrient_id -> our API key (must match FoodNutrient enum values in domain.nutrients)
# Structure: int (USDA id) -> str (calories | protein | carbs | fat)
USDA_NUTRIENT_MAPPING: Dict[int, str] = {
    1008: "calories",   # Energy
    1003: "protein",   # Protein, G
    2039: "carbs",     # Carb
    1085: "fat",       # Total Fat (NLEA)
}
