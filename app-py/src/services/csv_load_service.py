"""
Service that parses USDA CSVs and loads data into Postgres via repositories.

Load order: nutrients (FK target) → foods (foundation_food only) → food_nutrients
(only rows for those foods and the 4 nutrients we expose). Uses stdlib csv.

Memory: We do not load entire CSVs into memory. We stream row-by-row and insert
in batches of INGEST_DB_BATCH_SIZE; only one batch is held at a time. The only
larger in-memory structure is the set of foundation fdc_ids (used to filter
food_nutrient rows). For very large food CSVs (e.g. tens of millions of
foundation foods), that set can be scaled by a two-pass or DB-backed check later.
"""

import csv
import logging
from datetime import date
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

from ..config import (
    FOOD_CSV_PATH,
    FOOD_NUTRIENT_CSV_PATH,
    INGEST_DB_BATCH_SIZE,
    NUTRIENT_CSV_PATH,
    USDA_NUTRIENT_MAPPING,
)
from ..repositories.food_nutrient_repository import FoodNutrientRepository
from ..repositories.food_repository import FoodRepository
from ..repositories.nutrient_repository import NutrientRepository

logger = logging.getLogger(__name__)

NUTRIENT_IDS = set(USDA_NUTRIENT_MAPPING.keys())


def _parse_int(s: str) -> Optional[int]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_float(s: str) -> Optional[float]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(s: str) -> Optional[date]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


class CsvLoadService:
    """
    Parses nutrient, food, and food_nutrient CSVs and loads them into the DB
    using the provided repositories. Only foundation_food rows and the 4
    nutrients we expose are loaded.
    """

    def __init__(
        self,
        nutrient_repo: NutrientRepository,
        food_repo: FoodRepository,
        food_nutrient_repo: FoodNutrientRepository,
        *,  # keyword-only args below: must pass by name, e.g. batch_size=500
        nutrient_path: Optional[Path] = None,
        food_path: Optional[Path] = None,
        food_nutrient_path: Optional[Path] = None,
        batch_size: int = INGEST_DB_BATCH_SIZE,
    ) -> None:
        self._nutrient_repo = nutrient_repo
        self._food_repo = food_repo
        self._food_nutrient_repo = food_nutrient_repo
        self._nutrient_path = nutrient_path or NUTRIENT_CSV_PATH
        self._food_path = food_path or FOOD_CSV_PATH
        self._food_nutrient_path = food_nutrient_path or FOOD_NUTRIENT_CSV_PATH
        self._batch_size = batch_size

    async def load_all(self) -> None:
        """
        Load nutrients, then foods (foundation_food only), then food_nutrients.
        Logs inserted counts and skips invalid rows.
        """
        await self._load_nutrients()
        foundation_fdc_ids = await self._load_foods()
        await self._load_food_nutrients(foundation_fdc_ids)

    async def _load_nutrients(self) -> None:
        """Parse nutrient.csv and insert only the 4 nutrients we expose."""
        if not self._nutrient_path.exists():
            logger.warning("Nutrient CSV not found: %s", self._nutrient_path)
            return
        rows: List[Tuple[int, Optional[str], Optional[str]]] = []
        with open(self._nutrient_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                nid = _parse_int(row.get("id") or "")
                if nid is None or nid not in NUTRIENT_IDS:
                    continue
                name = (row.get("name") or "").strip() or None
                unit_name = (row.get("unit_name") or "").strip() or None
                rows.append((nid, name, unit_name))
        if rows:
            inserted = await self._nutrient_repo.bulk_insert(rows)
            logger.info("CsvLoadService: nutrients inserted=%s", inserted)
        else:
            logger.warning("CsvLoadService: no nutrient rows to insert (filtered to 4 IDs)")

    async def _load_foods(self) -> Set[int]:
        """
        Parse food.csv; keep only foundation_food rows. Strip description,
        normalize publication_date. Insert in batches. Return set of fdc_id for use in food_nutrients.
        """
        foundation_fdc_ids: Set[int] = set()
        if not self._food_path.exists():
            logger.warning("Food CSV not found: %s", self._food_path)
            return foundation_fdc_ids
        batch: List[Tuple[int, str, str, Optional[date]]] = []
        total_inserted = 0
        skipped = 0
        with open(self._food_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row.get("data_type") or "").strip() != "foundation_food":
                    skipped += 1
                    continue
                fdc_id = _parse_int(row.get("fdc_id") or "")
                if fdc_id is None:
                    skipped += 1
                    continue
                description = (row.get("description") or "").strip()
                pub_date = _parse_date(row.get("publication_date") or "")
                batch.append((fdc_id, "foundation_food", description, pub_date))
                foundation_fdc_ids.add(fdc_id)
                if len(batch) >= self._batch_size:
                    total_inserted += await self._food_repo.bulk_insert(batch)
                    batch = []
        if batch:
            total_inserted += await self._food_repo.bulk_insert(batch)
        logger.info(
            "CsvLoadService: foods inserted=%s, skipped=%s, foundation_fdc_ids=%s",
            total_inserted,
            skipped,
            len(foundation_fdc_ids),
        )
        return foundation_fdc_ids

    async def _load_food_nutrients(self, foundation_fdc_ids: Set[int]) -> None:
        """
        Parse food_nutrient.csv; keep rows for foundation_food fdc_ids and the 4 nutrients.
        Require valid numeric amount. Insert in batches.
        """
        if not self._food_nutrient_path.exists():
            logger.warning("Food nutrient CSV not found: %s", self._food_nutrient_path)
            return
        if not foundation_fdc_ids:
            logger.warning("CsvLoadService: no foundation fdc_ids; skipping food_nutrients")
            return
        batch: List[Tuple[int, int, int, float]] = []
        total_inserted = 0
        skipped = 0
        with open(self._food_nutrient_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                nutrient_id = _parse_int(row.get("nutrient_id") or "")
                if nutrient_id is None or nutrient_id not in NUTRIENT_IDS:
                    continue
                amount_val = _parse_float(row.get("amount") or "")
                if amount_val is None:
                    skipped += 1
                    continue
                row_id = _parse_int(row.get("id") or "")
                fdc_id = _parse_int(row.get("fdc_id") or "")
                if row_id is None or fdc_id is None or fdc_id not in foundation_fdc_ids:
                    skipped += 1
                    continue
                batch.append((row_id, fdc_id, nutrient_id, amount_val))
                if len(batch) >= self._batch_size:
                    total_inserted += await self._food_nutrient_repo.bulk_insert(batch)
                    batch = []
        if batch:
            total_inserted += await self._food_nutrient_repo.bulk_insert(batch)
        logger.info(
            "CsvLoadService: food_nutrients inserted=%s, skipped=%s",
            total_inserted,
            skipped,
        )
