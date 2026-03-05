"""
Domain type: Food.

Matches the API contract (name, nutrients). Used by services and converted to
response models at the API layer.
"""

from dataclasses import dataclass
from typing import List

from .nutrients import NutrientAmount


@dataclass
class Food:
    """A food with display name and list of nutrient amounts."""

    name: str
    nutrients: List[NutrientAmount]
