import httpx
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("=" * 65)
    print("🚀 CHUQUR TIZIM DIAGNOSTIKASI VA TEKSHIRUV SINOVLARI")
    print("=" * 65)

    all_passed = True

    # 1. Health check
    r = httpx.get(f"{BASE_URL}/health")
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    print(f"✅ 1. Health check: 200 OK -> {r.json()}")

    # 2. Clean routes check (/login, /demands, /)
    r_login_page = httpx.get(f"{BASE_URL}/login")
    assert r_login_page.status_code == 200, f"/login failed: {r_login_page.status_code}"
    assert "Tizimga Kirish" in r_login_page.text, "login.html content not matched"
    print(f"✅ 2. /login sahifasi mavjud: 200 OK (uzunligi: {len(r_login_page.text)} bayt)")

    r_dem_page = httpx.get(f"{BASE_URL}/demands")
    assert r_dem_page.status_code == 200, f"/demands failed: {r_dem_page.status_code}"
    print(f"✅ 3. /demands sahifasi mavjud: 200 OK")

    # 4. Auth protection on business endpoints (MUST BE 401 UNAUTHORIZED WITHOUT TOKEN)
    r_unauth_demands = httpx.get(f"{BASE_URL}/api/demands?limit=10")
    assert r_unauth_demands.status_code == 401, f"Expected 401, got {r_unauth_demands.status_code}"
    print(f"✅ 4. Tokensiz /api/demands so'rovi himoyalangan: 401 Unauthorized (To'g'ri!)")

    r_unauth_dash = httpx.get(f"{BASE_URL}/api/dashboard/summary")
    assert r_unauth_dash.status_code == 401, f"Expected 401, got {r_unauth_dash.status_code}"
    print(f"✅ 5. Tokensiz /api/dashboard/summary so'rovi himoyalangan: 401 Unauthorized (To'g'ri!)")

    # 5. Invalid login test
    r_bad = httpx.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert r_bad.status_code == 400, f"Expected 400, got {r_bad.status_code}"
    print(f"✅ 6. Noto'g'ri parol bilan kirish rad etildi: 400 Bad Request")

    # 6. Valid login test
    r_login = httpx.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r_login.status_code == 200, f"Login failed: {r_login.status_code}"
    token = r_login.json().get("access_token")
    assert token, "Token topilmadi"
    headers = {"Authorization": f"Bearer {token}"}
    print(f"✅ 7. To'g'ri login (admin/admin123): 200 OK, token olindi")

    # 7. Token validation via /api/auth/me
    r_me = httpx.get(f"{BASE_URL}/api/auth/me", headers=headers)
    assert r_me.status_code == 200, f"/auth/me failed: {r_me.status_code}"
    user_obj = r_me.json().get('data', {}) or r_me.json().get('user', {})
    print(f"✅ 8. /api/auth/me token tekshiruvi: 200 OK -> user: {user_obj.get('username')}")

    # 8. Demands metadata (states) — MUST NOT HANG!
    t0 = time.time()
    r_states = httpx.get(f"{BASE_URL}/api/demands/meta/states", headers=headers)
    el_states = time.time() - t0
    assert r_states.status_code == 200, f"States failed: {r_states.status_code}"
    states_data = r_states.json().get("data", [])
    assert len(states_data) > 0, "States bo'sh"
    print(f"✅ 9. Sotuv statuslari (States): 200 OK in {el_states:.4f}s (hech qanday qotish yo'q, {len(states_data)} ta status)")

    # 9. Demands with TODAY filter
    today = "2026-09-16"
    t0 = time.time()
    r_dem_today = httpx.get(f"{BASE_URL}/api/demands?limit=50&offset=0&date_from={today}&date_to={today}", headers=headers)
    el_today = time.time() - t0
    assert r_dem_today.status_code == 200, f"Demands today failed: {r_dem_today.status_code}"
    res_today = r_dem_today.json()
    print(f"✅ 10. Bugungi sotuvlar ro'yxati: 200 OK in {el_today:.4f}s")
    print(f"     Manba: {res_today.get('meta', {}).get('source')}, topilgan: {res_today.get('meta', {}).get('size')} ta")
    for d in res_today.get("data", [])[:2]:
        print(f"     -> {d['name']} | Mijoz: {d['agent_name']} | Sum: {d['sum']:,.0f} | Qarz: {d['remaining']:,.0f} | Holat: {d['state_name']}")

    # 10. Dashboard summary (Local DB optimization)
    t0 = time.time()
    r_dash = httpx.get(f"{BASE_URL}/api/dashboard/summary?date_from={today}&date_to={today}", headers=headers)
    el_dash = time.time() - t0
    assert r_dash.status_code == 200, f"Dashboard summary failed: {r_dash.status_code}"
    dash_data = r_dash.json().get("data", {})
    print(f"✅ 11. Dashboard summary: 200 OK in {el_dash:.4f}s (tezkor mahalliy DB)")
    print(f"     Umumiy savdo: {dash_data.get('total_sales'):,.0f} so'm ({dash_data.get('total_demands')} ta sotuv)")
    print(f"     To'langan: {dash_data.get('cash_payments'):,.0f} so'm | Qarz: {dash_data.get('debt_payments'):,.0f} so'm")
    print(f"     Top mijozlar soni: {len(dash_data.get('top_customers', []))}")

    # 11. Dashboard sales-by-day (7 days)
    t0 = time.time()
    r_sbd = httpx.get(f"{BASE_URL}/api/dashboard/sales-by-day?days=7", headers=headers)
    el_sbd = time.time() - t0
    assert r_sbd.status_code == 200, f"Sales-by-day failed: {r_sbd.status_code}"
    print(f"✅ 12. 7 kunlik savdo dinamikasi: 200 OK in {el_sbd:.4f}s ({len(r_sbd.json().get('data', []))} kun)")

    # 12. Organization endpoint
    t0 = time.time()
    r_org = httpx.get(f"{BASE_URL}/api/dashboard/organization", headers=headers)
    el_org = time.time() - t0
    assert r_org.status_code == 200, f"Organization failed: {r_org.status_code}"
    print(f"✅ 13. Tashkilot ma'lumotlari: 200 OK in {el_org:.4f}s -> {r_org.json().get('data', {}).get('name')}")

    print("\n" + "=" * 65)
    print("🎉 BARCHA 13 TA CHUQUR TESTLAR 100% MUVAFFAQIYATLI O'TDI!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
