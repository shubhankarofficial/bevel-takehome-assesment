-- Foods table: fdc_id, data_type, description, publication_date (foundation_food only at ingest).
-- Idempotent: safe to run multiple times.
CREATE TABLE IF NOT EXISTS foods (
    fdc_id BIGINT NOT NULL PRIMARY KEY,
    data_type TEXT,
    description TEXT,
    publication_date DATE
);
