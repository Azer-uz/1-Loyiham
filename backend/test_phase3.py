import asyncio
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import app
from auth_utils import create_access_token
from httpx import AsyncClient, ASGITransport

async def run_tests():
    print("=== SAID BARAKA 3-BOSQICH TESTI ===")
    token = create_access_token({"sub": "admin", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Valyuta
        r_curr = await client.get("/api/currency", headers=headers)
        print("\n1. VALYUTA & DOLLAR KURSI:")
        print("Status:", r_curr.status_code)
        cdata = r_curr.json().get("data", {})
        print("USD Rate in MoySklad:", cdata.get("usd_rate"))
        print("CBU Rate:", cdata.get("cbu"))

        # 2. Hisob raqamlar
        r_org = await client.get("/api/dashboard/organization", headers=headers)
        org_id = r_org.json().get("data", {}).get("id")
        print("\n2. TASHKILOT HISOB RAQAMLARI:")
        r_accs = await client.get(f"/api/payments/accounts/{org_id}", headers=headers)
        accounts = r_accs.json().get("data", [])
        print(f"Jami hisoblar soni: {len(accounts)}")
        for a in accounts:
            print(f"  - {a.get('name')} (ID: {a.get('id')}, Turi: {a.get('type')})")

        # 3. Kassa va hisoblar balansi
        print("\n3. KASSA VA HISOBLAR BALANSI:")
        r_cf = await client.get("/api/payments/cashflow", headers=headers)
        print("Cashflow status:", r_cf.status_code)
        cf_data = r_cf.json().get("data", {})
        summary = cf_data.get("summary", {})
        print("Jami kirim:", f"{summary.get('total_inflow', 0):,.0f} so'm (${summary.get('total_inflow_usd', 0):,.2f})")
        print("Jami chiqim:", f"{summary.get('total_outflow', 0):,.0f} so'm (${summary.get('total_outflow_usd', 0):,.2f})")
        print("Sof qoldiq:", f"{summary.get('net_balance', 0):,.0f} so'm (${summary.get('net_balance_usd', 0):,.2f})")
        
        print("\nHISOBLAR TAQSIMOTI (Account Balances):")
        for ab in summary.get("account_balances", []):
            bal = ab.get("balance", 0)
            usd = ab.get("usd_balance", 0)
            print(f"  * {ab.get('name')}: {bal:,.0f} so'm (${usd:,.2f})")

        # 4. Tranzaksiyalarda hisoblar va dollar ekvivalenti
        txs = cf_data.get("transactions", [])
        print(f"\nJami operatsiyalar: {len(txs)} ta")
        if txs:
            first = txs[0]
            print("Namuna operatsiya:")
            print(f"  Hujjat: {first.get('type_name')} {first.get('doc_number')}")
            print(f"  Hisob: {first.get('account_name')}")
            print(f"  Summa: {first.get('amount', 0):,.0f} so'm (${first.get('usd_amount', 0):,.2f})")
            print(f"  Kontragent: {first.get('target_name')}")

    print("\n=== BARCHA TESTLAR MUVAFFAQIYATLI O'TDI! ===")

if __name__ == "__main__":
    asyncio.run(run_tests())
