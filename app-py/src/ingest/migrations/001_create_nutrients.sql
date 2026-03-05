-- Nutrients table: id, name, unit_name (only columns we need for querying).
-- Idempotent: safe to run multiple times.
CREATE TABLE IF NOT EXISTS nutrients (
    id INTEGER NOT NULL PRIMARY KEY,
    name TEXT,
    unit_name TEXT
);
