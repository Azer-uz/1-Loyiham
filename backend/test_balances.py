import asyncio
import sys
sys.path.append(".")
from moysklad_client import ms_client

async def main():
    b = await ms_client.get_all_balances()
    print(list(b.items())[:5])

if __name__ == "__main__":
    asyncio.run(main())
