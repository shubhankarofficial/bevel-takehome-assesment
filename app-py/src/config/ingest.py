"""Ingestion pipeline settings (batch sizes, etc.)."""

import os

INGEST_DB_BATCH_SIZE = int(os.getenv("INGEST_DB_BATCH_SIZE", "1000"))
INDEX_BULK_BATCH_SIZE = int(os.getenv("INDEX_BULK_BATCH_SIZE", "1000"))
