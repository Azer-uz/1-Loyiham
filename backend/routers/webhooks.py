# backend/routers/webhooks.py
from fastapi import APIRouter, Request, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime

from database import get_db
from models_db import LocalDemand, LocalCounterparty, SyncLog
from tasks import sync_all_data
from moysklad_client import ms_client

router = APIRouter()


async def _delete_local_demand(demand_id: str):
    try:
        from database import AsyncSessionLocal
        from models_db import LocalDemand
        from sqlalchemy import delete
        async with AsyncSessionLocal() as session:
            await session.execute(delete(LocalDemand).where(LocalDemand.id == demand_id))
            await session.commit()
            print(f"🗑️ [Webhook] O'chirilgan demand DB dan tozalandi: {demand_id}")
    except Exception as e:
        print(f"⚠️ [Webhook] Demand o'chirishda xato: {e}")

async def _delete_local_payment(payment_id: str):
    try:
        from database import AsyncSessionLocal
        from models_db import LocalPayment
        from sqlalchemy import delete
        async with AsyncSessionLocal() as session:
            await session.execute(delete(LocalPayment).where(LocalPayment.id == payment_id))
            await session.commit()
            print(f"🗑️ [Webhook] O'chirilgan payment DB dan tozalandi: {payment_id}")
    except Exception as e:
        print(f"⚠️ [Webhook] Payment o'chirishda xato: {e}")


@router.post("/moysklad")
async def moysklad_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    MoySklad tizimidan keladigan avtomatik voqealar (Webhook) ni qabul qilish.
    Yangilanish kelishi bilan fonda kesh va lokal DB yangilanadi.
    """
    try:
        payload = await request.json()
        events = payload.get("events", [])
        print(f"🔔 [Webhook] MoySklad'dan xabar keldi ({len(events)} ta voqea)")

        # Keshni tozalash
        ms_client.invalidate_demands_cache()
        ms_client.invalidate_payments_cache()
        ms_client.invalidate_counterparties_cache()

        has_delete = False
        for ev in events:
            action = ev.get("action", "")
            meta = ev.get("meta", {})
            href = meta.get("href", "")
            entity_type = meta.get("type", "")
            entity_id = href.rstrip("/").split("/")[-1] if href else None

            if action == "DELETE" and entity_id:
                has_delete = True
                if entity_type == "demand":
                    background_tasks.add_task(_delete_local_demand, entity_id)
                elif entity_type in ["paymentin", "cashin"]:
                    background_tasks.add_task(_delete_local_payment, entity_id)

        # Orqa fonda barcha ma'lumotlarni tezkor yangilash
        background_tasks.add_task(sync_all_data)

        return {"status": "ok", "message": "Webhook qabul qilindi va fonda yangilanishga yuborildi"}
    except Exception as e:
        print(f"⚠️ Webhook parse xatosi: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/sync-now")
async def trigger_manual_sync():
    """Qo'lda darhol sinxronizatsiyani ishga tushirish (yangi sotuvlarni bir lahzada olib keladi)"""
    ms_client.invalidate_demands_cache()
    ms_client.invalidate_payments_cache()
    ms_client.invalidate_counterparties_cache()
    res = await sync_all_data(force_full=False)
    count = res.get("count", 0) if isinstance(res, dict) else 0
    return {"success": True, "count": count, "message": "MoySklad bilan sinxronlandi"}


@router.get("/status")
async def get_sync_status(db: AsyncSession = Depends(get_db)):
    """Oxirgi sinxronizatsiyalar va DB holati"""
    demands_count_res = await db.execute(select(func.count(LocalDemand.id)))
    demands_count = demands_count_res.scalar() or 0

    cp_count_res = await db.execute(select(func.count(LocalCounterparty.id)))
    cp_count = cp_count_res.scalar() or 0

    latest_log_res = await db.execute(
        select(SyncLog).order_by(SyncLog.id.desc()).limit(1)
    )
    latest_log = latest_log_res.scalars().first()

    return {
        "success": True,
        "data": {
            "local_demands_count": demands_count,
            "local_counterparties_count": cp_count,
            "last_synced_at": latest_log.created_at.strftime("%Y-%m-%d %H:%M:%S") if latest_log else "Hali sinxronlanmagan",
            "last_status": latest_log.status if latest_log else "none",
            "last_message": latest_log.message if latest_log else "",
        }
    }
