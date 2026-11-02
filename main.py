import secrets
import math
from typing import Optional

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy import select, update
from typing import List
from datetime import datetime, UTC, timedelta
from pydantic import BaseModel
from models import OrderRequest, OrderResponse, OrderListItem
from services.order_validation import validate_order
import database
from db_models import FuelOrder, ReviewStatus
import uuid
import os

async def get_app_api_key(x_api_key: Optional[str] = Header(None)):
    APP_API_KEY = os.getenv("APP_API_KEY")
    if not APP_API_KEY:
        raise HTTPException(status_code=500, detail="Server configuration incomplete")

    if x_api_key is None:
        raise HTTPException(status_code=403, detail="Missing API key")

    if not secrets.compare_digest(x_api_key.encode(), APP_API_KEY.encode()):
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return x_api_key

async def verify_reviewer_api_key(x_reviewer_key: Optional[str] = Header(None)):
    reviewer_api_key = os.getenv("REVIEWER_API_KEY")
    if not reviewer_api_key:
        raise HTTPException(status_code=500, detail="Server configuration incomplete")

    if x_reviewer_key is None:
        raise HTTPException(status_code=403, detail="Missing reviewer API key")

    if not secrets.compare_digest(x_reviewer_key.encode(), reviewer_api_key.encode()):
        raise HTTPException(status_code=403, detail="Invalid reviewer API key")
    return x_reviewer_key

async def lifespan(app: FastAPI):
    await database.init_db()
    yield

app = FastAPI(lifespan=lifespan)


def _sanitize_validation_value(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _sanitize_validation_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_validation_value(item) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": _sanitize_validation_value(jsonable_encoder(exc.errors()))},
    )


@app.post("/validate-order", response_model=OrderResponse, dependencies=[Depends(get_app_api_key)])
async def validate_order_endpoint(request: OrderRequest):
    response = validate_order(request.quantity, request.unit_price, request.stated_total)

    # Generate UUID before database operation
    order_id = str(uuid.uuid4())
    review_status = ReviewStatus.APPROVED if response.valid else ReviewStatus.PENDING_REVIEW

    async with database.AsyncSessionLocal() as session:
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

@app.get("/orders", response_model=List[OrderListItem], dependencies=[Depends(get_app_api_key)])
async def get_orders():
    async with database.AsyncSessionLocal() as session:
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

@app.get("/orders/pending-review", response_model=List[OrderListItem], dependencies=[Depends(get_app_api_key)])
async def get_pending_review_orders():
    async with database.AsyncSessionLocal() as session:
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

