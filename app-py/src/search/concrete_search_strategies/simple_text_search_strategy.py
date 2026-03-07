from typing import Any, Dict, List

from elasticsearch import AsyncElasticsearch

from ...config import FOOD_INDEX_NAME
from ..search_strategy import SearchStrategy


class SimpleTextSearchStrategy(SearchStrategy):
    """
    Basic search strategy that matches the query against the food name field
    using Elasticsearch's default BM25 scoring with optional fuzziness.
    """

    def __init__(self, es: AsyncElasticsearch, index_name: str = FOOD_INDEX_NAME) -> None:
        self._es = es
        self._index = index_name

    async def search(self, query: str, size: int = 20) -> List[Dict[str, Any]]:
        if not query:
            return []

        response = await self._es.search(
            index=self._index,
            size=size,
            query={
                "match": {
                    "name": {
                        "query": query,
                        "fuzziness": "AUTO",
                    }
                }
            },
        )
        hits = response.get("hits", {}).get("hits", [])
        return hits
