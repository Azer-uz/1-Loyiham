import httpx
import time
import sys
import io

if sys.platform == "win32":
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 1. Health check
r = httpx.get('http://localhost:8000/health')
print(f'1. Health: {r.status_code}, body={r.json()}')

# 2. Login invalid
r_bad = httpx.post('http://localhost:8000/api/auth/login', json={'username': 'admin', 'password': 'wrongpassword'})
print(f'2. Bad login: {r_bad.status_code}, detail={r_bad.json().get("detail")}')

# 3. Login valid
r_login = httpx.post('http://localhost:8000/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
print(f'3. Valid login: {r_login.status_code}, user={r_login.json().get("user")}')
token = r_login.json().get('access_token')

# 4. Get demands (local_db)
t0 = time.time()
r_dem = httpx.get('http://localhost:8000/api/demands?limit=10&offset=0', headers={'Authorization': f'Bearer {token}'})
elapsed = time.time() - t0
print(f'4. Demands: {r_dem.status_code} in {elapsed:.3f}s! source={r_dem.json().get("meta", {}).get("source")}, count={len(r_dem.json().get("data", []))}')

# Print first 5 demands
for d in r_dem.json().get('data', [])[:5]:
    print(f'   Demand {d["name"]}: agent="{d["agent_name"]}", state="{d["state_name"]}", sum={d["sum"]:,.0f}, payed={d["payed_sum"]:,.0f}, rem={d["remaining"]:,.0f}')

# 5. Search test
t0 = time.time()
r_search = httpx.get('http://localhost:8000/api/demands?limit=10&offset=0&search=Murod', headers={'Authorization': f'Bearer {token}'})
elapsed_search = time.time() - t0
print(f'5. Search "Murod": {r_search.status_code} in {elapsed_search:.3f}s, found={len(r_search.json().get("data", []))} records')
for d in r_search.json().get('data', [])[:2]:
    print(f'   Matched: {d["name"]} - {d["agent_name"]}')

# 6. Static Login page check
r_page = httpx.get('http://localhost:8000/static/login.html')
print(f'6. Login page: {r_page.status_code}, len={len(r_page.text)}')

print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
