"""
Phrase-boosted, prefix, and fuzzy search on food name with secondary sort by name.keyword.

Requires the foods index mapping to have name.keyword (see FoodSearchIndex.ensure_index).
Query is sanitized so special characters (+, ;, %, etc.) are handled safely.
"""

from typing import Any, Dict, List

from elasticsearch import AsyncElasticsearch

from ...config import FOOD_INDEX_NAME
from ..search_strategy import SearchStrategy
from ..services.query_sanitizer import sanitize_search_query


class PhrasePrefixFuzzySearchStrategy(SearchStrategy):
    """
    Search strategy: phrase boost + prefix + fuzzy on name, sort by score then name.keyword.
    """

    def __init__(self, es: AsyncElasticsearch, index_name: str = FOOD_INDEX_NAME) -> None:
        self._es = es
        self._index = index_name

    async def search(self, query: str, size: int = 20) -> List[Dict[str, Any]]:
        query = sanitize_search_query(query or "")
        if not query:
            return []

        response = await self._es.search(
            index=self._index,
            size=size,
            query={
                "bool": {
                    "should": [
                        {"match_phrase": {"name": {"query": query, "boost": 3}}},
                        {"match_phrase_prefix": {"name": {"query": query, "boost": 2}}},
                        {
                            "match": {
                                "name": {
                                    "query": query,
                                    "fuzziness": "AUTO",
                                }
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            },
            sort=[
                {"_score": {"order": "desc"}},
                {"name.keyword": {"order": "asc"}},
            ],
        )
        hits = response.get("hits", {}).get("hits", [])
        return hits
