"""
ORM model for the foods table.
"""

from sqlalchemy import BigInteger, Column, Date, Text

from . import Base


class Food(Base):
    __tablename__ = "foods"

    fdc_id = Column(BigInteger, primary_key=True)
    data_type = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    publication_date = Column(Date, nullable=True)
