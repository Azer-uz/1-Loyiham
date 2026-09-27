import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from httpx import AsyncClient, ASGITransport
from main import app
from auth_utils import create_access_token

async def test_search():
    token = create_access_token({'sub': 'admin', 'role': 'admin'})
    headers = {'Authorization': f'Bearer {token}'}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        for q in ['00144', '00021', '144', '21']:
            r = await client.get(f'/api/demands/search/assortment?query={q}', headers=headers)
            data = r.json()
            items = data.get('data', [])
            print(f"Search query '{q}' -> Status: {r.status_code}, Found: {len(items)}")
            for item in items[:3]:
                print(f"   📦 {item.get('name')} | Code: {item.get('code')} | Price: {item.get('price')}")

if __name__ == '__main__':
    asyncio.run(test_search())