@app.patch("/orders/{order_id}/review", dependencies=[Depends(get_app_api_key)])
async def review_order(
    order_id: str,
    decision: ReviewDecision,
    api_key: str = Depends(verify_reviewer_api_key)
):
    # Validate decision
    if decision.decision not in ["APPROVE", "REJECT"]:
        raise HTTPException(400, "Invalid decision")

    async with database.AsyncSessionLocal() as session:
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

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def demo_home():
    return HTMLResponse("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Order Intelligence | Live Demo</title>
<style>
:root{font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;color:#17233c;background:#f3f6fb}*{box-sizing:border-box}body{margin:0}.wrap{max-width:1000px;margin:auto;padding:35px 22px}header{display:flex;justify-content:space-between;align-items:center;gap:12px}.brand{font-weight:800;letter-spacing:-.4px;font-size:19px}.tag{font-size:12px;border-radius:30px;padding:8px 12px;background:#e4f7ec;color:#167147;font-weight:700}.hero{padding:65px 0 30px}h1{font-size:clamp(34px,5vw,55px);line-height:1.09;letter-spacing:-1.7px;margin:0 0 18px;max-width:720px}.sub{font-size:17px;color:#647089;line-height:1.65;max-width:650px}.layout{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:20px}.panel{background:white;border:1px solid #e2e8f2;border-radius:19px;padding:27px;box-shadow:0 10px 35px #17233c08}h2{font-size:21px;margin:0 0 8px}p.small{font-size:13px;color:#68758d;line-height:1.55}label{display:block;font-size:13px;font-weight:700;margin:17px 0 7px}input{width:100%;border:1px solid #cdd7e6;border-radius:10px;padding:13px 14px;font:inherit;font-size:16px}input:focus{outline:2px solid #b6c9ff;border-color:#4169df}.examples{display:flex;gap:9px;flex-wrap:wrap;margin:20px 0 4px}.examples button{background:#eef2ff;color:#304baf;border:0;padding:10px 12px;border-radius:9px;font-weight:700;cursor:pointer}.primary{width:100%;margin-top:22px;background:#315ce6;color:white;border:0;padding:15px;border-radius:11px;font-size:15px;font-weight:750;cursor:pointer}.primary:disabled{opacity:.6}.result{background:#f7f9fd;border:1px dashed #ccd6e8;border-radius:13px;padding:22px;margin-top:20px;min-height:180px}.result strong{display:block;font-size:22px;margin-bottom:10px}.result p{color:#637089;line-height:1.6}.metric{display:flex;justify-content:space-between;border-bottom:1px solid #e5eaf2;padding:12px 0;gap:10px}.metric span{color:#647089}.status{display:inline-block;padding:8px 12px;border-radius:9px;font-size:13px;font-weight:800}.approved{background:#dff7e8;color:#176a3b}.review{background:#fff0d7;color:#995600}footer{padding:32px 0;color:#718099;font-size:13px}a{color:#315ce6;text-decoration:none}@media(max-width:730px){.layout{grid-template-columns:1fr}.hero{padding:42px 0 20px}.panel{padding:20px}}</style></head>
<body><div class="wrap"><header><div class="brand">AI Order Intelligence</div><span class="tag">Live order validation system</span></header><section class="hero"><h1>Validate fuel orders in seconds.</h1><p class="sub">Enter an order to see how the system checks the amount, calculates the correct total and flags discrepancies for human review. No account or API key needed to try an order.</p></section><div class="layout"><section class="panel"><h2>Try an order</h2><p class="small">Choose a sample or enter your own numbers. Values are illustrative.</p><div class="examples"><button type="button" onclick="sample(1)">Matching order</button><button type="button" onclick="sample(2)">Mismatched order</button></div><form id="order"><label for="quantity">Fuel quantity (litres)</label><input id="quantity" type="number" min="0.01" step="any" value="100" required><label for="price">Price per litre (KES)</label><input id="price" type="number" min="0.01" step="any" value="180" required><label for="total">Submitted order total (KES)</label><input id="total" type="number" min="0" step="any" value="18000" required><button class="primary" id="submit" type="submit">Validate order</button></form></section><section class="panel"><h2>Validation result</h2><p class="small">The result comes from the deployed Python/FastAPI validation logic.</p><div id="result" class="result" aria-live="polite"><strong>Ready to validate</strong><p>Submit an order to see the calculated total, difference and review decision.</p></div><p class="small">Submitted orders are saved in PostgreSQL. Matching orders are approved automatically; discrepancies enter the protected reviewer queue.</p></section></div><footer>Built with Python, FastAPI and PostgreSQL. <a href="/docs" target="_blank" rel="noopener">Explore the API documentation</a> · <a href="https://github.com/lucyw1234/ai-order-intelligence" target="_blank" rel="noopener">View source code</a></footer></div>
<script>function sample(n){document.getElementById('quantity').value=100;document.getElementById('price').value=180;document.getElementById('total').value=n===1?18000:17500;document.getElementById('result').innerHTML='<strong>Ready to validate</strong><p>Click Validate order to check this example.</p>'}const fmt=n=>new Intl.NumberFormat('en-KE',{maximumFractionDigits:2}).format(n);document.getElementById('order').addEventListener('submit',async e=>{e.preventDefault();const btn=document.getElementById('submit'),out=document.getElementById('result');btn.disabled=true;out.innerHTML='<strong>Checking order...</strong>';try{const payload={quantity:Number(document.getElementById('quantity').value),unit_price:Number(document.getElementById('price').value),stated_total:Number(document.getElementById('total').value)};const res=await fetch('/orders/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await res.json();if(!res.ok)throw Error(typeof data.detail==='string'?data.detail:'Check the numbers and try again');const diff=Math.abs(data.calculated_total-payload.stated_total);out.innerHTML='<span class="status '+(data.valid?'approved':'review')+'">'+(data.valid?'APPROVED':'NEEDS HUMAN REVIEW')+'</span><div class="metric"><span>Calculated total</span><b>KES '+fmt(data.calculated_total)+'</b></div><div class="metric"><span>Submitted total</span><b>KES '+fmt(payload.stated_total)+'</b></div><div class="metric"><span>Difference</span><b>KES '+fmt(diff)+'</b></div><p>'+(data.valid?'The submitted total matches the calculated amount.':'The submitted total does not match. This order should be reviewed before approval.')+'</p>'}catch(err){out.textContent='Could not validate: '+err.message}finally{btn.disabled=false}});</script></body></html>""")


_public_requests = {}

@app.post("/orders/submit", response_model=OrderResponse, tags=["Order validation"])
async def submit_public_order(request: OrderRequest, http_request: Request):
    ip = http_request.client.host if http_request.client else "unknown"
    now = datetime.now(UTC)
    recent = [t for t in _public_requests.get(ip, []) if now - t < timedelta(minutes=1)]
    if len(recent) >= 10:
        raise HTTPException(status_code=429, detail="Too many submissions. Please try again in a minute.")
    recent.append(now)
    _public_requests[ip] = recent
    result = validate_order(request.quantity, request.unit_price, request.stated_total)
    order_id = str(uuid.uuid4())
    review_status = ReviewStatus.APPROVED if result.valid else ReviewStatus.PENDING_REVIEW
    async with database.AsyncSessionLocal() as session:
        async with session.begin():
            session.add(FuelOrder(
                id=order_id, quantity=request.quantity, unit_price=request.unit_price,
                stated_total=request.stated_total, calculated_total=result.calculated_total,
                valid=result.valid, error=result.error, review_status=review_status,
            ))
    return OrderResponse(id=order_id, valid=result.valid, calculated_total=result.calculated_total, error=result.error)

@app.post("/demo/validate", response_model=OrderResponse, tags=["Order validation"])
async def demo_validate_order(request: OrderRequest):
    result = validate_order(request.quantity, request.unit_price, request.stated_total)
    return OrderResponse(id=str(uuid.uuid4()), valid=result.valid, calculated_total=result.calculated_total, error=result.error)
