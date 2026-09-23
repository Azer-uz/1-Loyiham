# backend/test_system_upgrades.py
import asyncio
import sys
from pathlib import Path

import io

if sys.platform == "win32":
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


from database import init_db, AsyncSessionLocal
from auth_utils import ensure_default_admin, hash_password, verify_password, create_access_token
from models_db import User, LocalDemand, LocalCounterparty
from sqlalchemy import select, func
import httpx


async def run_tests():
    print("🧪 [Test 1] DB Initialization...")
    await init_db()
    print("   ✅ DB initialized successfully!")

    print("\n🧪 [Test 2] Default Admin Verification...")
    async with AsyncSessionLocal() as session:
        await ensure_default_admin(session)
        admin = (await session.execute(select(User).where(User.username == "admin"))).scalars().first()
        assert admin is not None, "Admin user topilmadi"
        assert verify_password("admin123", admin.hashed_password), "Admin paroli tekshiruvdan o'tmadi"
        print(f"   ✅ Admin topildi: {admin.username}, role={admin.role}")

    print("\n🧪 [Test 3] JWT Token Test...")
    token = create_access_token({"sub": "admin", "role": "admin"})
    assert token and isinstance(token, str), "Token generatsiya qilinmadi"
    print(f"   ✅ Token muvaffaqiyatli yaratildi (uzunligi: {len(token)})")

    print("\n🧪 [Test 4] Local DB Operations...")
    async with AsyncSessionLocal() as session:
        # Test insert LocalDemand
        test_demand = LocalDemand(
            id="test-demand-uuid-1",
            name="TEST-001",
            moment="2026-09-16 12:00:00",
            sum=500000.0,
            payed_sum=500000.0,
            remaining=0.0,
            payment_status="paid",
            payment_status_name="✅ To'langan",
            agent_name="Test Mijoz",
            agent_id="test-agent-1",
        )
        existing = await session.get(LocalDemand, "test-demand-uuid-1")
        if not existing:
            session.add(test_demand)
            await session.commit()
        
        count = await session.scalar(select(func.count(LocalDemand.id)))
        assert count > 0, "LocalDemand count 0 bo'ldi"
        print(f"   ✅ Local DB'da {count} ta test yozuv muvaffaqiyatli tekshirildi!")

    print("\n🎉 BARCHA TESTLAR MUVAFFAQIYATLI O'TDI!")


if __name__ == "__main__":
    asyncio.run(run_tests())
