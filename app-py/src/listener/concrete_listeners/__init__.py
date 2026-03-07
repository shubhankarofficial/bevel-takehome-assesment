"""
Concrete NOTIFY listener implementations.

- FoodIndexNotifyListener: syncs food_index_events to the search index.
"""

from .food_index_listener import FoodIndexNotifyListener

__all__ = ["FoodIndexNotifyListener"]
