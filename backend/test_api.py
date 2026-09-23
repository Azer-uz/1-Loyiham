import asyncio
import sys
import io

if sys.platform == "win32":
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from moysklad_client import ms_client
from routers.demands import list_demands, get_demand_detail, get_demand_states
from routers.customers import get_customer_unpaid_demands

async def test_all():
    print("🚀 MoySklad Yangi Funksiyalar Testi...")
    try:
        # 1. Statuslar
        print("\n1. MoySklad Sotuv Statuslari:")
        states_resp = await get_demand_states()
        states = states_resp.get("data", [])
        print(f"   Topilgan statuslar soni: {len(states)}")
        for s in states[:5]:
            print(f"   - {s.get('name')} (ID: {s.get('id')})")

        # 2. Sotuvlar ro'yxati (state va remaining bilan)
        print("\n2. Sotuvlar ro'yxati (State & Qarz bilan):")
        demands_resp = await list_demands(limit=3, offset=0)
        demands = demands_resp.get("data", [])
        print(f"   Jami sotuvlar: {demands_resp.get('meta', {}).get('size')} ta")
        for d in demands:
            print(f"   - № {d['name']} | Mijoz: {d['agent_name']} | Sum: {d['sum']:,.0f} | Qarz: {d['remaining']:,.0f} | Status: {d['state_name']} ({d['state_color']})")

        # 3. Sotuv tafsiloti va bog'langan to'lovlar
        if demands:
            target_id = demands[0]["id"]
            print(f"\n3. Sotuv {demands[0]['name']} tafsilotlari & Bog'langan to'lovlar:")
            detail_resp = await get_demand_detail(target_id)
            det = detail_resp.get("data", {})
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
