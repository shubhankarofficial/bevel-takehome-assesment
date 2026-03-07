"""
Concrete search strategy implementations.
"""

from .phrase_prefix_fuzzy_search_strategy import PhrasePrefixFuzzySearchStrategy
from .simple_text_search_strategy import SimpleTextSearchStrategy

__all__ = ["PhrasePrefixFuzzySearchStrategy", "SimpleTextSearchStrategy"]
