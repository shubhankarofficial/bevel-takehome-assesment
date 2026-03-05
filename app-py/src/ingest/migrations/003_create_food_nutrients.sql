-- Food_nutrients table: id, fdc_id, nutrient_id, amount.
-- Idempotent: safe to run multiple times.
CREATE TABLE IF NOT EXISTS food_nutrients (
    id BIGINT NOT NULL PRIMARY KEY,
    fdc_id BIGINT NOT NULL REFERENCES foods(fdc_id) ON DELETE CASCADE,
    nutrient_id INTEGER NOT NULL REFERENCES nutrients(id) ON DELETE RESTRICT,
    amount NUMERIC NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_food_nutrients_fdc_id ON food_nutrients(fdc_id);
