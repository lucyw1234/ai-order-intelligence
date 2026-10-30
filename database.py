from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import text
import os

# Determine if we're in test environment
TESTING = os.getenv("TESTING", "false").lower() == "true"

# Use different database for testing
DATABASE_URL = "sqlite+aiosqlite:///./orders_test.db" if TESTING else "sqlite+aiosqlite:///./orders.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False}
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def init_db():
    async with engine.connect() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)

        # Check if review_status column exists
        result = await conn.execute(text("""
            SELECT 1 FROM pragma_table_info('fuel_orders')
            WHERE name = 'review_status'
        """))
        if not result.scalar():
            # Add review_status column
            await conn.execute(text("""
                ALTER TABLE fuel_orders
                ADD COLUMN review_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW'
            """))

            # Backfill review_status based on valid field
            await conn.execute(text("""
                UPDATE fuel_orders
                SET review_status = 'APPROVED'
                WHERE valid = 1
            """))
            await conn.execute(text("""
                UPDATE fuel_orders
                SET review_status = 'PENDING_REVIEW'
                WHERE valid = 0
            """))

            # Add other review columns
            await conn.execute(text("""
                ALTER TABLE fuel_orders
                ADD COLUMN reviewer TEXT
            """))
            await conn.execute(text("""
                ALTER TABLE fuel_orders
                ADD COLUMN reviewed_at DATETIME
            """))
            await conn.execute(text("""
                ALTER TABLE fuel_orders
                ADD COLUMN review_notes TEXT
            """))

        await conn.commit()