"""
Listener process for Postgres NOTIFY → Elasticsearch index sync.

- NotifyListener: interface for a subscriber to a NOTIFY channel.
- FoodIndexNotifyListener: implementation for channel food_index_events; queues
  payloads, worker processes them via FoodIndexingService, failures retried then dropped.
"""

from .base import NotifyListener
from .food_index_listener import FoodIndexNotifyListener

__all__ = ["NotifyListener", "FoodIndexNotifyListener"]
