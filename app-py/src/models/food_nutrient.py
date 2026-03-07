"""
ORM model for the food_nutrients table.
"""

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, Numeric

from . import Base


class FoodNutrient(Base):
    __tablename__ = "food_nutrients"

    id = Column(BigInteger, primary_key=True)
    fdc_id = Column(BigInteger, ForeignKey("foods.fdc_id", ondelete="CASCADE"), nullable=False)
    nutrient_id = Column(Integer, ForeignKey("nutrients.id", ondelete="RESTRICT"), nullable=False)
    amount = Column(Numeric, nullable=False)
