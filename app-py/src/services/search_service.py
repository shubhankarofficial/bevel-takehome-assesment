"""
Search use-case: orchestrate search and shape response for the API.
"""

from typing import List

from ..domain import Food, FoodNutrient, NutrientAmount
from ..search.search_strategy import SearchStrategy


class SearchService:
    """
    High-level search service used by the API layer.

    Delegates search behavior to a SearchStrategy and returns domain Food list.
    API layer converts to FoodSearchResponse (Pydantic) for the endpoint.
    """

    def __init__(self, strategy: SearchStrategy) -> None:
        self._strategy = strategy

    async def search_foods(self, query: str, size: int = 20) -> List[Food]:
        """
        Execute search and return a list of domain Food objects.
        """
        hits = await self._strategy.search(query=query, size=size)
        foods: List[Food] = []

        for hit in hits:
            source = hit.get("_source", {})
            name = source.get("name", "")
            nutrients_raw = source.get("nutrients", [])
            nutrients: List[NutrientAmount] = []
            for n in nutrients_raw:
                n_type = n.get("type")
                amount = n.get("amount")
                if n_type is None or amount is None:
                    continue
                try:
                    nutrient_type = FoodNutrient(n_type)
                except ValueError:
                    continue
                nutrients.append(NutrientAmount(type=nutrient_type, amount=float(amount)))
            foods.append(Food(name=name, nutrients=nutrients))

        return foods
