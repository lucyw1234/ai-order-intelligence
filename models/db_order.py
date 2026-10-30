from sqlalchemy import Column, String, Numeric, Boolean, DateTime, func
from config.database import Base


class FuelOrder(Base):
    """
    n8n analogy: This is like designing your Google Sheet columns
    before adding data - defines exactly how orders will be stored
    """
    __tablename__ = 'fuel_orders'

    # Like Google Sheets' hidden row ID, but more secure (UUID)
    id = Column(String(36), primary_key=True)

    # Your business order ID (must be unique like a Google Forms response ID)
    order_id = Column(String(36), unique=True, nullable=False)

    # Quantities and prices stored as DECIMAL to avoid float errors
    # Like using Google Sheets' 'Number' format instead of 'Plain text'
    quantity = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    calculated_total = Column(Numeric(10, 2), nullable=False)

    # Critical: storing both valid AND invalid orders for review
    is_valid = Column(Boolean, nullable=False)
    error_message = Column(String(255), nullable=True)

    # Timestamp automatically set when created (like Google Sheets' =NOW())
    stated_total = Column(Numeric(10, 2), nullable=False)
    review_status = Column(String(20), default='pending', nullable=False)