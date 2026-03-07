import logging
from typing import Any, Dict, Iterable, List

from elasticsearch import AsyncElasticsearch

from ..config import FOOD_INDEX_NAME

logger = logging.getLogger(__name__)


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
        """
        exists = await self._es.indices.exists(index=self._index)
        if exists:
            logger.info("FoodSearchIndex: index %s already exists, skipping create", self._index)
            return

        logger.info(
            "FoodSearchIndex: index %s does not exist (HEAD returned 404), creating with mappings",
            self._index,
        )
        await self._es.indices.create(
            index=self._index,
            mappings={
                "properties": {
                    "fdc_id": {"type": "long"},
                    "name": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "nutrients": {
                        "properties": {
                            "type": {"type": "keyword"},
                            "amount": {"type": "float"},
                        }
                    },
                }
            },
        )
        logger.info("FoodSearchIndex: created index %s", self._index)

    async def index_food(self, doc_id: int, document: Dict[str, Any]) -> None:
        """
        Index or update a single food document.
        """
        await self._es.index(index=self._index, id=doc_id, document=document)
        logger.debug("FoodSearchIndex: indexed fdc_id=%s", doc_id)

    async def bulk_index_foods(
        self, documents: Iterable[Dict[str, Any]]
    ) -> None:
        """
        Bulk index many food documents.

        Each document must include an 'fdc_id' field which is used as the
        Elasticsearch document _id. Documents without fdc_id are skipped.
        """
        ops: List[Dict[str, Any]] = []
        for doc in documents:
            doc_id = doc.get("fdc_id")
            if doc_id is None:
                # Skip documents without an id; caller logs at a higher level if needed.
                continue
            ops.append({"index": {"_index": self._index, "_id": doc_id}})
            ops.append(doc)

        if not ops:
            return

        await self._es.bulk(operations=ops)
        num_docs = len(ops) // 2
        logger.info("FoodSearchIndex: bulk_index_foods indexed %s documents", num_docs)

    async def delete_food(self, doc_id: int) -> None:
        """
        Delete a food document from the index if it exists.
        """
        await self._es.delete(index=self._index, id=doc_id, ignore=[404])
        logger.debug("FoodSearchIndex: delete_food fdc_id=%s", doc_id)

    async def delete_index(self) -> None:
        """
        Delete the entire index if it exists. Use before a full reindex to avoid stale documents.
        """
        exists = await self._es.indices.exists(index=self._index)
        if exists:
            await self._es.indices.delete(index=self._index)
            logger.info("FoodSearchIndex: deleted index %s", self._index)
        else:
            logger.info("FoodSearchIndex: index %s does not exist, nothing to delete", self._index)

