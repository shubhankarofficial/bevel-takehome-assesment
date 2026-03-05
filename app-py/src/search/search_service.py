"""
Re-export SearchService from services for backward compatibility.

API should import from src.services; search strategy and index stay in this package.
"""

from ..services.search_service import SearchService

__all__ = ["SearchService"]
