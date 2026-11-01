from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine import make_url
import os

# Determine if we're in test environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./orders.db")
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Base declaration moved here to avoid circular imports
Base = declarative_base()

engine = None
AsyncSessionLocal = None


def _validate_test_database(url):
    if os.getenv("TESTING", "").lower() == "true" or "PYTEST_CURRENT_TEST" in os.environ:
        if url.drivername != "sqlite+aiosqlite" or url.database != ":memory:":
            raise RuntimeError("Tests must use the dedicated in-memory SQLite database")


def init_db_engine():
    global engine, AsyncSessionLocal
    database_url = make_url(DATABASE_URL)
    _validate_test_database(database_url)
    engine = create_async_engine(
        database_url,
        echo=(
            os.getenv("APP_ENV", "").lower() == "development"
            and os.getenv("SQL_ECHO", "").lower() == "true"
        ),
        connect_args={"check_same_thread": False} if "sqlite" in database_url.drivername else {}
    )
    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    print(f"[DEBUG] Database engine initialized for backend: {database_url.get_backend_name()}")

async def init_db():
    if engine is None:
        init_db_engine()
    _validate_test_database(engine.url)