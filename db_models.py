from sqlalchemy import Column, Float, Boolean, String, DateTime
from database import Base
import uuid
from enum import Enum


class ReviewStatus(str, Enum):
    APPROVED = "APPROVED"
    PENDING_REVIEW = "PENDING_REVIEW"
    REJECTED = "REJECTED"

class FuelOrder(Base):
    __tablename__ = 'fuel_orders'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    stated_total = Column(Float, nullable=False)
    calculated_total = Column(Float, nullable=True)
    valid = Column(Boolean, nullable=False)
    error = Column(String, nullable=True)
    review_status = Column(String, nullable=False, default=ReviewStatus.PENDING_REVIEW)
    reviewer = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(String, nullable=True)