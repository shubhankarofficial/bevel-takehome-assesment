"""
SQLAlchemy declarative base and table metadata.

Import models from here: from src.models import Base, Nutrient, Food, FoodNutrient
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for all ORM models. Table definitions live in nutrient, food, food_nutrient modules."""

    pass


from .food import Food
from .food_nutrient import FoodNutrient
from .nutrient import Nutrient

__all__ = ["Base", "Nutrient", "Food", "FoodNutrient"]
