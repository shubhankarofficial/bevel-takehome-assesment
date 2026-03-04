"""Elasticsearch connection and index settings."""

import os

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
FOOD_INDEX_NAME = os.getenv("FOOD_INDEX_NAME", "foods")
