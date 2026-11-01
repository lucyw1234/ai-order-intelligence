import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import make_url

import database


def test_test_database_uses_in_memory_sqlite():
    assert database.DATABASE_URL == database.TEST_DATABASE_URL


@pytest.mark.anyio
async def test_init_db_initializes_engine_without_creating_tables(monkeypatch):
    monkeypatch.setattr(database, "engine", None)
    monkeypatch.setattr(database, "AsyncSessionLocal", None)

    await database.init_db()

    async with database.engine.connect() as connection:
        table_names = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )
    assert "fuel_orders" not in table_names
    await database.engine.dispose()


@pytest.mark.parametrize(
    ("app_env", "sql_echo", "expected"),
    [
        ("", "true", False),
        ("production", "true", False),
        ("development", "false", False),
        ("development", "true", True),
    ],
)
@pytest.mark.anyio
async def test_sql_echo_requires_explicit_development_setting(
    monkeypatch, app_env, sql_echo, expected
):
    monkeypatch.setattr(database, "engine", None)
    monkeypatch.setattr(database, "AsyncSessionLocal", None)
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("SQL_ECHO", sql_echo)

    database.init_db_engine()

    assert database.engine.echo is expected
    await database.engine.dispose()


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite+aiosqlite:///./orders.db",
        "sqlite+aiosqlite:///./orders_test.db",
        "postgresql+asyncpg://localhost/ai_order_intelligence",
        "postgresql+asyncpg://railway.invalid/ai_order_intelligence",
        "postgresql+asyncpg://supabase.invalid/ai_order_intelligence",
    ],
)
def test_test_database_rejects_non_memory_urls(monkeypatch, database_url):
    monkeypatch.setattr(database, "DATABASE_URL", database_url)

    with pytest.raises(RuntimeError, match="dedicated in-memory SQLite"):
        database.init_db_engine()


@pytest.mark.anyio
async def test_init_db_rejects_existing_file_engine(monkeypatch):
    class ConnectionForbiddenEngine:
        url = make_url("sqlite+aiosqlite:///./orders_test.db")

        def connect(self):
            pytest.fail("The test attempted to connect to the existing database")

    monkeypatch.setattr(database, "engine", ConnectionForbiddenEngine())

    with pytest.raises(RuntimeError, match="dedicated in-memory SQLite"):
        await database.init_db()
