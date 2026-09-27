import asyncio
import sys
import os

# Set UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tasks import sync_all_data
from database import AsyncSessionLocal
from sqlalchemy import select
from models_db import LocalCounterparty

async def main():
    print("Sinxronlash boshlandi...")
    res = await sync_all_data()
    print("Sync natijasi:", res)
    
    async with AsyncSessionLocal() as db:
        aid = '7b1f630a-91f0-11f1-0a80-040f00076240' # Azer
        cp = await db.scalar(select(LocalCounterparty).where(LocalCounterparty.id == aid))
        if cp:
            print(f"Mijoz: {cp.name}, DB dagi rasmiy balansi: {cp.balance:,.2f} so'm")

if __name__ == '__main__':
    asyncio.run(main())
