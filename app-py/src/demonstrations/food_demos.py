"""
Food demos: show search results before and after add/update/delete to prove listener syncs ES.

Ensure index exists and listener is running before running these (e.g. run_ingest).
"""

import asyncio
import logging
from typing import List

# Seconds to wait after a DB change so the NOTIFY listener can update ES before we search
LISTENER_SYNC_WAIT_SEC = 2.0

from elasticsearch import AsyncElasticsearch

from ..config import FOOD_INDEX_NAME
from ..domain import Food
from ..services.food_service import FoodService
from ..services.search_service import SearchService

logger = logging.getLogger(__name__)

# Demo data (Foods)
DELETE_FOOD_FDC_ID = 333374
DELETE_FOOD_QUERY = "Fish, haddock, raw"

ADD_FOOD_FDC_ID = 333374
ADD_FOOD_DATA_TYPE = "foundation_food"
ADD_FOOD_DESCRIPTION = "Fish, haddock, raw"
ADD_FOOD_QUERY = "Fish, haddock, raw"

UPDATE_FOOD_FDC_ID = 2727566
UPDATE_FOOD_OLD_NAME = "Chicken, drumstick, meat and skin, raw"
UPDATE_FOOD_NEW_NAME = "chicken balooza"
UPDATE_FOOD_QUERY = "chicken balooza"


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


async def demonstrate_delete_food(
    search_service: SearchService,
    food_service: FoodService,
    es: AsyncElasticsearch,
) -> None:
    """
    Demo: delete a food. Show search results for 'Fish, haddock, raw', delete fdc_id 333374, show again.
    """
    await _ensure_ready(es)
    query = DELETE_FOOD_QUERY
    fdc_id = DELETE_FOOD_FDC_ID

    print(f"\n--- Demonstrate DELETE food (fdc_id={fdc_id}) ---")
    print(f"Query: {query!r}\n")

    print("BEFORE delete:")
    foods_before = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods_before))
    print()

    deleted = await food_service.delete_food(fdc_id)
    if not deleted:
        print(f"  (food fdc_id={fdc_id} was not in DB; nothing to delete)\n")
    else:
        print(f"  Deleted food fdc_id={fdc_id} from foods table. Listener will remove from ES.\n")
    await _wait_for_listener()

    print("AFTER delete (same query):")
    foods_after = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods_after))
    print("---\n")


async def demonstrate_add_food(
    search_service: SearchService,
    food_service: FoodService,
    es: AsyncElasticsearch,
) -> None:
    """
    Demo: add a food. If fdc_id 333374 exists, delete it. Show results for 'Fish, haddock, raw',
    then add the food, then show again so it appears (listener indexes it).
    """
    await _ensure_ready(es)
    query = ADD_FOOD_QUERY
    fdc_id = ADD_FOOD_FDC_ID

    print(f"\n--- Demonstrate ADD food (fdc_id={fdc_id}) ---")
    print(f"Query: {query!r}\n")

    # If it exists, delete so we can show add from scratch
    await food_service.delete_food(fdc_id)
    await _wait_for_listener()

    print("BEFORE add (after ensuring food not in DB):")
    foods_before = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods_before))
    print()

    try:
        await food_service.add_food(
            fdc_id=fdc_id,
            data_type=ADD_FOOD_DATA_TYPE,
            description=ADD_FOOD_DESCRIPTION,
        )
        print(f"  Added food fdc_id={fdc_id} ({ADD_FOOD_DESCRIPTION}). Listener will index it.\n")
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"  Food already exists; update or delete it first.\n")
        raise
    await _wait_for_listener()

    print("AFTER add (same query):")
    foods_after = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods_after))
    print("---\n")


async def demonstrate_update_food(
    search_service: SearchService,
    food_service: FoodService,
    es: AsyncElasticsearch,
) -> None:
    """
    Demo: update a food name to show exact match ranks higher.
    Show results for 'chicken balooza' (top is direct match). Then change fdc_id 2727566
    (Chicken, drumstick, meat and skin, raw) to name 'chicken balooza', show again — it comes to top.
    """
    await _ensure_ready(es)
    query = UPDATE_FOOD_QUERY
    fdc_id = UPDATE_FOOD_FDC_ID

    print(f"\n--- Demonstrate UPDATE food (fdc_id={fdc_id} -> name={UPDATE_FOOD_NEW_NAME!r}) ---")
    print(f"Query: {query!r}\n")

    print("BEFORE update:")
    foods_before = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods_before))
    print()
    # Before update: no food is named "chicken balooza", so the top result is the best fuzzy match, not a direct match.
    print("  (Top result is direct match only when a food has name 'chicken balooza'; here there is no such food yet.)\n")

    updated = await food_service.update_food(fdc_id, description=UPDATE_FOOD_NEW_NAME)
    if not updated:
        print(f"  (food fdc_id={fdc_id} not found in DB)\n")
    else:
        print(f"  Updated fdc_id={fdc_id} name to {UPDATE_FOOD_NEW_NAME!r}. Listener will update ES.\n")
    await _wait_for_listener()

    print("AFTER update (same query):")
    foods_after = await search_service.search_foods(query=query, size=10)
    print(_format_foods(foods_after))
    print("  (Updated food now exact match and should appear at top.)")
    print("---\n")
