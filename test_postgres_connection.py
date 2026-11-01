import os

os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest

import database


def test_postgresql_connection_is_blocked_in_test_mode(monkeypatch):
    monkeypatch.setattr(
        database,
        "DATABASE_URL",
        "postgresql+asyncpg://localhost/ai_order_intelligence",
    )

    with pytest.raises(RuntimeError, match="dedicated in-memory SQLite"):
        database.init_db_engine()
