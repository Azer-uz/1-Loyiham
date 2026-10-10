import asyncio
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from database import AsyncSessionLocal
from models_db import LocalDemand, LocalPayment, LocalCounterparty, User, SyncLog
from sqlalchemy import select, func

async def main():
    async with AsyncSessionLocal() as s:
        # Users
        u_count = await s.scalar(select(func.count(User.id)))
        users = (await s.execute(select(User))).scalars().all()
        print(f"Users count: {u_count}")
        for u in users:
            print(f"  User: {u.username}, role={u.role}, is_active={u.is_active}")

        # Demands
        d_count = await s.scalar(select(func.count(LocalDemand.id)))
        print(f"\nDemands count: {d_count}")
        demands = (await s.execute(select(LocalDemand).order_by(LocalDemand.moment.desc()).limit(10))).scalars().all()
        for d in demands:
            print(f"  {d.name} | moment: {d.moment} | agent: '{d.agent_name}' | state: '{d.state_name}' | sum: {d.sum} | remaining: {d.remaining}")

        # Payments
        p_count = await s.scalar(select(func.count(LocalPayment.id)))
        print(f"\nPayments count: {p_count}")

        # Counterparties
        c_count = await s.scalar(select(func.count(LocalCounterparty.id)))
        print(f"\nCounterparties count: {c_count}")

        # SyncLog
        logs = (await s.execute(select(SyncLog).order_by(SyncLog.created_at.desc()).limit(5))).scalars().all()
        print(f"\nRecent Sync Logs: {len(logs)}")
        for l in logs:
            print(f"  SyncLog: type={l.entity_type}, status={l.status}, synced={l.records_synced}, time={l.created_at}, msg={l.message}")

if __name__ == "__main__":
    asyncio.run(main())
