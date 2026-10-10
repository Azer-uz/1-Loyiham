# backend/tasks.py
import asyncio
import time
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import AsyncSessionLocal
from models_db import LocalDemand, LocalPayment, LocalCounterparty, LocalAssortment, SyncLog, SyncQueue, AppSetting
from moysklad_client import ms_client
import json

scheduler = AsyncIOScheduler()
_sync_lock = asyncio.Lock()


def extract_id_from_href(href: str) -> str:
    if not href:
        return ""
    return href.rstrip("/").split("/")[-1]


def color_int_to_hex(color_int, state_name: str = "") -> str:
    if color_int and color_int > 0:
        return f"#{color_int:06x}"
    name_lower = (state_name or "").lower()
    if "договор" in name_lower or "kelish" in name_lower:
        return "#3b82f6"
    if "собран" in name_lower or "yig" in name_lower:
        return "#f59e0b"
    if "пути" in name_lower or "yo'l" in name_lower:
        return "#8b5cf6"
    if "магазин" in name_lower or "magazin" in name_lower:
        return "#06b6d4"
    if "закр" in name_lower or "yopil" in name_lower:
        return "#10b981"
    if "отмен" in name_lower or "bekor" in name_lower:
        return "#ef4444"
    return "#64748b"


async def sync_all_data(force_full: bool = False):
    """
    MoySklad ma'lumotlarini lokal SQLite DB ga sinxronlash:
    - Boshida (yoki force_full=True bo'lsa) butun arxivdagi barcha sotuvlar sana cheklovisiz to'liq yuklanadi.
    - Keyingi davriy sinxronizatsiyalarda esa faqat oxirgi o'zgargan (updated>=...) sotuvlar tezkor yangilanadi.
    """
    if _sync_lock.locked():
        print("⏳ Sinxronizatsiya allaqachon bajarilmoqda, keyingi navbat kutiladi...")
        return {"status": "busy", "message": "Sinxronizatsiya allaqachon ketmoqda"}

    async with _sync_lock:
        start_time = time.time()
        
        # Baza holatini tekshirish: to'liq arxiv olinganmi va oxirgi sync qachon bo'lgan?
        is_full_done = False
        last_sync_time_str = None
        try:
            async with AsyncSessionLocal() as db_check:
                full_done_setting = await db_check.scalar(select(AppSetting).where(AppSetting.key == "demands_full_sync_completed"))
                last_sync_setting = await db_check.scalar(select(AppSetting).where(AppSetting.key == "demands_last_sync_time"))
                is_full_done = (full_done_setting and full_done_setting.value == "true")
                if last_sync_setting and last_sync_setting.value:
                    last_sync_time_str = last_sync_setting.value
        except Exception as e:
            print(f"⚠️ AppSetting tekshirishda xato: {e}")

        # Agar majburiy to'liq sync so'ralgan bo'lsa yoki baza hali to'liq yuklanmagan bo'lsa
        do_full_archive_sync = force_full or (not is_full_done)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if do_full_archive_sync:
            print("🔄 [Sync: TO'LIQ ARXIV] Barcha sotuvlar sana cheklovisiz MoySklad dan to'liq yuklanmoqda...")
        else:
            # Incremental sync: oxirgi sinxronizatsiya vaqtidan boshlab (15 daqiqa bufer bilan)
            if last_sync_time_str:
                try:
                    last_dt = datetime.strptime(last_sync_time_str[:19], "%Y-%m-%d %H:%M:%S")
                    updated_from_str = (last_dt - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    updated_from_str = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            else:
                updated_from_str = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            print(f"🔄 [Sync: INCREMENTAL] Faqat o'zgargan sotuvlar yangilanmoqda (updated>={updated_from_str})...")

        try:
            # Demands: Paginatsiya bilan sotuvlarni olish
            async def fetch_demands_paginated():
                all_demands = []
                demand_offset = 0
                demand_page_limit = 100
                is_fully_fetched = False
                while True:
                    try:
                        if do_full_archive_sync:
                            # TO'LIQ: sana filtrisiz, barcha sotuvlar
                            page_resp = await ms_client.get_demands(
                                limit=demand_page_limit,
                                offset=demand_offset,
                                order="moment,desc",
                            )
                        else:
                            # INCREMENTAL: faqat o'zgarganlar (updated)
                            page_resp = await ms_client.get_demands(
                                limit=demand_page_limit,
                                offset=demand_offset,
                                updated_from=updated_from_str,
                                order="updated,desc",
                            )

                        if isinstance(page_resp, Exception):
                            print(f"❌ [Sync Error Demands page {demand_offset}] {page_resp}")
                            break
                        page_rows = page_resp.get("rows", [])
                        all_demands.extend(page_rows)
                        meta_size = page_resp.get("meta", {}).get("size", 0)
                        print(f"📦 [Sync] Demands sahifa: offset={demand_offset}, olindi={len(page_rows)}, jami API da={meta_size}")
                        if len(page_rows) < demand_page_limit or len(all_demands) >= meta_size:
                            is_fully_fetched = (len(all_demands) >= meta_size)
                            break
                        demand_offset += demand_page_limit
                    except Exception as e:
                        print(f"❌ [Sync Error Demands page {demand_offset}] {e}")
                        break
                return all_demands, is_fully_fetched

            demands_task = fetch_demands_paginated()
            payments_task = ms_client.get_all_payments_cached()
            counterparties_task = ms_client.get_all_counterparties_cached()
            metadata_task = ms_client.get_demand_metadata()
            cp_metadata_task = ms_client.get_counterparty_metadata()
            groups_task = ms_client._request("GET", "/entity/group")
            balances_task = ms_client.get_all_balances()
            assortments_task = ms_client.get_all_assortments()

            demands_res, all_payments, counterparties, meta_resp, cp_meta_resp, groups_resp, balances, assortments_resp = await asyncio.gather(
                demands_task, payments_task, counterparties_task, metadata_task, cp_metadata_task, groups_task, balances_task, assortments_task, return_exceptions=True
            )

            if isinstance(demands_res, tuple):
                raw_demands, is_fully_synced = demands_res
            elif isinstance(demands_res, list):
                raw_demands, is_fully_synced = demands_res, False
            else:
                print(f"❌ [Sync Error Demands] {demands_res}")
                raw_demands, is_fully_synced = [], False
            if isinstance(all_payments, Exception):
                print(f"❌ [Sync Error Payments] {all_payments}")
                return {"status": "error", "message": str(all_payments)}
            if isinstance(counterparties, Exception):
                counterparties = []
            if isinstance(meta_resp, Exception):
                meta_resp = {}
            if isinstance(cp_meta_resp, Exception):
                cp_meta_resp = {}
            if isinstance(groups_resp, Exception) or not isinstance(groups_resp, dict):
                groups_resp = {}
            cashins = all_payments.get("cashins", [])
            paymentins = all_payments.get("paymentins", [])
            if isinstance(assortments_resp, list):
                raw_assortments = assortments_resp
            elif isinstance(assortments_resp, dict):
                raw_assortments = assortments_resp.get("rows", [])
            else:
                raw_assortments = []

            # Kengaytirilgan xaritalar (Agent, State va Guruh nomlarini tezkor topish)
            cp_map = {c.get("id"): c.get("name", "Noma'lum") for c in counterparties if isinstance(c, dict) and c.get("id")}
            state_map = {}
            for s in meta_resp.get("states", []):
                sid = s.get("id") or extract_id_from_href(s.get("meta", {}).get("href", ""))
                if sid:
                    state_map[sid] = {
                        "name": s.get("name", "—"),
                        "color": s.get("color", 0),
                        "href": s.get("meta", {}).get("href", ""),
                    }

            cp_state_map = {}
            for s in cp_meta_resp.get("states", []):
                sid = s.get("id") or extract_id_from_href(s.get("meta", {}).get("href", ""))
                if sid:
                    cp_state_map[sid] = s.get("name", "")

            group_map = {}
            for g in groups_resp.get("rows", []):
                gid = g.get("id") or extract_id_from_href(g.get("meta", {}).get("href", ""))
                if gid and g.get("name"):
                    group_map[gid] = g["name"]

            # To'lovlarni hisoblash (MoySklad'ning o'zini native 'payedSum' ishlatiladi)
            # Endi bu yerda to'lovlarni qo'lda qidirib mapping qilish shart emas.

            # DB ga tezkor yozish (barcha yozuvlarni 1 marta tekshirib olish)
            async with AsyncSessionLocal() as db:
                existing_demands = {d.id: d for d in (await db.execute(select(LocalDemand))).scalars().all()}
                existing_cps = {c.id: c for c in (await db.execute(select(LocalCounterparty))).scalars().all()}
                existing_payments = {p.id: p for p in (await db.execute(select(LocalPayment))).scalars().all()}

                # LocalDemands ni yangilash
                processed_demand_ids = set()
                for d in raw_demands:
                    did = d.get("id")
                    if not did:
                        continue
                    processed_demand_ids.add(did)
                    existing = existing_demands.get(did)
                    raw_agent_name = (agent.get("name") if isinstance(agent, dict) else None) or cp_map.get(agent_id)
                    if not raw_agent_name or raw_agent_name == "Noma'lum":
                        agent_name = existing.agent_name if (existing and existing.agent_name and existing.agent_name != "Noma'lum") else "Noma'lum"
                    else:
                        agent_name = raw_agent_name

                    state = d.get("state", {}) if isinstance(d.get("state"), dict) else {}
                    state_href = state.get("meta", {}).get("href", "")
                    state_id = extract_id_from_href(state_href)
                    matched_state = state_map.get(state_id, {})
                    state_name = state.get("name") or matched_state.get("name", "—")
                    state_color = color_int_to_hex(matched_state.get("color"), state_name)

                    demand_sum = d.get("sum", 0) / 100.0
                    payed_sum = d.get("payedSum", 0) / 100.0
                    remaining = max(0.0, demand_sum - payed_sum)

                    if remaining <= 0.01:
                        payment_status = "paid"
                        payment_status_name = "To'langan"
                    elif payed_sum > 0:
                        payment_status = "partial"
                        payment_status_name = "Qisman"
                    else:
                        payment_status = "unpaid"
                        payment_status_name = "To'lanmagan"

                    existing = existing_demands.get(did)
                    if existing:
                        existing.name = d.get("name", "")
                        existing.moment = d.get("moment", "")
                        existing.sum = demand_sum
                        existing.payed_sum = payed_sum
                        existing.remaining = remaining
                        existing.payment_status = payment_status
                        existing.payment_status_name = payment_status_name
                        existing.state_name = state_name
                        existing.state_color = state_color
                        existing.state_id = state_id
                        existing.state_href = state_href or matched_state.get("href", "")
                        existing.agent_name = agent_name
                        existing.agent_id = agent_id
                        existing.description = d.get("description", "") or ""
                    else:
                        new_d = LocalDemand(
                            id=did,
                            name=d.get("name", ""),
                            moment=d.get("moment", ""),
                            sum=demand_sum,
                            payed_sum=payed_sum,
                            remaining=remaining,
                            payment_status=payment_status,
                            payment_status_name=payment_status_name,
                            state_name=state_name,
                            state_color=state_color,
                            state_id=state_id,
                            state_href=state_href or matched_state.get("href", ""),
                            agent_name=agent_name,
                            agent_id=agent_id,
                            description=d.get("description", "") or "",
                        )
                        db.add(new_d)

                # Orphan deletion: FAQAT to'liq arxiv sync bo'lib, butun baza 100% olingandagina
                if do_full_archive_sync and is_fully_synced and len(raw_demands) > 500:
                    for did, d_obj in existing_demands.items():
                        if did not in processed_demand_ids:
                            await db.delete(d_obj)

                # LocalCounterparty ni yangilash
                for cp in counterparties:
                    cpid = cp.get("id")
                    if not cpid:
                        continue
                    existing_cp = existing_cps.get(cpid)
                    balance = balances.get(cpid, 0.0) if isinstance(balances, dict) else 0.0

                    tags = cp.get("tags", [])
                    g_obj = cp.get("group", {})
                    gid = g_obj.get("id") or (extract_id_from_href(g_obj.get("meta", {}).get("href", "")) if isinstance(g_obj, dict) and g_obj.get("meta") else "")
                    g_name = group_map.get(gid, "")
                    group_val = ", ".join(tags) if tags else (g_name or "Основной")

                    state_obj = cp.get("state", {})
                    sid = state_obj.get("id") or (extract_id_from_href(state_obj.get("meta", {}).get("href", "")) if isinstance(state_obj, dict) and state_obj.get("meta") else "")
                    status_val = state_obj.get("name") or cp_state_map.get(sid, "") or "Новый"

                    if existing_cp:
                        existing_cp.name = cp.get("name", "")
                        existing_cp.phone = cp.get("phone", "") or ""
                        existing_cp.group = group_val
                        existing_cp.status = status_val
                        # Agar balances API dan kelgan bo'lsa (bo'sh bo'lmasa), shuni ishlatamiz
                        if balances and len(balances) > 0:
                            existing_cp.balance = balances.get(cpid, 0.0)
                    else:
                        db.add(LocalCounterparty(
                            id=cpid,
                            name=cp.get("name", ""),
                            phone=cp.get("phone", "") or "",
                            balance=balances.get(cpid, 0.0) if balances and len(balances) > 0 else 0.0,
                            group=group_val,
                            status=status_val,
                        ))

                # LocalPayment larni yangilash
                processed_pids = set()
                def process_payment(p_doc, p_type):
                    pid = p_doc.get("id")
                    if not pid:
                        return
                    processed_pids.add(pid)
                    agent = p_doc.get("agent", {})
                    agent_href = agent.get("meta", {}).get("href", "") if isinstance(agent, dict) else ""
                    agent_id = extract_id_from_href(agent_href)

                    rate_obj = p_doc.get("rate") or {}
                    rate_val = float(rate_obj.get("value") or 0.0)
                    curr_href = rate_obj.get("currency", {}).get("meta", {}).get("href", "")
                    is_usd = bool("45062adb" in curr_href or "usd" in curr_href.lower() or rate_val > 1)
                    raw_sum = p_doc.get("sum", 0) / 100.0

                    usd_amt = raw_sum if is_usd else 0.0
                    sum_uzs = (usd_amt * rate_val) if is_usd else raw_sum

                    ops = p_doc.get("operations", [])
                    if isinstance(ops, dict):
                        ops = ops.get("rows", [])
                    linked_did = ""
                    if isinstance(ops, list) and ops:
                        for op in ops:
                            if isinstance(op, dict):
                                op_href = op.get("meta", {}).get("href", "")
                                if "/entity/demand/" in op_href:
                                    linked_did = extract_id_from_href(op_href)
                                    break
                    if not linked_did and isinstance(p_doc.get("demand"), dict):
                        d_href = p_doc.get("demand", {}).get("meta", {}).get("href", "")
                        if "/entity/demand/" in d_href:
                            linked_did = extract_id_from_href(d_href)

                    existing_p = existing_payments.get(pid)
                    if existing_p:
                        existing_p.type = p_type
                        existing_p.name = p_doc.get("name", "")
                        existing_p.sum = sum_uzs
                        existing_p.moment = p_doc.get("moment", "")
                        existing_p.demand_id = linked_did
                        existing_p.agent_id = agent_id
                        existing_p.purpose = p_doc.get("paymentPurpose", "") or ""
                        existing_p.is_usd = is_usd
                        existing_p.usd_amount = usd_amt
                        existing_p.usd_rate = rate_val
                    else:
                        db.add(LocalPayment(
                            id=pid,
                            type=p_type,
                            name=p_doc.get("name", ""),
                            sum=sum_uzs,
                            moment=p_doc.get("moment", ""),
                            demand_id=linked_did,
                            agent_id=agent_id,
                            purpose=p_doc.get("paymentPurpose", "") or "",
                            is_usd=is_usd,
                            usd_amount=usd_amt,
                            usd_rate=rate_val,
                        ))

                for c in cashins:
                    process_payment(c, "cash")
                for p in paymentins:
                    process_payment(p, "card")

                # Delete orphaned payments
                if len(cashins) + len(paymentins) > 0:
                    for pid, p_obj in existing_payments.items():
                        if pid not in processed_pids:
                            await db.delete(p_obj)

                # LocalAssortment ni yangilash
                existing_assortments = {a.id: a for a in (await db.execute(select(LocalAssortment))).scalars().all()}
                processed_assortment_ids = set()
                
                for item in raw_assortments:
                    item_id = item.get("id")
                    if not item_id: continue
                    processed_assortment_ids.add(item_id)
                    
                    price = 0
                    if item.get("salePrices") and len(item.get("salePrices", [])) > 0:
                        price = item["salePrices"][0].get("value", 0) / 100.0
                    elif item.get("salePrice"):
                        price = item.get("salePrice", 0) / 100.0
                        
                    barcodes = item.get("barcodes", [])
                    barcode = ""
                    if barcodes:
                        bc = barcodes[0]
                        if isinstance(bc, dict) and bc:
                            barcode = str(list(bc.values())[0])
                        else:
                            barcode = str(bc)
                    
                    existing_a = existing_assortments.get(item_id)
                    if existing_a:
                        existing_a.name = item.get("name", "")
                        existing_a.code = item.get("code") or item.get("article") or ""
                        existing_a.article = item.get("article", "")
                        existing_a.barcode = barcode
                        existing_a.price = price
                        existing_a.quantity = item.get("quantity", 0)
                    else:
                        db.add(LocalAssortment(
                            id=item_id,
                            name=item.get("name", ""),
                            code=item.get("code") or item.get("article") or "",
                            article=item.get("article", ""),
                            barcode=barcode,
                            price=price,
                            quantity=item.get("quantity", 0)
                        ))
                        
                # Delete orphaned assortments
                if len(raw_assortments) > 0:
                    for aid, a_obj in existing_assortments.items():
                        if aid not in processed_assortment_ids:
                            await db.delete(a_obj)

                # AppSetting: Full sync va Oxirgi sync vaqtini saqlash
                async def update_app_setting(k: str, v: str):
                    s = await db.scalar(select(AppSetting).where(AppSetting.key == k))
                    if s:
                        s.value = v
                    else:
                        db.add(AppSetting(key=k, value=v))

                if do_full_archive_sync and is_fully_synced:
                    await update_app_setting("demands_full_sync_completed", "true")
                await update_app_setting("demands_last_sync_time", now_str)

                # SyncLog
                db.add(SyncLog(
                    entity_type="demands_payments",
                    records_synced=len(raw_demands),
                    status="success",
                    message=f"{'To\'liq arxiv' if do_full_archive_sync else 'Incremental'}: {len(raw_demands)} sotuv, {len(cashins)+len(paymentins)} to'lov sinxronlandi"
                ))
                await db.commit()

            elapsed = time.time() - start_time
            print(f"✅ [Sync] Sinxronizatsiya tugadi ({elapsed:.2f}s)! {len(raw_demands)} ta sotuv DB ga yangilandi.")
            return {"status": "success", "count": len(raw_demands), "elapsed": elapsed}

        except Exception as e:
            print(f"❌ [Sync Exception] {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

async def process_sync_queue():
    """SyncQueue da yig'ilib qolgan (offline rejimda qilingan) amallarni serverga jo'natish"""
    from routers.demands import DemandUpdateRequest, update_demand
    
    async with AsyncSessionLocal() as db:
        pending_items = (await db.execute(select(SyncQueue).where(SyncQueue.status == "pending"))).scalars().all()
        
        if not pending_items:
            return
            
        print(f"🔄 [SyncQueue] {len(pending_items)} ta oflayn vazifa topildi, yuborilmoqda...")
        
        for item in pending_items:
            try:
                payload = json.loads(item.payload)
                if item.action == "update_demand":
                    req = DemandUpdateRequest(**payload)
                    # SyncQueue process calls the same endpoint but directly via ms_client
                    # To avoid circular imports and complex dependencies, we will just call ms_client logic directly
                    
                    # 1. Deleted positions
                    if req.deleted_positions:
                        for pid in req.deleted_positions:
                            await ms_client.delete_demand_position(item.local_id, pid)
                    
                    # 2. Added positions
                    if req.added_positions:
                        for p in req.added_positions:
                            pos_data = {
                                "assortment": {
                                    "meta": {
                                        "href": f"https://api.moysklad.ru/api/remap/1.2/entity/product/{p.assortment_id}",
                                        "type": "product",
                                        "mediaType": "application/json"
                                    }
                                },
                                "quantity": p.quantity,
                                "price": int(p.price * 100),
                            }
                            await ms_client.add_demand_position(item.local_id, pos_data)
                            
                    # 3. Update positions
                    if req.positions:
                        pos_batch = [{"id": p.position_id, "quantity": p.quantity, "price": int(p.price * 100)} for p in req.positions if p.position_id]
                        if pos_batch:
                            await ms_client.update_demand_positions_batch(item.local_id, pos_batch)
                            
                    # 4. Status update
                    state_update = {}
                    if req.state_href:
                        state_update["state"] = {"meta": {"href": req.state_href, "type": "state", "mediaType": "application/json"}}
                    elif req.state_id:
                        state_update["state"] = {"meta": {"href": f"https://api.moysklad.ru/api/remap/1.2/entity/demand/metadata/states/{req.state_id}", "type": "state", "mediaType": "application/json"}}
                    if state_update:
                        await ms_client.update_demand(item.local_id, state_update)

                    # 5. Discount update
                    if (req.discount_type in ["sum", "percent"] and req.discount_value is not None) or req.discount is not None:
                        positions_resp = await ms_client.get_demand_positions(item.local_id)
                        positions = positions_resp.get("rows", [])
                        if positions:
                            total_sum = sum(p.get("price", 0) * p.get("quantity", 0) for p in positions) / 100.0
                            if req.discount_type == "sum" and req.discount_value is not None:
                                dp = (req.discount_value / total_sum) * 100 if total_sum > 0 else 0
                                dp = min(dp, 99.99)
                                discount_percent = dp
                            elif req.discount_type == "percent" and req.discount_value is not None:
                                discount_percent = req.discount_value
                            else:
                                discount_percent = req.discount or 0
                            
                            batch_data = [{"id": p.get("id"), "discount": discount_percent} for p in positions if p.get("id")]
                            if batch_data:
                                await ms_client.update_demand_positions_batch(item.local_id, batch_data)

                    # 6. Payment
                    usd_amt = req.usd_amount or 0.0
                    usd_rt = req.usd_rate or 12800.0
                    total_payment = (req.cash_amount or 0.0) + (req.card_amount or 0.0) + (usd_amt * usd_rt)
                    if total_payment > 0:
                        from routers.payments import create_mixed_payment, MixedPaymentRequest
                        payment_req = MixedPaymentRequest(
                            demand_id=item.local_id,
                            cash_amount=req.cash_amount or 0.0,
                            card_amount=req.card_amount or 0.0,
                            usd_amount=usd_amt,
                            usd_rate=usd_rt,
                            usd_account_id=req.usd_account_id,
                            account_id=req.account_id,
                            update_payment_attribute=bool(req.update_payment_attribute)
                        )
                        await create_mixed_payment(payment_req)

                    # Mark as success
                    item.status = "success"
                    await db.commit()
                    print(f"✅ [SyncQueue] {item.local_id} muvaffaqiyatli jo'natildi!")
                    
            except Exception as e:
                print(f"❌ [SyncQueue] Xato yuz berdi ({item.local_id}): {e}")
                item.status = "failed"
                item.error = str(e)
                await db.commit()



def start_background_scheduler():
    """Har 180 soniyada ma'lumotlarni yangilab turuvchi orqa fon vazifasi"""
    scheduler.add_job(
        sync_all_data,
        "interval",
        seconds=180,
        id="moysklad_periodic_sync",
        replace_existing=True,
    )
    
    # SyncQueue ni tez-tez tekshirib turamiz (har 30 soniyada)
    scheduler.add_job(
        process_sync_queue,
        "interval",
        seconds=30,
        id="sync_queue_processor",
        replace_existing=True,
    )
    
    scheduler.start()
    print("⏰ Orqa fon sinxronizatori (Scheduler) ishga tushirildi (har 180s, queue 30s)")
