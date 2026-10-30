from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class OrderRequest(BaseModel):
    quantity: float
    unit_price: float
    stated_total: float

class OrderResponse(BaseModel):
    id: Optional[str] = None
    valid: bool
    calculated_total: Optional[float]
    error: Optional[str]

class OrderListItem(BaseModel):
    id: str
    quantity: float
    unit_price: float
    stated_total: float
    calculated_total: Optional[float]
    valid: bool
    error: Optional[str]
    review_status: str
    reviewer: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None