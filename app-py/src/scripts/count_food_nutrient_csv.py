"""
One-off script: count food_nutrient.csv rows the same way CsvLoadService does.
Run from app-py: python -m src.scripts.count_food_nutrient_csv
"""
import csv
import sys
from pathlib import Path

# Paths match config (src/scripts -> app-py is parent.parent.parent)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CSV_DIR = BASE_DIR.parent / "csv"
FOOD_CSV_PATH = CSV_DIR / "food.csv"
FOOD_NUTRIENT_CSV_PATH = CSV_DIR / "food_nutrient.csv"

NUTRIENT_IDS = {1008, 1003, 1085, 2039}


def parse_int(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_float(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main():
    # 1. Foundation fdc_ids from food.csv
    foundation_fdc_ids = set()
    with open(FOOD_CSV_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("data_type") or "").strip() != "foundation_food":
                continue
            fdc_id = parse_int(row.get("fdc_id") or "")
            if fdc_id is not None:
                foundation_fdc_ids.add(fdc_id)
    print(f"Foundation foods (fdc_ids): {len(foundation_fdc_ids)}")

    # 2. food_nutrient.csv counts
    total_rows = 0
    our_nutrient_rows = 0
    valid_amount = 0
    valid_id_fdc_in_foundation = 0
    row_ids_seen = set()
    duplicate_row_ids = 0
    would_insert = 0

    with open(FOOD_NUTRIENT_CSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            nutrient_id = parse_int(row.get("nutrient_id") or "")
            if nutrient_id is None or nutrient_id not in NUTRIENT_IDS:
                continue
            our_nutrient_rows += 1

            amount_val = parse_float(row.get("amount") or "")
            if amount_val is None:
                continue
            valid_amount += 1

            row_id = parse_int(row.get("id") or "")
            fdc_id = parse_int(row.get("fdc_id") or "")
            if row_id is None or fdc_id is None or fdc_id not in foundation_fdc_ids:
                continue
            valid_id_fdc_in_foundation += 1

            if row_id in row_ids_seen:
                duplicate_row_ids += 1
            else:
                row_ids_seen.add(row_id)
                would_insert += 1

    print(f"food_nutrient.csv total rows: {total_rows}")
    print()
    print("Criteria: foundation_food (fdc_id in our 436) + nutrient_id in {1003,1008,1085,2039} + valid amount + valid id.")
    print(f"Rows meeting criteria (each row = one food, one nutrient): {would_insert}")
    print()
    print(f"Breakdown: rows with our 4 nutrients (any fdc_id): {our_nutrient_rows}")
    print(f"  of those, valid amount: {valid_amount}")
    print(f"  of those, fdc_id in foundation_food set: {valid_id_fdc_in_foundation}")
    print(f"  duplicate row id: {duplicate_row_ids}")
    print(f"  => inserted: {would_insert}  |  skipped (our nutrients, non-foundation fdc_id): {our_nutrient_rows - would_insert}")


if __name__ == "__main__":
    main()
    sys.exit(0)
