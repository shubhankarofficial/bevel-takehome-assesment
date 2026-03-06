"""
Phase 1.4 verification: listen for NOTIFY on food_index_events and print payloads.

Run from app-py with venv active:
  python scripts/verify_notify.py

In another terminal, run ingest or change DB (e.g. UPDATE foods SET description = ... WHERE fdc_id = ...)
to see notifications printed here.
"""
import asyncio
import os
import sys

# Run from app-py so src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

import asyncpg
from src.config import NOTIFY_CHANNEL_FOOD_INDEX
from src.config.database import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)


async def main():
    conn = await asyncpg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB,
    )
    await conn.add_listener(NOTIFY_CHANNEL_FOOD_INDEX, on_notify)
    print(f"Listening on channel '{NOTIFY_CHANNEL_FOOD_INDEX}'. Change DB in another terminal to see payloads.")
    while True:
        await asyncio.sleep(3600)


def on_notify(connection, pid, channel, payload):
    print(f"NOTIFY {channel}: {payload}")


if __name__ == "__main__":
    asyncio.run(main())
