from abc import ABC, abstractmethod
from typing import Any, Dict, List


class SearchStrategy(ABC):
    """
    Strategy interface for search behavior.

    Different implementations can adjust how queries are built, how results are ranked,
    or which fields are searched.
    """

    @abstractmethod
    async def search(self, query: str, size: int = 20) -> List[Dict[str, Any]]:
        """
        Execute a search and return a list of hits as dictionaries
        (to be converted into API response objects by a higher layer).
        """
        raise NotImplementedError


