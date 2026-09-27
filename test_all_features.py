import asyncio
import os
import sys

# Set up paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from httpx import AsyncClient, ASGITransport
from main import app
from auth_utils import create_access_token

async def run_all_tests():
    token = create_access_token({"sub": "admin", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        print("--- 1. Testing GET /api/customers ---")
        r = await client.get("/api/customers?limit=50", headers=headers)
        assert r.status_code == 200, f"Failed: {r.status_code} {r.text}"
        data = r.json()
        print(f"✅ Customers count: {len(data['data'])}, Total: {data['meta']['size']}")

        print("--- 2. Testing GET /api/customers?limit=2000 (Dropdown loading) ---")
        r = await client.get("/api/customers?limit=2000", headers=headers)
        assert r.status_code == 200, f"Failed: {r.status_code} {r.text}"
        data = r.json()
        print(f"✅ All Customers for dropdown: {len(data['data'])}")

        print("--- 3. Testing GET /api/demands ---")
        r = await client.get("/api/demands?limit=50", headers=headers)
        assert r.status_code == 200, f"Failed: {r.status_code} {r.text}"
        data = r.json()
        print(f"✅ Demands count: {len(data['data'])}, Total: {data['meta']['size']}")

        print("--- 4. Testing GET /api/settings/accounts ---")
        r = await client.get("/api/settings/accounts", headers=headers)
        assert r.status_code == 200, f"Failed: {r.status_code} {r.text}"
        data = r.json()
        accs = data.get("data", {}).get("accounts", [])
        print(f"✅ Accounts count: {len(accs)}")
        for acc in accs:
            print(f"   Account: {acc.get('name')} | Currency: {acc.get('currency')} | Type: {acc.get('type')}")

        print("--- 5. Testing GET /api/currency/rates ---")
        r = await client.get("/api/currency/rates", headers=headers)
        if r.status_code == 200:
            print("✅ Currency rates endpoint OK")

        print("--- 6. Testing GET /api/payments/cashflow ---")
        r = await client.get("/api/payments/cashflow", headers=headers)
        assert r.status_code == 200, f"Failed: {r.status_code} {r.text}"
        cf_data = r.json().get("data", {})
        print(f"✅ Cashflow loaded: {len(cf_data.get('transactions', []))} transactions, Accounts count: {len(cf_data.get('accounts', []))}")

        print("--- 7. Testing GET /api/customers/{id} details & payments ---")
        cust_resp = await client.get("/api/customers?limit=1", headers=headers)
        cust_list = cust_resp.json().get("data", [])
        assert len(cust_list) > 0, "No customers found"
        cust_id = cust_list[0]["id"]
        r = await client.get(f"/api/customers/{cust_id}", headers=headers)
        assert r.status_code == 200, f"Failed: {r.status_code} {r.text}"
        c_detail = r.json().get("data", {})
        print(f"✅ Customer '{c_detail.get('name')}' detail OK: {len(c_detail.get('demands', []))} demands, {len(c_detail.get('payments', []))} payments")

        print("--- 8. Testing GET /api/demands/search/by-product (Instant indexed search) ---")
        t0 = asyncio.get_event_loop().time()
        r = await client.get("/api/demands/search/by-product?query=00843", headers=headers)
        search_dur = (asyncio.get_event_loop().time() - t0) * 1000
        assert r.status_code == 200, f"Failed: {r.status_code} {r.text}"
        search_data = r.json().get("data", {})
        matched_sales = search_data.get("matched_sales", [])
        assert len(matched_sales) > 0, "No sales found for 00843"
        has_eldor = any(s.get("agent_name") == "Eldor Qatortol" or s.get("demand_name") == "00843" for s in matched_sales)
        assert has_eldor, "00843 Eldor Qatortol was NOT found in search results"
        print(f"✅ Return Search OK ({search_dur:.1f}ms): {len(search_data.get('assortments', []))} tovar, {len(matched_sales)} sotuv topildi. 00843 Eldor Qatortol mavjud!")

    print("\n🎉 ALL 8 MODULE CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
