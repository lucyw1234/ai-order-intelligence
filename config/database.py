from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, func
import os
from dotenv import load_dotenv

load_dotenv()

# n8n analogy: This is like setting up your PostgreSQL node credentials in n8n
# but stored securely where only your app can access them

SUPABASE_URL = os.getenv("SUPABASE_URL")

# n8n analogy: Like having a PostgreSQL node configured but not connected yet
# We'll initialize the connection only when actually needed
if SUPABASE_URL:
    engine = create_async_engine(
        SUPABASE_URL,
        echo=True,
        pool_size=5,
        max_overflow=10
    )
else:
    engine = None

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
) if engine else None

Base = declarative_base()

async def get_db():
    """
    Dependency to get database session
    n8n analogy: Like the "Execute Query" node that automatically handles connections
    """
    if not engine:
        raise RuntimeError("Database not configured - set SUPABASE_URL")
    async with AsyncSessionLocal() as session:
        yield session