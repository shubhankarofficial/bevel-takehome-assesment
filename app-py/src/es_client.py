"""Elasticsearch client. Uses central config for connection URL."""

from elasticsearch import AsyncElasticsearch

from .config import ELASTICSEARCH_URL

es_client = AsyncElasticsearch(
    hosts=[ELASTICSEARCH_URL],
    verify_certs=False,
    ssl_show_warn=False,
)


async def close_es_client() -> None:
    """Close the Elasticsearch client connection."""
    await es_client.close()
