"""
Food_nutrient demos: show search results before/after add/update/delete to prove listener syncs ES.

Ensure index exists and listener is running (e.g. run_ingest).
"""

import asyncio
import logging
from typing import List

# Seconds to wait after a DB change so the NOTIFY listener can update ES before we search
LISTENER_SYNC_WAIT_SEC = 2.0

from elasticsearch import AsyncElasticsearch

from ..config import FOOD_INDEX_NAME
from ..domain import Food
from ..services.food_nutrient_service import FoodNutrientService
from ..services.search_service import SearchService

logger = logging.getLogger(__name__)

# Demo 1: Add food_nutrient (carbs to tuna)
ADD_FN_FDC_ID = 334194
ADD_FN_QUERY = "Fish, tuna, light, canned in water, drained solids"
ADD_FN_NUTRIENT_ID = 2039  # carbs (mapping in config)
ADD_FN_AMOUNT = 20.0

# Demo 2: Delete one food_nutrient row (tuna) — delete first nutrient row, show before/after
DELETE_FN_FDC_ID = 334194
DELETE_FN_QUERY = "Fish, tuna, light, canned in water, drained solids"
DELETE_FN_ROW_ONE = 2268170  # one nutrient row (e.g. protein) to delete

# Demo 3: Update food_nutrient (egg white protein)
UPDATE_FN_FDC_ID = 747997
UPDATE_FN_QUERY = "Eggs, Grade A, Large, egg white"
UPDATE_FN_ROW_ID = 8526265  # protein row
UPDATE_FN_NEW_AMOUNT = 10.9


async def _index_exists(es: AsyncElasticsearch, index_name: str) -> bool:
    return await es.indices.exists(index=index_name)


def _format_foods(foods: List[Food]) -> str:
    if not foods:
        return "  (no results)"
    lines = []
    for i, f in enumerate(foods, 1):
        nut_str = ", ".join(f"{n.type.value}: {n.amount}" for n in f.nutrients)
        lines.append(f"  {i}. {f.name} | nutrients: [{nut_str}]")
    return "\n".join(lines)


async def _ensure_ready(es: AsyncElasticsearch) -> None:
    if not await _index_exists(es, FOOD_INDEX_NAME):
        raise RuntimeError(
            "Index does not exist. Run ingest first: python -m src.run_ingest"
        )
    logger.info("Index exists. Ensure listener is running (run_ingest or run_food_index_listener).")


async def _wait_for_listener() -> None:
    """Wait for the NOTIFY listener (separate process) to sync ES after a DB change."""
    print(f"  Waiting {LISTENER_SYNC_WAIT_SEC}s for listener to sync ES...")
    await asyncio.sleep(LISTENER_SYNC_WAIT_SEC)


async def demonstrate_add_food_nutrient(
    search_service: SearchService,
    food_nutrient_service: FoodNutrientService,
    es: AsyncElasticsearch,
) -> None:
    """
    Demo: add a food_nutrient (carbs) to fdc_id 334194 (Fish, tuna, light...).
    Show results (already has protein, fat, calories), add carbs (nutrient_id 2039), show again.
    """
    await _ensure_ready(es)
    query = ADD_FN_QUERY
    fdc_id = ADD_FN_FDC_ID

    print(f"\n--- Demonstrate ADD food_nutrient (fdc_id={fdc_id}, nutrient_id={ADD_FN_NUTRIENT_ID} carbs, amount={ADD_FN_AMOUNT}) ---")
    print(f"Query: {query!r}\n")

    print("BEFORE add (food already has protein, fat, calories):")
    foods_before = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods_before))
    print()

    try:
        row_id = await food_nutrient_service.add_food_nutrient(
            fdc_id=fdc_id,
            nutrient_id=ADD_FN_NUTRIENT_ID,
            amount=ADD_FN_AMOUNT,
        )
        print(f"  Added food_nutrient row id={row_id} (fdc_id={fdc_id}, carbs={ADD_FN_AMOUNT}). Listener will reindex.\n")
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"  (Food already has this nutrient; skip or delete existing row first.)\n")
        raise
    await _wait_for_listener()

    print("AFTER add (same query; carbs should appear):")
    foods_after = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods_after))
    print("---\n")


async def demonstrate_delete_food_nutrient(
    search_service: SearchService,
    food_nutrient_service: FoodNutrientService,
    es: AsyncElasticsearch,
) -> None:
    """
    Demo: delete one food_nutrient row for fdc_id 334194 (tuna). Show before, delete one row, show after.
    """
    await _ensure_ready(es)
    query = DELETE_FN_QUERY

    print(f"\n--- Demonstrate DELETE food_nutrient (fdc_id={DELETE_FN_FDC_ID}) ---")
    print(f"Query: {query!r}\n")

    print("BEFORE delete:")
    foods = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods))
    print()

    deleted = await food_nutrient_service.delete_food_nutrient(DELETE_FN_ROW_ONE)
    print(f"  Deleted row id={DELETE_FN_ROW_ONE}. Listener will reindex.\n")
    await _wait_for_listener()
    print("AFTER delete (same query):")
    foods = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods))
    print("---\n")


async def demonstrate_update_food_nutrient(
    search_service: SearchService,
    food_nutrient_service: FoodNutrientService,
    es: AsyncElasticsearch,
) -> None:
    """
    Demo: update food_nutrient row 8526265 (protein for egg white) from 10.7 to 10.9.
    Show results for 'Eggs, Grade A, Large, egg white', update amount, show again.
    """
    await _ensure_ready(es)
    query = UPDATE_FN_QUERY

    print(f"\n--- Demonstrate UPDATE food_nutrient (row id={UPDATE_FN_ROW_ID} -> amount={UPDATE_FN_NEW_AMOUNT}) ---")
    print(f"Query: {query!r}\n")

    print("BEFORE update (protein shown as 10.7):")
    foods_before = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods_before))
    print()

    updated = await food_nutrient_service.update_food_nutrient(
        UPDATE_FN_ROW_ID,
        amount=UPDATE_FN_NEW_AMOUNT,
    )
    if not updated:
        print(f"  (Row id={UPDATE_FN_ROW_ID} not found.)\n")
    else:
        print(f"  Updated food_nutrient row id={UPDATE_FN_ROW_ID} to amount={UPDATE_FN_NEW_AMOUNT}. Listener will reindex.\n")
    await _wait_for_listener()

    print("AFTER update (same query; protein should show 10.9):")
    foods_after = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods_after))
    print("---\n")
