"""PostgreSQL connection settings."""

import os

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "54328"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "bevel")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "bevel")
