import asyncio
import sys
import os
import time

# Reconfigure utf-8
if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from httpx import AsyncClient, ASGITransport
from main import app
from auth_utils import create_access_token
from database import AsyncSessionLocal
from models_db import LocalDemand, LocalCounterparty, User, LocalPayment, LocalDemandPosition, LocalAssortment
from sqlalchemy import select, func

async def run_full_audit():
    print("=" * 70)
    print("🔍 TO'LIQ AUDIT VA TIZIM TEKSHIRUVI (FULL SYSTEM AUDIT & TEST)")
    print("=" * 70)

    token = create_access_token({"sub": "admin", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    
    passed_steps = 0
    total_steps = 0

    async with AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as client:
        
        # ----------------------------------------------------
        # 1. AUTH & SECURITY AUDIT
        # ----------------------------------------------------
        print("\n🔐 1. AUTH & XAVFSIZLIK AUDITI:")
        
        # Test 1.1: Unauthorized access
        total_steps += 1
        r = await client.get("/api/demands")
        assert r.status_code == 401, f"Security fail: Expected 401, got {r.status_code}"
        print("   ✅ 1.1 Tokensiz so'rovlar to'liq bloklangan (401 Unauthorized)")
        passed_steps += 1

        # Test 1.2: Bad credentials
        total_steps += 1
        r = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code in [400, 401], f"Security fail: Bad login accepted {r.status_code}"
        print("   ✅ 1.2 Noto'g'ri login/parol rad etildi")
        passed_steps += 1

        # Test 1.3: Me endpoint
        total_steps += 1
        r = await client.get("/api/auth/me", headers=headers)
        assert r.status_code == 200, f"/auth/me failed: {r.status_code}"
        user_info = r.json()
        print(f"   ✅ 1.3 /auth/me OK -> user: {user_info.get('username') or user_info.get('data', {}).get('username')}")
        passed_steps += 1

        # ----------------------------------------------------
        # 2. DASHBOARD & ANALYTICS AUDIT
        # ----------------------------------------------------
        print("\n📊 2. DASHBOARD VA ANALITIKA AUDITI:")
        
        # Test 2.1: Summary
        total_steps += 1
        t0 = time.time()
        r = await client.get("/api/dashboard/summary", headers=headers)
        dur = (time.time() - t0) * 1000
        assert r.status_code == 200, f"Summary failed: {r.status_code}"
        dash = r.json().get("data", {})
        print(f"   ✅ 2.1 Dashboard Summary ({dur:.1f}ms): {dash.get('total_demands', 0)} sotuv, Umumiy: {dash.get('total_sales', 0):,.0f} so'm")
        passed_steps += 1

        # Test 2.2: Sales by day
        total_steps += 1
        r = await client.get("/api/dashboard/sales-by-day?days=14", headers=headers)
        assert r.status_code == 200, f"Sales-by-day failed: {r.status_code}"
        sbd = r.json().get("data", [])
        print(f"   ✅ 2.2 14 kunlik savdo dinamikasi: {len(sbd)} kun ma'lumotlari mavjud")
        passed_steps += 1

        # Test 2.3: Organization info
        total_steps += 1
        r = await client.get("/api/dashboard/organization", headers=headers)
        assert r.status_code == 200, f"Organization failed: {r.status_code}"
        org = r.json().get("data", {})
        print(f"   ✅ 2.3 Tashkilot profili: {org.get('name')} (ID: {org.get('id')})")
        passed_steps += 1

        # ----------------------------------------------------
        # 3. CUSTOMERS (MIJOZLAR) AUDIT
        # ----------------------------------------------------
        print("\n👥 3. MIJOZLAR MODULI AUDITI:")
        
        # Test 3.1: Customer listing
        total_steps += 1
        r = await client.get("/api/customers?limit=50", headers=headers)
        assert r.status_code == 200, f"Customers failed: {r.status_code}"
        c_data = r.json()
        cust_list = c_data.get("data", [])
        total_cust = c_data.get("meta", {}).get("size", len(cust_list))
        print(f"   ✅ 3.1 Mijozlar ro'yxati: {len(cust_list)} ta yuklandi (Jami bazada: {total_cust} ta)")
        passed_steps += 1

        # Test 3.2: Customer detail & unpaid demands
        if cust_list:
            total_steps += 1
            cid = cust_list[0]["id"]
            cname = cust_list[0].get("name", "Noma'lum")
            r = await client.get(f"/api/customers/{cid}", headers=headers)
            assert r.status_code == 200, f"Customer detail failed: {r.status_code}"
            cdet = r.json().get("data", {})
            print(f"   ✅ 3.2 Mijoz tafsiloti: '{cname}' -> Balans: {cdet.get('balance', 0):,.0f} so'm, Sotuvlar: {len(cdet.get('demands', []))} ta")
            passed_steps += 1

            total_steps += 1
            r_unpaid = await client.get(f"/api/customers/{cid}/unpaid-demands", headers=headers)
            assert r_unpaid.status_code == 200, f"Unpaid demands failed: {r_unpaid.status_code}"
            unpaid_list = r_unpaid.json().get("data", [])
            print(f"   ✅ 3.3 Mijozning to'lanmagan sotuvlari: {len(unpaid_list)} ta")
            passed_steps += 1

        # Test 3.3: Groups and tags
        total_steps += 1
        r_tags = await client.get("/api/customers/meta/groups-tags", headers=headers)
        if r_tags.status_code != 200:
            r_tags = await client.get("/api/customers/groups-tags", headers=headers)
        assert r_tags.status_code == 200, f"Groups-tags failed: {r_tags.status_code}"
        print(f"   ✅ 3.4 Mijozlar guruhlari va teglari yuklandi")
        passed_steps += 1

        # ----------------------------------------------------
        # 4. DEMANDS (OTGRUZKA / SOTUVLAR) AUDIT
        # ----------------------------------------------------
        print("\n📦 4. SOTUVLAR (OTGRUZKA) MODULI AUDITI:")
        
        # Test 4.1: Demands list
        total_steps += 1
        r_dem = await client.get("/api/demands?limit=50&offset=0", headers=headers)
        assert r_dem.status_code == 200, f"Demands list failed: {r_dem.status_code}"
        dem_data = r_dem.json()
        dem_items = dem_data.get("data", [])
        total_dem = dem_data.get("meta", {}).get("size", len(dem_items))
        print(f"   ✅ 4.1 Sotuvlar ro'yxati: {len(dem_items)} ta yuklandi (Jami bazada: {total_dem} ta)")
        passed_steps += 1

        # Test 4.2: Demands states
        total_steps += 1
        r_states = await client.get("/api/demands/meta/states", headers=headers)
        assert r_states.status_code == 200, f"States failed: {r_states.status_code}"
        states = r_states.json().get("data", [])
        print(f"   ✅ 4.2 Sotuv statuslari: {len(states)} ta status aniqlandi")
        passed_steps += 1

        # Test 4.3: Demand detail & linked payments
        if dem_items:
            total_steps += 1
            target_dem = dem_items[0]
            did = target_dem["id"]
            dname = target_dem.get("name", "Noma'lum")
            r_det = await client.get(f"/api/demands/{did}", headers=headers)
            assert r_det.status_code == 200, f"Demand detail failed: {r_det.status_code}"
            ddet = r_det.json().get("data", {})
            print(f"   ✅ 4.3 Sotuv #{dname} tafsiloti: {len(ddet.get('positions', []))} tovar pozitsiyasi, Bog'langan to'lovlar: {len(ddet.get('linked_payments', []))} ta")
            passed_steps += 1

        # Test 4.4: Indexed Product Search
        total_steps += 1
        t0 = time.time()
        r_srch = await client.get("/api/demands/search/by-product?query=00843", headers=headers)
        dur = (time.time() - t0) * 1000
        assert r_srch.status_code == 200, f"Search by product failed: {r_srch.status_code}"
        s_data = r_srch.json().get("data", {})
        print(f"   ✅ 4.4 Tovarlar bo'yicha tezkor qidiruv ({dur:.1f}ms): {len(s_data.get('assortments', []))} tovar, {len(s_data.get('matched_sales', []))} ta sotuv topildi")
        passed_steps += 1

        # ----------------------------------------------------
        # 5. PAYMENTS & CASHFLOW AUDIT
        # ----------------------------------------------------
        print("\n💰 5. TO'LOVLAR VA KASSA (CASHFLOW) AUDITI:")
        
        # Test 5.1: Cashflow
        total_steps += 1
        r_cf = await client.get("/api/payments/cashflow", headers=headers)
        assert r_cf.status_code == 200, f"Cashflow failed: {r_cf.status_code}"
        cf_data = r_cf.json().get("data", {})
        summary = cf_data.get("summary", {})
        txs = cf_data.get("transactions", [])
        print(f"   ✅ 5.1 Kassa oqimi: {len(txs)} ta operatsiya, Jami kirim: {summary.get('total_inflow', 0):,.0f} so'm, Sof qoldiq: {summary.get('net_balance', 0):,.0f} so'm")
        passed_steps += 1

        # ----------------------------------------------------
        # 6. SETTINGS & CURRENCY AUDIT
        # ----------------------------------------------------
        print("\n⚙️ 6. SOZLAMALAR VA VALYUTA AUDITI:")
        
        # Test 6.1: Currency rates
        total_steps += 1
        r_cur = await client.get("/api/currency", headers=headers)
        assert r_cur.status_code == 200, f"Currency failed: {r_cur.status_code}"
        c_info = r_cur.json().get("data", {})
        print(f"   ✅ 6.1 Dollar kursi: MoySklad = {c_info.get('usd_rate')}, Markaziy Bank = {c_info.get('cbu', {}).get('rate')}")
        passed_steps += 1

        # Test 6.2: Accounts
        total_steps += 1
        r_acc = await client.get("/api/settings/accounts", headers=headers)
        assert r_acc.status_code == 200, f"Accounts failed: {r_acc.status_code}"
        acc_list = r_acc.json().get("data", {}).get("accounts", [])
        print(f"   ✅ 6.2 Hisob raqamlar: {len(acc_list)} ta faol hisob")
        for a in acc_list[:3]:
            print(f"      * {a.get('name')} -> {a.get('current_balance', 0):,.0f} {a.get('currency')}")
        passed_steps += 1

        # Test 6.3: Payment methods
        total_steps += 1
        r_pm = await client.get("/api/settings/payment-methods", headers=headers)
        assert r_pm.status_code == 200, f"Payment methods failed: {r_pm.status_code}"
        pms = r_pm.json().get("data", {}).get("methods", [])
        print(f"   ✅ 6.3 To'lov usullari: {len(pms)} ta usul sozlangan")
        passed_steps += 1

        # ----------------------------------------------------
        # 7. DATABASE INTEGRITY AUDIT
        # ----------------------------------------------------
        print("\n🗄️ 7. MAHALLIY MA'LUMOTLAR BAZASI (SQLITE) BUTUNLIGI AUDITI:")
        async with AsyncSessionLocal() as db:
            total_steps += 1
            user_count = await db.scalar(select(func.count(User.id)))
            assert user_count > 0, "No users in DB"
            print(f"   ✅ 7.1 Foydalanuvchilar jadvali (User): {user_count} ta foydalanuvchi")
            passed_steps += 1

            total_steps += 1
            demand_count = await db.scalar(select(func.count(LocalDemand.id)))
            assert demand_count > 0, "No demands in DB"
            print(f"   ✅ 7.2 Sotuvlar indeksi (LocalDemand): {demand_count} ta yozuv")
            passed_steps += 1

            total_steps += 1
            cust_count = await db.scalar(select(func.count(LocalCounterparty.id)))
            assert cust_count > 0, "No counterparties in DB"
            print(f"   ✅ 7.3 Mijozlar jadvali (LocalCounterparty): {cust_count} ta mijoz keshda")
            passed_steps += 1

            total_steps += 1
            pay_count = await db.scalar(select(func.count(LocalPayment.id)))
            print(f"   ✅ 7.4 To'lovlar indeksi (LocalPayment): {pay_count} ta to'lov")
            passed_steps += 1

            total_steps += 1
            pos_count = await db.scalar(select(func.count(LocalDemandPosition.id)))
            print(f"   ✅ 7.5 Tovar pozitsiyalari indeksi (LocalDemandPosition): {pos_count} ta pozitsiya")
            passed_steps += 1

            total_steps += 1
            assort_count = await db.scalar(select(func.count(LocalAssortment.id)))
            print(f"   ✅ 7.6 Mahsulotlar (LocalAssortment): {assort_count} ta mahsulot")
            passed_steps += 1

    print("\n" + "=" * 70)
    print(f"🎉 AUDIT VA TEST XULOSASI: {passed_steps}/{total_steps} TA BOSQICH 100% MUVAFFAQIYATLI O'TDI!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_full_audit())
