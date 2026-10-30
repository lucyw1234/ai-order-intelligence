from sqlalchemy import Column, String, Numeric, Boolean, DateTime, func
from config.database import Base  # Correct absolute import path


class FuelOrder(Base):
    """
    n8n analogy: Database table design (like Google Sheets columns)
    """
    __tablename__ = 'fuel_orders'

    id = Column(String(36), primary_key=True)
    order_id = Column(String(36), unique=True, nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    calculated_total = Column(Numeric(10, 2), nullable=False)
    stated_total = Column(Numeric(10, 2), nullable=False)
    is_valid = Column(Boolean, nullable=False)
    error_message = Column(String(255), nullable=True)
    validated_at = Column(DateTime(timezone=True), server_default=func.now())
    review_status = Column(String(20), default='pending', nullable=False)