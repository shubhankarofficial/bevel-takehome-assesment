"""
Demonstrations of listener functionality: run search, change DB, run search again to show ES updates.

Requires ingest to have been run (index exists) and listener to be running (run_ingest or run_food_index_listener).
"""

from .food_demos import (
    demonstrate_add_food,
    demonstrate_delete_food,
    demonstrate_update_food,
)
from .food_nutrient_demos import (
    demonstrate_add_food_nutrient,
    demonstrate_delete_food_nutrient,
    demonstrate_update_food_nutrient,
)

__all__ = [
    "demonstrate_add_food",
    "demonstrate_delete_food",
    "demonstrate_update_food",
    "demonstrate_add_food_nutrient",
    "demonstrate_delete_food_nutrient",
    "demonstrate_update_food_nutrient",
]
