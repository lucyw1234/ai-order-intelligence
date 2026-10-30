from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Depends
from sqlalchemy import select, update
from typing import List, Optional
from datetime import datetime, UTC
from pydantic import BaseModel
from models import OrderRequest, OrderResponse, OrderListItem
from services.order_validation import validate_order
from database import init_db, AsyncSessionLocal
from db_models import FuelOrder, ReviewStatus
import uuid
import os

# Reviewer API key configuration
REVIEWER_API_KEY = os.getenv("REVIEWER_API_KEY", "reviewer_secret_key")

async def verify_reviewer_api_key(x_reviewer_key: str = Header(...)):
    if x_reviewer_key != REVIEWER_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid reviewer API key")
    return x_reviewer_key

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/validate-order", response_model=OrderResponse)
async def validate_order_endpoint(request: OrderRequest):
    response = validate_order(request.quantity, request.unit_price, request.stated_total)

    # Generate UUID before database operation
    order_id = str(uuid.uuid4())
    review_status = ReviewStatus.APPROVED if response.valid else ReviewStatus.PENDING_REVIEW

    async with AsyncSessionLocal() as session:
        async with session.begin():
            order = FuelOrder(
                id=order_id,
                quantity=request.quantity,
                unit_price=request.unit_price,
                stated_total=request.stated_total,
                calculated_total=response.calculated_total,
                valid=response.valid,
                error=response.error,
                review_status=review_status
            )
            session.add(order)
        # Commit happens automatically when exiting the begin block

    return OrderResponse(
        id=order_id,
        valid=response.valid,
        calculated_total=response.calculated_total,
        error=response.error
    )

@app.get("/orders", response_model=List[OrderListItem])
async def get_orders():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(FuelOrder))
        orders = result.scalars().all()

        return [
            OrderListItem(
                id=order.id,
                quantity=order.quantity,
                unit_price=order.unit_price,
                stated_total=order.stated_total,
                calculated_total=order.calculated_total,
                valid=order.valid,
                error=order.error,
                review_status=order.review_status,
                reviewer=order.reviewer,
                reviewed_at=order.reviewed_at,
                review_notes=order.review_notes
            ) for order in orders
        ]

@app.get("/orders/pending-review", response_model=List[OrderListItem])
async def get_pending_review_orders():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(FuelOrder).where(FuelOrder.review_status == ReviewStatus.PENDING_REVIEW)
        )
        orders = result.scalars().all()

        return [
            OrderListItem(
                id=order.id,
                quantity=order.quantity,
                unit_price=order.unit_price,
                stated_total=order.stated_total,
                calculated_total=order.calculated_total,
                valid=order.valid,
                error=order.error,
                review_status=order.review_status,
                reviewer=order.reviewer,
                reviewed_at=order.reviewed_at,
                review_notes=order.review_notes
            ) for order in orders
        ]

class ReviewDecision(BaseModel):
    decision: str  # "APPROVE" or "REJECT"
    notes: Optional[str] = None

@app.patch("/orders/{order_id}/review")
async def review_order(
    order_id: str,
    decision: ReviewDecision,
    api_key: str = Depends(verify_reviewer_api_key)
):
    # Validate decision
    if decision.decision not in ["APPROVE", "REJECT"]:
        raise HTTPException(400, "Invalid decision")

    async with AsyncSessionLocal() as session:
        async with session.begin():
            # Fetch order
            order = await session.get(FuelOrder, order_id)
            if not order:
                raise HTTPException(404, "Order not found")

            # Check if order is in PENDING_REVIEW state
            if order.review_status != ReviewStatus.PENDING_REVIEW:
                raise HTTPException(400, "Order is not pending review")

            # Update based on decision
            if decision.decision == "APPROVE":
                order.review_status = ReviewStatus.APPROVED
            else:  # REJECT
                order.review_status = ReviewStatus.REJECTED

            # Record review details
            reviewer_name = os.getenv("REVIEWER_NAME")
            if not reviewer_name:
                raise HTTPException(status_code=500, detail="Reviewer configuration incomplete")
            order.reviewer = reviewer_name
            order.reviewed_at = datetime.now(UTC)
            order.review_notes = decision.notes

        await session.commit()

    return {"status": "success"}