import httpx
import sys
import io

if sys.platform == "win32":
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_URL = "http://127.0.0.1:8000"

def test():
    # 0. Login
    login_r = httpx.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = login_r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test payment methods
    r_methods = httpx.get(f"{BASE_URL}/api/settings/payment-methods", headers=headers)
    print("PAYMENT METHODS STATUS:", r_methods.status_code)
    mdata = r_methods.json().get("data", {})
    for m in mdata.get("methods", []):
        print(f"  Method: {m['name']} | Currency: {m['currency']} | Active: {m['is_active']} | Linked: {len(m.get('linked_account_ids', []))} ta hisob")

    # 2. Test accounts with corrections
    r_accs = httpx.get(f"{BASE_URL}/api/settings/accounts", headers=headers)
    print("\nACCOUNTS STATUS:", r_accs.status_code)
    adata = r_accs.json().get("data", {})
    print("  Total UZS balance:", f"{adata.get('total_uzs_balance', 0.0):,.0f} so'm")
    print("  Total USD balance:", f"${adata.get('total_usd_balance', 0.0):,.2f}")
    print("  Consolidated UZS equivalent:", f"{adata.get('consolidated_uzs_equivalent', 0.0):,.0f} so'm")

    for a in adata.get("accounts", []):
        cur = a.get("currency")
        bal = a.get("current_balance", 0.0)
        if cur == "USD":
            print(f"  -> {a.get('name')}: ${bal:,.2f}")
        else:
            print(f"  -> {a.get('name')}: {bal:,.0f} so'm")

    # 3. Test adjustment
    r_adj = httpx.post(f"{BASE_URL}/api/settings/accounts/adjust-balance", headers=headers, json={
        "account_id": "cash_default",
        "new_balance": 585000000.0,
        "reason": "Kassa sanash testi"
    })
    print("\nADJUST STATUS:", r_adj.status_code, r_adj.json().get("message"))

    # Re-check updated account
    r_accs2 = httpx.get(f"{BASE_URL}/api/settings/accounts", headers=headers)
    for a in r_accs2.json().get("data", {}).get("accounts", []):
        if a["id"] == "cash_default":
            print(f"  Updated cash_default balance: {a['current_balance']:,.0f} so'm | has_correction: {a['has_correction']}")

    print("\n🎉 test_settings.py muvaffaqiyatli yakunlandi!")

if __name__ == "__main__":
    test()
