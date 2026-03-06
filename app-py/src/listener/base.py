"""
Base abstraction for a listener that subscribes to a Postgres NOTIFY channel.

Implementations bind to a specific channel and define how to handle payloads.
Multiple listener types can coexist (e.g. food_index_events, other channels later).
"""

from abc import ABC, abstractmethod
from typing import Any, Awaitable


class NotifyListener(ABC):
    """
    Interface for a subscriber that LISTENs to a single NOTIFY channel and runs until stopped.
    """

    @property
    @abstractmethod
    def channel(self) -> str:
        """Postgres NOTIFY channel name this listener subscribes to."""
        ...

    @abstractmethod
    def run(self) -> Awaitable[None]:
        """Start listening; blocks until stop() is called."""
        ...

    def stop(self) -> None:
        """Signal the listener to shut down (idempotent)."""
        ...
