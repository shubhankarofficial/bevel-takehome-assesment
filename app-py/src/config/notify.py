"""
Postgres NOTIFY channel and payload format for food index sync.

Used by DB triggers (NOTIFY) and the listener process (LISTEN).
Payload shape: JSON with table, op, fdc_id.
"""

# Channel name for NOTIFY/LISTEN (must match trigger in migration 004).
NOTIFY_CHANNEL_FOOD_INDEX = "food_index_events"

# Payload format (JSON string): {"table": "foods"|"food_nutrients", "op": "INSERT"|"UPDATE"|"DELETE", "fdc_id": <int>}
