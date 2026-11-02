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
<body><div class="wrap"><header><div class="brand">AI Order Intelligence</div><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><a href="/review-preview" style="background:#315ce6;color:white;padding:11px 14px;border-radius:10px;font-weight:700;font-size:13px">Try review workflow</a><a href="/review" style="font-size:13px;font-weight:700">Reviewer login</a><span class="tag">Live order validation system</span></div></header><section class="hero"><h1>Validate fuel orders in seconds.</h1><p class="sub">Enter an order to see how the system checks the amount, calculates the correct total and flags discrepancies for human review. No account or API key needed to try an order.</p></section><div class="layout"><section class="panel"><h2>Try an order</h2><p class="small">Choose a sample or enter your own numbers. Values are illustrative.</p><div class="examples"><button type="button" onclick="sample(1)">Matching order</button><button type="button" onclick="sample(2)">Mismatched order</button></div><form id="order"><label for="quantity">Fuel quantity (litres)</label><input id="quantity" type="number" min="0.01" step="any" value="100" required><label for="price">Price per litre (KES)</label><input id="price" type="number" min="0.01" step="any" value="180" required><label for="total">Submitted order total (KES)</label><input id="total" type="number" min="0" step="any" value="18000" required><button class="primary" id="submit" type="submit">Validate order</button></form></section><section class="panel"><h2>Validation result</h2><p class="small">The result comes from the deployed Python/FastAPI validation logic.</p><div id="result" class="result" aria-live="polite"><strong>Ready to validate</strong><p>Submit an order to see the calculated total, difference and review decision.</p></div><p class="small">Submitted orders are saved in PostgreSQL. Matching orders are approved automatically; discrepancies enter the protected reviewer queue.</p></section></div><footer>Built with Python, FastAPI and PostgreSQL. <a href="/docs" target="_blank" rel="noopener">Explore the API documentation</a> · <a href="/review">Reviewer dashboard</a> · <a href="https://github.com/lucyw1234/ai-order-intelligence" target="_blank" rel="noopener">View source code</a></footer></div>
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

