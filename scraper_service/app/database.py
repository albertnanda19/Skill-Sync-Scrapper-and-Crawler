from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def _make_engine():
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    return create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)


engine = _make_engine()
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
