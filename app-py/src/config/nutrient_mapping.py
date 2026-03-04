"""
USDA nutrient ID -> API nutrient key mapping.

This is the single place that defines which USDA nutrient IDs (from nutrient.csv)
map to the nutrients we expose in the API. Keeping it in config allows:
- Changing IDs without touching business logic (e.g. if USDA dataset changes).
- Adding new nutrients later by extending the mapping (and the API enum).
- Overriding via env or a config file in the future if needed.

Default mapping (USDA Foundation Foods / nutrient.csv):
- 2047 = Energy (Atwater General Factors), KCAL -> calories
- 1003 = Protein, G -> protein
- 1005 = Carbohydrate, by difference, G -> carbs
- 1004 = Total lipid (fat), G -> fat
"""

from typing import Dict

# USDA nutrient_id -> our API key (must match FoodNutrient enum values in nutrients.py)
# Structure: int (USDA id) -> str (calories | protein | carbs | fat)
USDA_NUTRIENT_MAPPING: Dict[int, str] = {
    2047: "calories",   # Energy (Atwater General Factors), KCAL
    1003: "protein",   # Protein, G
    1005: "carbs",     # Carbohydrate, by difference, G
    1004: "fat",       # Total lipid (fat), G
}
