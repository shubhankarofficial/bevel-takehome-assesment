"""
Run cleaning checks on USDA CSVs and produce a report.

Reports what is wrong in the rows/columns we care about so we can fix in ingest.
For each CSV we report every issue type: either "N found" or "none".
food_nutrient checks only the 4 nutrients we expose (from config).
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from ..config import USDA_NUTRIENT_MAPPING

logger = logging.getLogger(__name__)

# Nutrient IDs we care about (calories, protein, carbs, fat)
NUTRIENT_IDS_WE_CARE_ABOUT: Set[int] = set(USDA_NUTRIENT_MAPPING.keys())


@dataclass
class CleaningReport:
    """Result of running cleaning checks on the CSV data."""

    food_issues: List[str] = field(default_factory=list)
    food_nutrient_issues: List[str] = field(default_factory=list)
    nutrient_issues: List[str] = field(default_factory=list)
    summary: str = ""

    @property
    def has_issues(self) -> bool:
        def _line_is_issue(s: str) -> bool:
            if s.startswith("File not found") or "Error" in s:
                return True
            if s.startswith("Foundation_food rows in scan"):
                return s.endswith(": none")
            if s.endswith(": none"):
                return False
            return " found" in s
        return (
            any(_line_is_issue(s) for s in self.food_issues)
            or any(_line_is_issue(s) for s in self.food_nutrient_issues)
            or any(_line_is_issue(s) for s in self.nutrient_issues)
        )


def _parse_int(s: str) -> Optional[int]:
    """Return int if s is non-empty and parsable, else None."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _fmt(label: str, count: int) -> str:
    """Format one issue line: 'label: none' or 'label: N found'."""
    if count <= 0:
        return f"{label}: none"
    return f"{label}: {count} found"


