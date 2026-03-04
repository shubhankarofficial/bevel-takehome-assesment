"""
Central configuration package.

All environment-dependent and data-driven configuration lives here.
Import from this package so there is a single source of truth:

    from src.config import POSTGRES_HOST, FOOD_INDEX_NAME, USDA_NUTRIENT_MAPPING

Adding new config (e.g. feature flags, new services) goes in a new module
under config/ and is re-exported here.
"""

from .database import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_DB,
)
from .elasticsearch import ELASTICSEARCH_URL, FOOD_INDEX_NAME
from .paths import BASE_DIR, CSV_DIR, FOOD_CSV_PATH, FOOD_NUTRIENT_CSV_PATH, NUTRIENT_CSV_PATH
from .ingest import INGEST_DB_BATCH_SIZE, INDEX_BULK_BATCH_SIZE
from .nutrient_mapping import USDA_NUTRIENT_MAPPING

__all__ = [
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "ELASTICSEARCH_URL",
    "FOOD_INDEX_NAME",
    "BASE_DIR",
    "CSV_DIR",
    "FOOD_CSV_PATH",
    "FOOD_NUTRIENT_CSV_PATH",
    "NUTRIENT_CSV_PATH",
    "INGEST_DB_BATCH_SIZE",
    "INDEX_BULK_BATCH_SIZE",
    "USDA_NUTRIENT_MAPPING",
]
