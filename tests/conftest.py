import os
import sys
from pathlib import Path
import pytest

# Set test environment variables FIRST (before any module imports)
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["APP_API_KEY"] = "test_key"
os.environ["REVIEWER_API_KEY"] = "reviewer_secret_key"
os.environ["REVIEWER_NAME"] = "Test Reviewer"

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
async def isolated_test_database():
    import database

    await database.init_db()
    async with database.engine.begin() as connection:
        await connection.run_sync(database.Base.metadata.create_all)

    yield

    async with database.engine.begin() as connection:
        await connection.run_sync(database.Base.metadata.drop_all)
