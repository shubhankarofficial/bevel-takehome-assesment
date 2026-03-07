"""
ORM model for the nutrients table.
"""

from sqlalchemy import Column, Integer, Text

from . import Base


class Nutrient(Base):
    __tablename__ = "nutrients"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=True)
    unit_name = Column(Text, nullable=True)
