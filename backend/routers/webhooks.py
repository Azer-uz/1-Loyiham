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


@router.post("/moysklad")
async def moysklad_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    MoySklad tizimidan keladigan avtomatik voqealar (Webhook) ni qabul qilish.
    Yangilanish kelishi bilan fonda kesh va lokal DB yangilanadi.
    """
    try:
        payload = await request.json()
        print(f"🔔 [Webhook] MoySklad'dan xabar keldi: {payload.get('events', [])}")

        # Keshni tozalash
        ms_client.invalidate_demands_cache()
        ms_client.invalidate_payments_cache()
        ms_client.invalidate_counterparties_cache()

        # Orqa fonda ma'lumotlarni yangilash
        background_tasks.add_task(sync_all_data)

        return {"status": "ok", "message": "Webhook qabul qilindi va fonda yangilanishga yuborildi"}
    except Exception as e:
        print(f"⚠️ Webhook parse xatosi: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/sync-now")
async def trigger_manual_sync(background_tasks: BackgroundTasks):
    """Qo'lda darhol sinxronizatsiyani ishga tushirish"""
    ms_client.invalidate_demands_cache()
    ms_client.invalidate_payments_cache()
    ms_client.invalidate_counterparties_cache()
    background_tasks.add_task(sync_all_data)
    return {"success": True, "message": "Sinxronizatsiya orqa fonda boshlandi"}


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