def run_cleaning_checks(
    food_path: Path,
    food_nutrient_path: Path,
    nutrient_path: Path,
    *,
    max_rows_to_scan: Optional[int] = 5000,
) -> CleaningReport:
    """
    Run validation/cleaning checks on the three USDA CSVs.

    Only checks data we care about: foundation_food rows (food), all nutrients (id),
    and food_nutrient rows with valid amount. Returns a report of issues that would
    affect ingest.
    """
    report = CleaningReport()

    # --- food.csv: only foundation_food rows; every issue type reported ---
    foundation_count = 0
    dup_fdc_id = 0
    empty_invalid_fdc_id = 0
    empty_description = 0
    whitespace_description = 0
    if not food_path.exists():
        report.food_issues.append(f"File not found: {food_path}")
    else:
        try:
            with open(food_path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows_checked = 0
                foundation_fdc_ids: List[Optional[int]] = []
                for row in reader:
                    rows_checked += 1
                    if max_rows_to_scan and rows_checked >= max_rows_to_scan:
                        break
                    data_type = (row.get("data_type") or "").strip()
                    if data_type != "foundation_food":
                        continue
                    foundation_count += 1
                    fdc_id_val = _parse_int(row.get("fdc_id") or "")
                    foundation_fdc_ids.append(fdc_id_val)
                    desc = (row.get("description") or "").strip()
                    if not desc:
                        empty_description += 1
                    elif (row.get("description") or "") != desc:
                        whitespace_description += 1
                if foundation_count > 0:
                    seen: Set[int] = set()
                    duplicates: Set[int] = set()
                    for v in foundation_fdc_ids:
                        if v is None:
                            empty_invalid_fdc_id += 1
                        elif v in seen:
                            duplicates.add(v)
                        else:
                            seen.add(v)
                    dup_fdc_id = len(duplicates)
            report.food_issues.extend([
                _fmt("Foundation_food rows in scan (data_type=foundation_food)", foundation_count),
                _fmt("Duplicate fdc_id among foundation_food", dup_fdc_id),
                _fmt("Empty or non-integer fdc_id", empty_invalid_fdc_id),
                _fmt("Empty description", empty_description),
                _fmt("Leading/trailing whitespace in description", whitespace_description),
            ])
        except Exception as e:
            report.food_issues.append(f"Error reading food CSV: {e}")

    # --- nutrient.csv: every issue type reported ---
    missing_columns = 0
    dup_nutrient_id = 0
    empty_invalid_nutrient_id = 0
    if not nutrient_path.exists():
        report.nutrient_issues.append(f"File not found: {nutrient_path}")
    else:
        try:
            with open(nutrient_path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                required = {"id", "name", "unit_name"}
                row = next(reader, None)
                if row and not required.issubset(row.keys()):
                    missing_columns = 1
                seen_ids: Set[int] = set()
                duplicate_ids: Set[int] = set()
                if row:
                    vid = _parse_int(row.get("id") or "")
                    if vid is None:
                        empty_invalid_nutrient_id += 1
                    elif vid in seen_ids:
                        duplicate_ids.add(vid)
                    else:
                        seen_ids.add(vid)
                for row in reader:
                    vid = _parse_int(row.get("id") or "")
                    if vid is None:
                        empty_invalid_nutrient_id += 1
                    elif vid in seen_ids:
                        duplicate_ids.add(vid)
                    else:
                        seen_ids.add(vid)
                dup_nutrient_id = len(duplicate_ids)
            report.nutrient_issues.extend([
                _fmt("Missing required columns (id, name, unit_name)", missing_columns),
                _fmt("Duplicate nutrient id", dup_nutrient_id),
                _fmt("Empty or non-integer id", empty_invalid_nutrient_id),
            ])
        except Exception as e:
            report.nutrient_issues.append(f"Error reading nutrient CSV: {e}")

    # --- food_nutrient.csv: only the 4 nutrients we care about; every issue type reported ---
    empty_amount = 0
    non_numeric_amount = 0
    dup_id = 0
    empty_invalid_fdc_id = 0
    empty_invalid_nutrient_id = 0
    if not food_nutrient_path.exists():
        report.food_nutrient_issues.append(f"File not found: {food_nutrient_path}")
    else:
        try:
            with open(food_nutrient_path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows_checked = 0
                seen_ids: Set[int] = set()
                duplicate_ids: Set[int] = set()
                for row in reader:
                    rows_checked += 1
                    if max_rows_to_scan and rows_checked >= max_rows_to_scan:
                        break
                    nutrient_id_val = _parse_int(row.get("nutrient_id") or "")
                    if nutrient_id_val not in NUTRIENT_IDS_WE_CARE_ABOUT:
                        continue
                    amount_str = (row.get("amount") or "").strip()
                    if not amount_str:
                        empty_amount += 1
                        continue
                    try:
                        float(amount_str)
                    except ValueError:
                        non_numeric_amount += 1
                        continue
                    row_id = _parse_int(row.get("id") or "")
                    fdc_id_val = _parse_int(row.get("fdc_id") or "")
                    if row_id is None:
                        continue
                    if row_id in seen_ids:
                        duplicate_ids.add(row_id)
                    else:
                        seen_ids.add(row_id)
                    if fdc_id_val is None:
                        empty_invalid_fdc_id += 1
                    if nutrient_id_val is None:
                        empty_invalid_nutrient_id += 1
                dup_id = len(duplicate_ids)
            report.food_nutrient_issues.extend([
                _fmt("Empty amount (among 4 nutrients we care about)", empty_amount),
                _fmt("Non-numeric amount (among 4 nutrients we care about)", non_numeric_amount),
                _fmt("Duplicate id (among valid-amount rows for those nutrients)", dup_id),
                _fmt("Empty or non-integer fdc_id (among valid-amount rows)", empty_invalid_fdc_id),
                _fmt("Empty or non-integer nutrient_id (among valid-amount rows)", empty_invalid_nutrient_id),
            ])
        except Exception as e:
            report.food_nutrient_issues.append(f"Error reading food_nutrient CSV: {e}")

    # Summary: count actual issues (exclude ": none" except for Foundation_food rows where none=problem)
    def _is_issue_line(s: str) -> bool:
        if s.startswith("File not found") or "Error" in s:
            return True
        if s.startswith("Foundation_food rows in scan"):
            return s.endswith(": none")  # zero rows is an issue
        if s.endswith(": none"):
            return False  # "none" for other checks = no issue
        return " found" in s
    def count_issues(lines: List[str]) -> int:
        return sum(1 for s in lines if _is_issue_line(s))

    n_food = count_issues(report.food_issues)
    n_food_nutrient = count_issues(report.food_nutrient_issues)
    n_nutrient = count_issues(report.nutrient_issues)
    if n_food or n_food_nutrient or n_nutrient:
        report.summary = (
            f"Cleaning checks found issues: "
            f"food={n_food}, food_nutrient={n_food_nutrient}, nutrient={n_nutrient}."
        )
        logger.info("Data cleaning report: %s", report.summary)
    else:
        report.summary = (
            "Cleaning checks completed. No issues found; "
            "data is acceptable for ingest (filtering and validation will still run at ingest time)."
        )
        logger.info("Data cleaning report: %s", report.summary)

    return report
