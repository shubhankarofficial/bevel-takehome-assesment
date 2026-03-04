from typing import Any, Dict, List

from ..nutrients import NutrientAmount
from .search_strategy import SearchStrategy


class SearchService:
    """
    High-level search service used by the API layer.

    Delegates search behavior to a SearchStrategy and converts raw hits into
    the response shape expected by the API.
    """

    def __init__(self, strategy: SearchStrategy) -> None:
        self._strategy = strategy

    async def search_foods(self, query: str, size: int = 20) -> List[Dict[str, Any]]:
        """
        Execute a search using the configured strategy and map hits into a list
        of Food objects (as plain dicts).

        The exact document structure will be solidified when indexing is implemented.
        """
        hits = await self._strategy.search(query=query, size=size)
        foods: List[Dict[str, Any]] = []

        for hit in hits:
            source = hit.get("_source", {})
            # Expected shape of source (to be enforced at indexing time):
            # {
            #   "name": str,
            #   "nutrients": [{ "type": "calories" | "protein" | "carbs" | "fat", "amount": number }, ...]
            # }
            name = source.get("name", "")
            nutrients_raw = source.get("nutrients", [])
            nutrients: List[NutrientAmount] = []
            for n in nutrients_raw:
                n_type = n.get("type")
                amount = n.get("amount")
                if n_type is None or amount is None:
                    continue
                nutrients.append(
                    NutrientAmount(
                        type=n_type,  # type: ignore[arg-type]
                        amount=float(amount),
                    )
                )

            foods.append(
                {
                    "name": name,
                    "nutrients": [
                        {"type": na.type.value, "amount": na.amount} for na in nutrients
                    ],
                }
            )

        return foods

