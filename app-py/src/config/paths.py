"""File system paths (CSV directory, etc.)."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # app-py/
_DEFAULT_CSV_DIR = BASE_DIR.parent / "csv"
CSV_DIR = Path(os.getenv("CSV_DIR", str(_DEFAULT_CSV_DIR)))
FOOD_CSV_PATH = CSV_DIR / "food.csv"
FOOD_NUTRIENT_CSV_PATH = CSV_DIR / "food_nutrient.csv"
NUTRIENT_CSV_PATH = CSV_DIR / "nutrient.csv"
