import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from database import init_db, AsyncSessionLocal
from sqlalchemy import text
import os

os.environ["TESTING"] = "true"

@pytest.fixture(autouse=True, scope="function")
async def clear_database():
    await init_db()
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM fuel_orders"))
        await session.commit()


@pytest.mark.anyio
async def test_correct_total():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
async def test_invalid_total():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/validate-order", json={
            "quantity": 3.0,
            "unit_price": 0.1,
            "stated_total": 0.3
        })
        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert "id" in response.json()


@pytest.mark.anyio
async def test_mismatched_total():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/validate-order", json={
            "quantity": 5.0,
            "unit_price": 10.0,
            "stated_total": 40.0
        })
        assert response.status_code == 200
        assert response.json()["valid"] is False
        assert response.json()["error"] == "Total mismatch"
        assert "id" in response.json()


@pytest.mark.anyio
async def test_negative_values():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/validate-order", json={
            "quantity": -5.0,
            "unit_price": 10.0,
            "stated_total": -50.0
        })
        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert "id" in response.json()


@pytest.mark.anyio
async def test_zero_values():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/validate-order", json={
            "quantity": 0.0,
            "unit_price": 10.0,
            "stated_total": 0.0
        })
        assert response.status_code == 200
        assert response.json()["valid"] is True
        assert "id" in response.json()