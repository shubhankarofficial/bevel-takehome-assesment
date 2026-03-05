"""
Run database migrations in order.

Lists .sql files in config MIGRATIONS_DIR, sorts by name, executes each and logs
completion to console. Idempotent DDL (CREATE TABLE IF NOT EXISTS) so safe to re-run.
Included in ingest pipeline later.
"""

import logging
from pathlib import Path
from typing import List, Optional

import asyncpg

from ..config import MIGRATIONS_DIR

logger = logging.getLogger(__name__)


def _split_sql_statements(content: str) -> List[str]:
    """Split SQL file by semicolon; return non-empty stripped statements."""
    parts = content.split(";")
    return [p.strip() for p in parts if p.strip()]


class MigrationService:
    """Runs migration SQL files in order and logs each completion."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        migrations_dir: Optional[Path] = None,
    ) -> None:
        self._pool = pool
        self._migrations_dir = migrations_dir or MIGRATIONS_DIR

    async def run(self) -> None:
        """Run all .sql files in migrations dir in sorted order; log after each."""
        if not self._migrations_dir.exists():
            logger.warning("Migrations dir not found: %s", self._migrations_dir)
            return
        files = sorted(self._migrations_dir.glob("*.sql"))
        if not files:
            logger.info("No migration files in %s", self._migrations_dir)
            return
        async with self._pool.acquire() as conn:
            for path in files:
                name = path.name
                try:
                    content = path.read_text(encoding="utf-8")
                    for stmt in _split_sql_statements(content):
                        if stmt:
                            await conn.execute(stmt)
                    logger.info("Migration completed: %s", name)
                except Exception as e:
                    logger.exception("Migration failed: %s - %s", name, e)
                    raise
