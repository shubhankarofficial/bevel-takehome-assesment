"""
Run the data cleaning report and print + save results.

Usage (from app-py directory):
  python -m src.data_cleaning.run_cleaning_report

Output is printed to the terminal and written to cleaning_report.txt in this folder.
"""

from pathlib import Path

from ..config import FOOD_CSV_PATH, FOOD_NUTRIENT_CSV_PATH, NUTRIENT_CSV_PATH
from .report import run_cleaning_checks

REPORT_FILE = Path(__file__).parent / "cleaning_report.txt"


def main() -> None:
    r = run_cleaning_checks(
        FOOD_CSV_PATH,
        FOOD_NUTRIENT_CSV_PATH,
        NUTRIENT_CSV_PATH,
        max_rows_to_scan=10000,
    )
    lines = [
        "=== Data cleaning report ===",
        "",
        f"Has issues: {r.has_issues}",
        "",
        f"Summary: {r.summary}",
        "",
        "Food issues:",
        *([f"  - {s}" for s in r.food_issues] or ["  (none)"]),
        "",
        "Food nutrient issues:",
        *([f"  - {s}" for s in r.food_nutrient_issues] or ["  (none)"]),
        "",
        "Nutrient issues:",
        *([f"  - {s}" for s in r.nutrient_issues] or ["  (none)"]),
    ]
    text = "\n".join(lines)
    print(text)
    REPORT_FILE.write_text(text, encoding="utf-8")
    print(f"\nReport also saved to: {REPORT_FILE}")


if __name__ == "__main__":
    main()
