import json
import pytest
from httpx import AsyncClient, ASGITransport
from main import app
import database
from sqlalchemy import text
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
async def test_correct_total(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        response = await client.post("/validate-order", json={
            "quantity": 2,
            "unit_price": 10.0,
            "stated_total": 20.0
        })
        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert response.json()["calculated_total"] == 20.0
        assert "id" in response.json()


@pytest.mark.anyio
async def test_invalid_total(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        response = await client.post("/validate-order", json={
            "quantity": 3.0,
            "unit_price": 0.1,
            "stated_total": 0.3
        })
        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert "id" in response.json()


@pytest.mark.anyio
async def test_mismatched_total(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        response = await client.post("/validate-order", json={
            "quantity": 5.0,
            "unit_price": 10.0,
            "stated_total": 40.0
        })
        assert response.status_code == 200
        assert response.json()["valid"] is False
        assert response.json()["error"] == "Total mismatch"
        assert "id" in response.json()
        orders_response = await client.get("/orders")
        assert orders_response.status_code == 200
        assert len(orders_response.json()) == 1
        assert orders_response.json()[0]["review_status"] == "PENDING_REVIEW"


@pytest.mark.anyio
async def test_small_positive_values_are_valid(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        response = await client.post("/validate-order", json={
            "quantity": 0.01,
            "unit_price": 0.01,
            "stated_total": 0.0001
        })
        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert "id" in response.json()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {"quantity": 0, "unit_price": 1, "stated_total": 1},
        {"quantity": -1, "unit_price": 1, "stated_total": 1},
        {"quantity": float("nan"), "unit_price": 1, "stated_total": 1},
        {"quantity": float("inf"), "unit_price": 1, "stated_total": 1},
        {"quantity": -float("inf"), "unit_price": 1, "stated_total": 1},
        {"quantity": 1, "unit_price": 0, "stated_total": 1},
        {"quantity": 1, "unit_price": -1, "stated_total": 1},
        {"quantity": 1, "unit_price": float("nan"), "stated_total": 1},
        {"quantity": 1, "unit_price": float("inf"), "stated_total": 1},
        {"quantity": 1, "unit_price": -float("inf"), "stated_total": 1},
        {"quantity": 1, "unit_price": 1, "stated_total": 0},
        {"quantity": 1, "unit_price": 1, "stated_total": -1},
        {"quantity": 1, "unit_price": 1, "stated_total": float("nan")},
        {"quantity": 1, "unit_price": 1, "stated_total": float("inf")},
        {"quantity": 1, "unit_price": 1, "stated_total": -float("inf")},
    ],
)
async def test_invalid_numeric_inputs_return_422_without_creating_orders(monkeypatch, payload):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        response = await client.post(
            "/validate-order",
            content=json.dumps(payload, allow_nan=True),
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422

        orders_response = await client.get("/orders")
        assert orders_response.status_code == 200
        assert orders_response.json() == []

@pytest.mark.anyio
async def test_validate_order_unauthorized(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Missing API key
        response = await client.post("/validate-order", json={
            "quantity": 2,
            "unit_price": 10.0,
            "stated_total": 20.0
        })
        assert response.status_code == 403


@pytest.mark.anyio
async def test_validate_order_invalid_api_key(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test_key")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-api-key": "invalid"},
    ) as client:
        response = await client.post("/validate-order", json={
            "quantity": 2,
            "unit_price": 10.0,
            "stated_total": 20.0
        })
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid API Key"


@pytest.mark.anyio
async def test_validate_order_missing_api_key_configuration(monkeypatch):
    monkeypatch.delenv("APP_API_KEY", raising=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-api-key": "test_key"},
    ) as client:
        response = await client.post("/validate-order", json={
            "quantity": 2,
            "unit_price": 10.0,
            "stated_total": 20.0
        })
    assert response.status_code == 500
    assert response.json()["detail"] == "Server configuration incomplete"