@app.get("/review", response_class=HTMLResponse, include_in_schema=False)
async def reviewer_dashboard():
    return HTMLResponse("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Order Review | AI Order Intelligence</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fb;color:#17233c;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}.wrap{max-width:1050px;margin:auto;padding:36px 22px}header{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}h1{font-size:clamp(28px,4vw,42px);margin:38px 0 8px}p{color:#647089;line-height:1.6}.panel{background:white;border:1px solid #e0e7f0;border-radius:17px;padding:24px;margin:20px 0;box-shadow:0 8px 30px #17233c08}label{display:block;font-weight:650;font-size:13px;margin:12px 0 6px}input,textarea{width:100%;font:inherit;border:1px solid #cdd7e6;border-radius:9px;padding:12px}textarea{min-height:68px}button{font:inherit;border:0;border-radius:9px;padding:11px 15px;cursor:pointer;font-weight:700;background:#315ce6;color:white}button:disabled{opacity:.5;cursor:wait}.danger{background:#a52c38}.muted{background:#e9edf5;color:#30405b}a{color:#315ce6}.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}.row>*{flex:1}.item{border:1px solid #e0e7f0;border-radius:13px;padding:19px;margin-top:15px}.item h3{margin:0 0 12px}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.stat{background:#f5f7fb;padding:14px;border-radius:9px}.stat b{display:block;margin-top:5px}.notice{font-size:13px}#queue{margin-top:18px}@media(max-width:650px){.stats{grid-template-columns:1fr}.row{display:block}.row button{margin-top:8px;width:100%}}</style></head>
<body><div class="wrap"><header><strong>AI Order Intelligence / Reviewer</strong><a href="/">Back to order submission</a></header>
<h1>Review flagged orders</h1><p>Authorized reviewers can inspect saved PostgreSQL orders and approve or reject discrepancies.</p>
<section class="panel" id="login"><h2>Reviewer access</h2><p class="notice">Enter your application API key and reviewer key. Credentials are used for this browser session only and are not saved.</p>
<label for="appkey">Application API key</label><input id="appkey" type="password" autocomplete="off">
<label for="reviewkey">Reviewer API key</label><input id="reviewkey" type="password" autocomplete="off">
<div style="margin-top:16px"><button id="load">Load pending orders</button></div><p id="message" role="status"></p></section>
<section class="panel" id="workspace" hidden><div class="row"><h2>Pending review queue</h2><button class="muted" id="refresh">Refresh</button><button class="muted" id="logout">Lock dashboard</button></div>
<div id="queue" aria-live="polite"></div></section>
</div><script>
let appKey='',reviewKey='';const $=id=>document.getElementById(id);const fmt=n=>new Intl.NumberFormat('en-KE',{maximumFractionDigits:2}).format(n);
function el(tag,text){const x=document.createElement(tag);if(text!==undefined)x.textContent=text;return x}
async function load(){const k=$('appkey').value.trim();const rk=$('reviewkey').value.trim();if(k)appKey=k;if(rk)reviewKey=rk;if(!appKey||!reviewKey){$('message').textContent='Both keys are required.';return}
$('load').disabled=true;$('message').textContent='Loading orders...';try{
const res=await fetch('/orders/pending-review',{headers:{'x-api-key':appKey},cache:'no-store'});
if(!res.ok)throw Error('Unable to load orders. Check the application API key.');
const orders=await res.json();$('login').hidden=true;$('workspace').hidden=false;render(orders)
}catch(e){$('message').textContent=e.message}finally{$('load').disabled=false}}
function render(orders){const queue=$('queue');queue.replaceChildren();if(!orders.length){queue.append(el('p','No orders are currently awaiting review.'));return}
queue.append(el('p',orders.length+' order(s) awaiting review'));
for(const o of orders){const card=el('div');card.className='item';card.append(el('h3','Order '+o.id.slice(0,8)));
const stats=el('div');stats.className='stats';for(const [label,value] of [['Quantity',fmt(o.quantity)+' litres'],['Calculated total','KES '+fmt(o.calculated_total)],['Submitted total','KES '+fmt(o.stated_total)]]){const d=el('div');d.className='stat';d.append(el('span',label),el('b',value));stats.append(d)}card.append(stats);
card.append(el('p','Difference: KES '+fmt(Math.abs(o.calculated_total-o.stated_total))));
const note=el('textarea');note.placeholder='Review notes (optional)';note.setAttribute('aria-label','Review notes for order '+o.id);card.append(note);
const actions=el('div');actions.className='row';for(const [decision,label,cls] of [['APPROVE','Approve',''],['REJECT','Reject','danger']]){const b=el('button',label);b.className=cls;b.onclick=async()=>{if(!confirm(label+' this order?'))return;for(const child of actions.querySelectorAll('button'))child.disabled=true;try{const res=await fetch('/orders/'+encodeURIComponent(o.id)+'/review',{method:'PATCH',headers:{'Content-Type':'application/json','x-api-key':appKey,'x-reviewer-key':reviewKey},body:JSON.stringify({decision,notes:note.value})});if(!res.ok){const body=await res.json();throw Error(typeof body.detail==='string'?body.detail:'Review request failed')}card.replaceChildren(el('p','Decision saved: '+label));}catch(e){card.append(el('p','Error: '+e.message));for(const child of actions.querySelectorAll('button'))child.disabled=false}};actions.append(b)}card.append(actions);queue.append(card)}}
$('load').onclick=load;$('refresh').onclick=load;$('logout').onclick=()=>{appKey='';reviewKey='';$('appkey').value='';$('reviewkey').value='';$('workspace').hidden=true;$('login').hidden=false;$('message').textContent='Dashboard locked.'};
</script></body></html>""")

@app.get("/review-preview", response_class=HTMLResponse, include_in_schema=False)
async def public_review_preview():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review Workflow | AI Order Intelligence</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fb;color:#17233c;font-family:Inter,system-ui,sans-serif}.wrap{max-width:920px;margin:auto;padding:32px 22px}header{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center}a{color:#315ce6}h1{font-size:clamp(30px,5vw,46px);letter-spacing:-1px;margin:42px 0 10px}p{color:#63718a;line-height:1.6}.panel{background:white;border:1px solid #e0e7f0;border-radius:17px;padding:26px;margin:24px 0;box-shadow:0 8px 30px #17233c08}.tag{display:inline-block;background:#fff0d7;color:#995600;padding:8px 12px;border-radius:8px;font-weight:750;font-size:13px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}.metric{background:#f5f7fb;padding:17px;border-radius:10px}.metric span{display:block;color:#647089;font-size:13px}.metric b{display:block;margin-top:7px;font-size:21px}.row{display:flex;gap:12px;flex-wrap:wrap}button{font:inherit;border:0;border-radius:10px;padding:13px 20px;cursor:pointer;background:#315ce6;color:white;font-weight:750}.danger{background:#b33343}.reset{background:#e9edf5;color:#30405b}textarea{width:100%;font:inherit;border:1px solid #cdd7e6;border-radius:9px;padding:12px;min-height:75px;margin:12px 0}.notice{border-left:4px solid #315ce6;padding:10px 14px;background:#eaf0ff;border-radius:6px;font-size:14px}@media(max-width:650px){.grid{grid-template-columns:1fr}}</style></head><body><div class="wrap">
<header><strong>AI Order Intelligence</strong><nav><a href="/">Submit an order</a> &nbsp; · &nbsp; <a href="/review">Authorized reviewer login</a></nav></header>
<h1>Order review workflow</h1><p>Inspect a flagged fuel order and try the reviewer decision process.</p>
<p class="notice"><strong>Public interactive preview.</strong> This example uses sample data. Approve and Reject show how the reviewer interface works but do not modify PostgreSQL. Real decisions require authorized reviewer access.</p>
<section class="panel"><span class="tag" id="status">PENDING REVIEW</span><h2>Fuel order: SAMPLE-001</h2><div class="grid"><div class="metric"><span>Quantity</span><b>100 litres</b></div><div class="metric"><span>Unit price</span><b>KES 180</b></div><div class="metric"><span>Submitted total</span><b>KES 17,500</b></div></div><div class="grid"><div class="metric"><span>Expected total</span><b>KES 18,000</b></div><div class="metric"><span>Difference</span><b>KES 500</b></div><div class="metric"><span>Validation</span><b>Mismatch</b></div></div>
<label for="notes"><strong>Reviewer notes</strong></label><textarea id="notes" placeholder="Add a reason for your decision"></textarea><div class="row"><button id="approve">Approve order</button><button id="reject" class="danger">Reject order</button><button id="reset" class="reset">Reset example</button></div><p id="outcome" role="status"></p></section>
<p>Want to inspect the real backend? <a href="/docs">View API documentation</a> or <a href="https://github.com/lucyw1234/ai-order-intelligence">view the source code</a>.</p></div><script>
const status=document.getElementById('status'),out=document.getElementById('outcome'),notes=document.getElementById('notes');
function decide(value){status.textContent=value;status.style.background=value==='APPROVED'?'#dff7e8':'#ffe2e4';status.style.color=value==='APPROVED'?'#176a3b':'#a52c38';out.textContent='Sample decision: '+value+'. '+(notes.value.trim()?'Notes: '+notes.value.trim():'No notes added.')+' No database records were changed.'}
document.getElementById('approve').onclick=()=>decide('APPROVED');document.getElementById('reject').onclick=()=>decide('REJECTED');document.getElementById('reset').onclick=()=>{status.textContent='PENDING REVIEW';status.style.background='#fff0d7';status.style.color='#995600';out.textContent='';notes.value=''};
</script></body></html>""")
