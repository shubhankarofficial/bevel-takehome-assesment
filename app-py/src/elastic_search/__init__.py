"""
Elasticsearch index facades (write/read access to ES indices).

For now this package contains the FoodSearchIndex used to manage the foods
index in Elasticsearch. Other indices can be added here later.
"""

from .food_search_index import FoodSearchIndex

__all__ = ["FoodSearchIndex"]

