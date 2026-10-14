# backend/register_webhooks.py
import asyncio
from moysklad_client import ms_client

WEBHOOK_TARGET_URL = "https://said-baraka.uz/api/webhooks/moysklad"

ACTIONS_ENTITIES = [
    ("demand", ["CREATE", "UPDATE", "DELETE"]),
    ("paymentin", ["CREATE", "UPDATE", "DELETE"]),
    ("cashin", ["CREATE", "UPDATE", "DELETE"]),
    ("counterparty", ["CREATE", "UPDATE"]),
]

async def ensure_webhooks():
    """MoySklad tizimida barcha zaruriy webhooklarni tekshirish va ro'yxatdan o'tkazish"""
    try:
        existing_resp = await ms_client._request("GET", "/entity/webhook")
        existing_rows = existing_resp.get("rows", [])
        print(f"🔍 MoySklad da mavjud webhooklar soni: {len(existing_rows)}")

        existing_set = set()
        for w in existing_rows:
            url = w.get("url", "")
            action = w.get("action", "")
            entity = w.get("entityType", "")
            existing_set.add((entity, action, url))

        registered_count = 0
        for entity, actions in ACTIONS_ENTITIES:
            for action in actions:
                key = (entity, action, WEBHOOK_TARGET_URL)
                if key not in existing_set:
                    payload = {
                        "url": WEBHOOK_TARGET_URL,
                        "action": action,
                        "entityType": entity,
                        "enabled": True
                    }
                    try:
                        res = await ms_client._request("POST", "/entity/webhook", json_data=payload)
                        print(f"✅ Webhook qo'shildi: {entity} -> {action} ({res.get('id')})")
                        registered_count += 1
                    except Exception as err:
                        print(f"⚠️ Webhook qo'shishda xato ({entity}:{action}): {err}")
                else:
                    print(f"ℹ️ Webhook allaqachon mavjud: {entity} -> {action}")

        print(f"🎉 Webhooklar tekshiruvi tugadi. Yangi qo'shilgan: {registered_count}")
        return True
    except Exception as e:
        print(f"❌ Webhooklarni tekshirishda xato: {e}")
        return False

if __name__ == "__main__":
    async def main():
        await ensure_webhooks()
        await ms_client.close()
    asyncio.run(main())
