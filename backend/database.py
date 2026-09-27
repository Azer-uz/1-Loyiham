# backend/database.py
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "app.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DB_PATH}")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    pass

async def get_db():
    """FastAPI dependency for DB session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Barcha jadvallarni yaratish va boshlang'ich admin foydalanuvchini kiritish"""
    # SQLite uchun WAL rejimini yoqish (tezlikni bir necha barobar oshiradi)
    if "sqlite" in DATABASE_URL:
        async with engine.begin() as conn:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            await conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
            await conn.exec_driver_sql("PRAGMA cache_size=-64000;")
            await conn.exec_driver_sql("PRAGMA temp_store=MEMORY;")
            await conn.exec_driver_sql("PRAGMA mmap_size=268435456;")
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.exec_driver_sql("ALTER TABLE local_counterparties ADD COLUMN \"group\" VARCHAR(100) DEFAULT '';")
            except Exception:
                pass
            try:
                await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500) DEFAULT '';")
            except Exception:
                pass
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
