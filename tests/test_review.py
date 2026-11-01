import pytest
from httpx import AsyncClient, ASGITransport
from main import app
import database
from sqlalchemy import event, text
from sqlalchemy.orm import Session
from datetime import timedelta, timezone
import os
import os

os.environ["TESTING"] = "true"

@pytest.fixture(autouse=True, scope="function")
async def clear_database(isolated_test_database):
    await database.init_db()
    async with database.AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM fuel_orders"))
        await session.commit()

@pytest.mark.anyio
async def test_pending_review_endpoint(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    monkeypatch.setenv("REVIEWER_API_KEY", "reviewer_secret_key")
    monkeypatch.setenv("REVIEWER_NAME", "Reviewer")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        # Create an invalid order that should be pending review
        response = await client.post("/validate-order", json={
            "quantity": 5.0,
            "unit_price": 10.0,
            "stated_total": 40.0
        })
        assert response.status_code == 200
        assert response.json()["valid"] is False

        # Check pending review endpoint
        pending_response = await client.get("/orders/pending-review")
        assert pending_response.status_code == 200
        pending_orders = pending_response.json()
        assert len(pending_orders) == 1
        assert pending_orders[0]["review_status"] == "PENDING_REVIEW"

@pytest.mark.anyio
async def test_review_order_approval(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    monkeypatch.setenv("REVIEWER_API_KEY", "reviewer_secret_key")
    monkeypatch.setenv("REVIEWER_NAME", "Test Approver")
    captured_timestamps = []

    def capture_review_timestamp(session, flush_context, instances):
        captured_timestamps.extend(
            order.reviewed_at
            for order in session.dirty
            if hasattr(order, "reviewed_at") and order.reviewed_at is not None
        )

    assert database.Base.metadata.tables["fuel_orders"].c.reviewed_at.type.timezone is True
    event.listen(Session, "before_flush", capture_review_timestamp)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
            response = await client.post("/validate-order", json={
                "quantity": 5.0,
                "unit_price": 10.0,
                "stated_total": 40.0
            })
            order_id = response.json()["id"]

            review_response = await client.patch(
                f"/orders/{order_id}/review",
                json={"decision": "APPROVE", "notes": "Valid after review"},
                headers={"x-reviewer-key": "reviewer_secret_key"}
            )
            assert review_response.status_code == 200

            orders_response = await client.get("/orders")
            orders = orders_response.json()
            assert orders[0]["review_status"] == "APPROVED"
            assert orders[0]["reviewer"] == "Test Approver"
            assert orders[0]["review_notes"] == "Valid after review"
    finally:
        event.remove(Session, "before_flush", capture_review_timestamp)

    assert len(captured_timestamps) == 1
    assert captured_timestamps[0].tzinfo == timezone.utc
    assert captured_timestamps[0].utcoffset() == timedelta(0)

@pytest.mark.anyio
async def test_review_order_rejection(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    monkeypatch.setenv("REVIEWER_API_KEY", "reviewer_secret_key")
    monkeypatch.setenv("REVIEWER_NAME", "Test Rejector")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        # Create an invalid order
        response = await client.post("/validate-order", json={
            "quantity": 5.0,
            "unit_price": 10.0,
            "stated_total": 40.0
        })
        order_id = response.json()["id"]

        # Reject the order
        review_response = await client.patch(
            f"/orders/{order_id}/review",
            json={"decision": "REJECT", "notes": "Invalid order"},
            headers={"x-reviewer-key": "reviewer_secret_key"}
        )
        assert review_response.status_code == 200

        # Verify the order was updated
        orders_response = await client.get("/orders")
        orders = orders_response.json()
        assert orders[0]["review_status"] == "REJECTED"
        assert orders[0]["reviewer"] == "Test Rejector"

@pytest.mark.anyio
async def test_invalid_review_decision(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    monkeypatch.setenv("REVIEWER_API_KEY", "reviewer_secret_key")
    monkeypatch.setenv("REVIEWER_NAME", "Reviewer")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        # Create an invalid order
        response = await client.post("/validate-order", json={
            "quantity": 5.0,
            "unit_price": 10.0,
            "stated_total": 40.0
        })
        order_id = response.json()["id"]

        # Try invalid decision
        review_response = await client.patch(
            f"/orders/{order_id}/review",
            json={"decision": "INVALID", "notes": "Test"},
            headers={"x-reviewer-key": "reviewer_secret_key"}
        )
        assert review_response.status_code == 400

@pytest.mark.anyio
async def test_review_non_pending_order(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    monkeypatch.setenv("REVIEWER_API_KEY", "reviewer_secret_key")
    monkeypatch.setenv("REVIEWER_NAME", "Reviewer")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        # Create a valid order (should be auto-approved)
        response = await client.post("/validate-order", json={
            "quantity": 10.0,
            "unit_price": 10.0,
            "stated_total": 100.0
        })
        order_id = response.json()["id"]

        # Try to review an already approved order
        review_response = await client.patch(
            f"/orders/{order_id}/review",
            json={"decision": "REJECT", "notes": "Test"},
            headers={"x-reviewer-key": "reviewer_secret_key"}
        )
        assert review_response.status_code == 400

@pytest.mark.anyio
async def test_missing_reviewer_configuration(monkeypatch):
    # Set API key but no reviewer name
    monkeypatch.setenv("APP_API_KEY", "test_key")
    monkeypatch.setenv("REVIEWER_API_KEY", "reviewer_secret_key")
    monkeypatch.delenv("REVIEWER_NAME", raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        # Create an invalid order
        response = await client.post("/validate-order", json={
            "quantity": 5.0,
            "unit_price": 10.0,
            "stated_total": 40.0
        })
        order_id = response.json()["id"]

        # Attempt to review (should fail due to missing config)
        review_response = await client.patch(
            f"/orders/{order_id}/review",
            json={"decision": "APPROVE"},
            headers={"x-reviewer-key": "reviewer_secret_key"}
        )
        assert review_response.status_code == 500
        assert "Reviewer configuration incomplete" in review_response.json()["detail"]


@pytest.mark.anyio
async def test_review_order_missing_reviewer_api_key(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    monkeypatch.setenv("REVIEWER_API_KEY", "reviewer_secret_key")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-api-key": "test_key"},
    ) as client:
        response = await client.patch(
            "/orders/unused/review",
            json={"decision": "APPROVE"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "Missing reviewer API key"


@pytest.mark.anyio
async def test_review_order_invalid_reviewer_api_key(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    monkeypatch.setenv("REVIEWER_API_KEY", "reviewer_secret_key")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-api-key": "test_key", "x-reviewer-key": "invalid"},
    ) as client:
        response = await client.patch(
            "/orders/unused/review",
            json={"decision": "APPROVE"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid reviewer API key"


@pytest.mark.anyio
async def test_review_order_missing_reviewer_api_key_configuration(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    monkeypatch.delenv("REVIEWER_API_KEY", raising=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-api-key": "test_key", "x-reviewer-key": "reviewer_secret_key"},
    ) as client:
        response = await client.patch(
            "/orders/unused/review",
            json={"decision": "APPROVE"},
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "Server configuration incomplete"