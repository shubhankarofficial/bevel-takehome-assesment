from typing import Any, Dict, Iterable, List

from elasticsearch import AsyncElasticsearch

from ..config import FOOD_INDEX_NAME


class FoodSearchIndex:
    """
    Facade over the Elasticsearch index used for foods.

    This class hides index name, mappings, and query details from the rest of the codebase.
    """

    def __init__(self, es: AsyncElasticsearch, index_name: str = FOOD_INDEX_NAME) -> None:
        self._es = es
        self._index = index_name

    async def ensure_index(self) -> None:
        """
        Create the index with appropriate mappings if it does not exist.
        Implementation will be filled in later.
        """
        # Placeholder skeleton; to be implemented in a later step.
        pass

    async def index_food(self, doc_id: int, document: Dict[str, Any]) -> None:
        """
        Index or update a single food document.
        """
        await self._es.index(index=self._index, id=doc_id, document=document)

    async def bulk_index_foods(
        self, documents: Iterable[Dict[str, Any]]
    ) -> None:
        """
        Bulk index many food documents.
        The expected shape of each document will be defined later.
        """
        # Implementation will be filled in using Elasticsearch bulk API.
        pass

    async def delete_food(self, doc_id: int) -> None:
        """
        Delete a food document from the index if it exists.
        """
        await self._es.delete(index=self._index, id=doc_id, ignore=[404])

