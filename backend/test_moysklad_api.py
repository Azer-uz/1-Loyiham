import asyncio
import os
import sys

# Append backend path
sys.path.append(os.path.abspath('.'))

from moysklad_client import MoySkladClient

async def main():
    client = MoySkladClient()
    
    try:
        # 1. Get USD account
        orgs = await client.get_organization()
        org_id = orgs[0]['id']
        org_meta = orgs[0]['meta']
        
        accounts = await client._request("GET", f"/entity/organization/{org_id}/accounts")
        print("Accounts:", accounts.get('rows', []))
        
        usd_account = None
        uzs_account = None
        for acc in accounts.get('rows', []):
            if 'Dollar' in acc.get('name', '') or 'USD' in acc.get('name', ''):
                usd_account = acc
            else:
                uzs_account = acc
                
        print(f"USD account: {usd_account}")
        
        # 2. Test expenseitem metadata
        try:
            expense_meta = await client._request("GET", "/entity/expenseitem")
            print("Expense items:", [{"name": e['name'], "meta": e['meta']} for e in expense_meta.get('rows', [])])
        except Exception as e:
            print("Expense item error:", e)

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
