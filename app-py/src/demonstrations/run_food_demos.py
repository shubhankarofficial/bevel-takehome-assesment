"""
Run food and food_nutrient demos: show search before/after delete, add, update.

Requires: ingest done (index exists) and listener running (e.g. run_ingest or run_food_index_listener).

Usage:
  cd app-py && source src/venv/bin/activate
  python -m src.demonstrations.run_food_demos                    # run all six
  python -m src.demonstrations.run_food_demos --delete --add --update   # food demos only
  python -m src.demonstrations.run_food_demos --add-fn --delete-fn --update-fn  # food_nutrient demos only
"""

import argparse
import asyncio
import logging
import os
import sys

# Ensure project root is on path when run as module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from dotenv import load_dotenv

load_dotenv()

from src.db import close_pool, get_pool
from src.demonstrations.food_demos import (
    demonstrate_add_food,
    demonstrate_delete_food,
    demonstrate_update_food,
)
from src.demonstrations.food_nutrient_demos import (
    demonstrate_add_food_nutrient,
    demonstrate_delete_food_nutrient,
    demonstrate_update_food_nutrient,
)
from src.es_client import close_es_client, es_client
from src.repositories.food_nutrient_repository import FoodNutrientRepository
from src.repositories.food_repository import FoodRepository
from src.search.phrase_prefix_fuzzy_search_strategy import PhrasePrefixFuzzySearchStrategy
from src.services.food_nutrient_service import FoodNutrientService
from src.services.food_service import FoodService
from src.services.search_service import SearchService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run food index listener demos")
    parser.add_argument("--delete", action="store_true", help="Run delete-food demo")
    parser.add_argument("--add", action="store_true", help="Run add-food demo")
    parser.add_argument("--update", action="store_true", help="Run update-food demo")
    parser.add_argument("--add-fn", action="store_true", help="Run add-food_nutrient demo")
    parser.add_argument("--delete-fn", action="store_true", help="Run delete-food_nutrient demo")
    parser.add_argument("--update-fn", action="store_true", help="Run update-food_nutrient demo")
    args = parser.parse_args()

    any_selected = args.delete or args.add or args.update or args.add_fn or args.delete_fn or args.update_fn
    run_all = not any_selected

    pool = await get_pool()
    food_repo = FoodRepository(pool)
    food_nutrient_repo = FoodNutrientRepository(pool)
    food_service = FoodService(food_repo)
    food_nutrient_service = FoodNutrientService(food_nutrient_repo, food_repo)
    strategy = PhrasePrefixFuzzySearchStrategy(es_client)
    search_service = SearchService(strategy)

    try:
        if run_all or args.delete:
            await demonstrate_delete_food(search_service, food_service, es_client)
        if run_all or args.add:
            await demonstrate_add_food(search_service, food_service, es_client)
        if run_all or args.update:
            await demonstrate_update_food(search_service, food_service, es_client)
        if run_all or args.add_fn:
            await demonstrate_add_food_nutrient(search_service, food_nutrient_service, es_client)
        if run_all or args.delete_fn:
            await demonstrate_delete_food_nutrient(search_service, food_nutrient_service, es_client)
        if run_all or args.update_fn:
            await demonstrate_update_food_nutrient(search_service, food_nutrient_service, es_client)
    finally:
        await close_pool()
        await close_es_client()


if __name__ == "__main__":
    asyncio.run(main())
