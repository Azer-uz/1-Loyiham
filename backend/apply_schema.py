import asyncio
from database import engine, Base
import models_db

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Schema applied successfully!")

if __name__ == "__main__":
    asyncio.run(init())
