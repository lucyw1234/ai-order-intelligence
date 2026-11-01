import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from database import init_db
import database
from sqlalchemy import text
import os

os.environ["TESTING"] = "true"

@pytest.fixture(autouse=True, scope="function")
async def clear_database(isolated_test_database):
    await init_db()
    async with database.AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM fuel_orders"))
        await session.commit()


@pytest.mark.anyio
async def test_order_persistence():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        # Validate an order
        response = await client.post("/validate-order", json={
            "quantity": 100.0,
            "unit_price": 2.5,
            "stated_total": 250.0
        })
        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert "id" in response.json()

        # Check if order was saved
        orders_response = await client.get("/orders")
        assert orders_response.status_code == 200
        orders = orders_response.json()
        assert len(orders) == 1
        assert orders[0]["quantity"] == 100.0
        assert orders[0]["valid"] is True

@pytest.mark.anyio
async def test_unique_order_ids():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-api-key": "test_key"}) as client:
        # Create two orders
        response1 = await client.post("/validate-order", json={
            "quantity": 50.0,
            "unit_price": 3.0,
            "stated_total": 150.0
        })
        response2 = await client.post("/validate-order", json={
            "quantity": 75.0,
            "unit_price": 2.0,
            "stated_total": 150.0
        })

        orders_response = await client.get("/orders")
        orders = orders_response.json()

        assert orders[0]["id"] != orders[1]["id"]