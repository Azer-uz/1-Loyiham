import asyncio
import sys
import io
import os

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from auth_utils import create_access_token
from httpx import AsyncClient, ASGITransport

async def test_all():
    print("🚀 MoySklad API Funksiyalar Testi...")
    token = create_access_token({"sub": "admin", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            # 1. Statuslar
            print("\n1. MoySklad Sotuv Statuslari:")
            r_states = await client.get("/api/demands/meta/states", headers=headers)
            assert r_states.status_code == 200, f"Status failed: {r_states.status_code}"
            states = r_states.json().get("data", [])
            print(f"   Topilgan statuslar soni: {len(states)}")
            for s in states[:5]:
                print(f"   - {s.get('name')} (ID: {s.get('id')})")

            # 2. Sotuvlar ro'yxati (state va remaining bilan)
            print("\n2. Sotuvlar ro'yxati (State & Qarz bilan):")
            r_demands = await client.get("/api/demands?limit=3&offset=0", headers=headers)
            assert r_demands.status_code == 200, f"Demands failed: {r_demands.status_code}"
            demands_resp = r_demands.json()
            demands = demands_resp.get("data", [])
            print(f"   Jami sotuvlar: {demands_resp.get('meta', {}).get('size')} ta")
            for d in demands:
                print(f"   - № {d['name']} | Mijoz: {d['agent_name']} | Sum: {d['sum']:,.0f} | Qarz: {d['remaining']:,.0f} | Status: {d.get('state_name', 'Noma\'lum')}")

            # 3. Sotuv tafsiloti va bog'langan to'lovlar
            if demands:
                target_id = demands[0]["id"]
                print(f"\n3. Sotuv {demands[0]['name']} tafsilotlari:")
                r_det = await client.get(f"/api/demands/{target_id}", headers=headers)
                assert r_det.status_code == 200, f"Demand detail failed: {r_det.status_code}"
                det = r_det.json().get("data", {})
                print(f"   Status: {det.get('state_name')} ({det.get('state_color')})")
                print(f"   Tovarlar: {len(det.get('positions', []))} ta")
                print(f"   Bog'langan to'lovlar: {len(det.get('linked_payments', []))} ta")

            print("\n✅ Barcha testlar muvaffaqiyatli o'tdi!")
        except Exception as e:
            print(f"\n❌ Testda xato: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_all())
