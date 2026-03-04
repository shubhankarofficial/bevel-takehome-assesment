"""
Run cleaning checks on USDA CSVs and produce a report.

Shows explicitly what we checked for; if nothing needs cleaning, the report states that.
Extensible: add new checks here when new data or nutrients are introduced.
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CleaningReport:
    """Result of running cleaning checks on the CSV data."""

    food_issues: List[str] = field(default_factory=list)
    food_nutrient_issues: List[str] = field(default_factory=list)
    nutrient_issues: List[str] = field(default_factory=list)
    summary: str = ""

    @property
    def has_issues(self) -> bool:
        return bool(self.food_issues or self.food_nutrient_issues or self.nutrient_issues)


def run_cleaning_checks(
    food_path: Path,
    food_nutrient_path: Path,
    nutrient_path: Path,
    *,
    max_rows_to_scan: Optional[int] = 5000,
) -> CleaningReport:
    """
    Run validation/cleaning checks on the three USDA CSVs.

    Returns a report listing any issues found. If nothing worth cleaning is found,
    the report will be empty and summary will state that we tried but found no issues.
    Extensible: add more checks (e.g. for new nutrients or columns) here.
    """
    report = CleaningReport()

    # --- food.csv checks ---
    if not food_path.exists():
        report.food_issues.append(f"File not found: {food_path}")
    else:
        try:
            with open(food_path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows_checked = 0
                foundation_count = 0
                empty_description_count = 0
                whitespace_description_count = 0
                for row in reader:
                    rows_checked += 1
                    if max_rows_to_scan and rows_checked >= max_rows_to_scan:
                        break
                    data_type = (row.get("data_type") or "").strip()
                    if data_type == "foundation_food":
                        foundation_count += 1
                    desc = row.get("description") or ""
                    if not desc.strip():
                        empty_description_count += 1
                    elif desc != desc.strip():
                        whitespace_description_count += 1
                if foundation_count == 0 and rows_checked > 0:
                    report.food_issues.append(
                        "No rows with data_type='foundation_food' in scanned rows."
                    )
                if empty_description_count > 0:
                    report.food_issues.append(
                        f"Found {empty_description_count} rows with empty description (in scan)."
                    )
                if whitespace_description_count > 0:
                    report.food_issues.append(
                        f"Found {whitespace_description_count} rows with leading/trailing whitespace in description (in scan)."
                    )
        except Exception as e:
            report.food_issues.append(f"Error reading food CSV: {e}")

    # --- food_nutrient.csv checks ---
    if not food_nutrient_path.exists():
        report.food_nutrient_issues.append(f"File not found: {food_nutrient_path}")
    else:
        try:
            with open(food_nutrient_path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows_checked = 0
                empty_amount_count = 0
                non_numeric_amount_count = 0
                for row in reader:
                    rows_checked += 1
                    if max_rows_to_scan and rows_checked >= max_rows_to_scan:
                        break
                    amount_str = (row.get("amount") or "").strip()
                    if not amount_str:
                        empty_amount_count += 1
                        continue
                    try:
                        float(amount_str)
                    except ValueError:
                        non_numeric_amount_count += 1
                if empty_amount_count > 0:
                    report.food_nutrient_issues.append(
                        f"Found {empty_amount_count} rows with empty amount (in scan)."
                    )
                if non_numeric_amount_count > 0:
                    report.food_nutrient_issues.append(
                        f"Found {non_numeric_amount_count} rows with non-numeric amount (in scan)."
                    )
        except Exception as e:
            report.food_nutrient_issues.append(f"Error reading food_nutrient CSV: {e}")

    # --- nutrient.csv checks (structure only; we don't change this file) ---
    if not nutrient_path.exists():
        report.nutrient_issues.append(f"File not found: {nutrient_path}")
    else:
        try:
            with open(nutrient_path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                required = {"id", "name", "unit_name"}
                row = next(reader, None)
                if row and not required.issubset(row.keys()):
                    report.nutrient_issues.append(
                        f"Expected columns {required}; got {list(row.keys())}"
                    )
        except Exception as e:
            report.nutrient_issues.append(f"Error reading nutrient CSV: {e}")

    # Summary
    if report.has_issues:
        report.summary = (
            f"Cleaning checks found issues: "
            f"food={len(report.food_issues)}, "
            f"food_nutrient={len(report.food_nutrient_issues)}, "
            f"nutrient={len(report.nutrient_issues)}."
        )
        logger.info("Data cleaning report: %s", report.summary)
    else:
        report.summary = (
            "Cleaning checks completed. No issues worth cleaning found; "
            "data is acceptable for ingest (filtering and validation will still run at ingest time)."
        )
        logger.info("Data cleaning report: %s", report.summary)

    return report
