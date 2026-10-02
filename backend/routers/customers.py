
# ================= TEZKOR AKT-SVERKA KESHI (RAM / 30s TTL) =================
_AKT_SVERKA_CACHE = {}
_AKT_SVERKA_CACHE_TTL = 30.0

def invalidate_akt_sverka_cache(customer_id: str = None):
    global _AKT_SVERKA_CACHE
    if customer_id:
        _AKT_SVERKA_CACHE.pop(customer_id, None)
    else:
        _AKT_SVERKA_CACHE.clear()

import asyncio
import time
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc, func
from database import get_db
from models_db import LocalCounterparty
from moysklad_client import ms_client

router = APIRouter()

# KESH: 120 soniya + Async Lock
_balances_cache = {"data": None, "timestamp": 0}
_balances_lock = asyncio.Lock()
CACHE_TTL = 120


async def get_balances_cached() -> dict:
    now = time.time()
    if _balances_cache["data"] is not None and (now - _balances_cache["timestamp"]) <= CACHE_TTL:
        return _balances_cache["data"]
        
    async with _balances_lock:
        now = time.time()
        if _balances_cache["data"] is None or (now - _balances_cache["timestamp"]) > CACHE_TTL:
            _balances_cache["data"] = await ms_client.get_all_balances()
            _balances_cache["timestamp"] = now
    return _balances_cache["data"]


class CustomerCreateRequest(BaseModel):
    name: str
    phone: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    group: Optional[str] = None
    tags: Optional[List[str]] = None


class CorrectionRequest(BaseModel):
    counterparty_id: str
    new_balance: Optional[float] = None
    adjustment_amount: Optional[float] = None
    reason: str = "Balansni tuzatish"
    moment: Optional[str] = None


@router.post("")
@router.post("/")
async def create_customer(req: CustomerCreateRequest, db: AsyncSession = Depends(get_db)):
    """Yangi mijoz (kontragent) yaratish — MoySklad va Local DB ga saqlash"""
    try:
        ms_payload = {
            "name": req.name.strip(),
        }
        if req.phone:
            ms_payload["phone"] = req.phone.strip()
        if req.description:
            ms_payload["description"] = req.description.strip()
        if req.email:
            ms_payload["email"] = req.email.strip()
        if req.address:
            ms_payload["actualAddress"] = req.address.strip()
            ms_payload["legalAddress"] = req.address.strip()

        tags_list = []
        if req.tags:
            tags_list = [t.strip() for t in req.tags if t.strip()]
        if req.group and req.group.strip() and req.group.strip() not in tags_list:
            tags_list.append(req.group.strip())
        if tags_list:
            ms_payload["tags"] = tags_list

        created_ms = await ms_client.create_counterparty(ms_payload)
        new_id = created_ms.get("id")

        if new_id:
            # Local DB ga ham yozish
            local_cp = LocalCounterparty(
                id=new_id,
                name=req.name.strip(),
                phone=req.phone.strip() if req.phone else "",
                group=req.group.strip() if req.group else (tags_list[0] if tags_list else "mijozlar"),
                balance=0.0,
                updated_at=datetime.utcnow()
            )
            db.add(local_cp)
            await db.commit()

        return {
            "success": True,
            "message": "Mijoz muvaffaqiyatli yaratildi",
            "data": {
                "id": new_id,
                "name": req.name.strip(),
                "phone": req.phone or "",
                "address": req.address or "",
                "group": req.group or (tags_list[0] if tags_list else "mijozlar"),
                "balance": 0.0
            }
        }
    except Exception as e:
        print(f"❌ Mijoz yaratish xatosi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/filters")
async def get_customer_filters(db: AsyncSession = Depends(get_db)):
    """Mijozlar filtri uchun barcha mavjud guruhlar va statuslar"""
    try:
        distinct_groups_q = select(LocalCounterparty.group).where(LocalCounterparty.group != None, LocalCounterparty.group != "").distinct()
        distinct_statuses_q = select(LocalCounterparty.status).where(LocalCounterparty.status != None, LocalCounterparty.status != "").distinct()
        avail_groups = [g for g in (await db.execute(distinct_groups_q)).scalars().all() if g and g.strip() and g.strip() != "—"]
        avail_statuses = [s for s in (await db.execute(distinct_statuses_q)).scalars().all() if s and s.strip() and s.strip() != "—"]
        return {
            "success": True,
            "data": {
                "groups": sorted(list(set(avail_groups))),
                "statuses": sorted(list(set(avail_statuses)))
            }
        }
    except Exception as e:
        return {"success": False, "data": {"groups": [], "statuses": []}}


@router.get("")
@router.get("/")
async def list_customers(
    limit: int = Query(50, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    sort_by: str = Query("balance"),
    sort_dir: str = Query("desc"),
    debt_filter: Optional[str] = Query("all"),
    groups: Optional[str] = Query(None),
    statuses: Optional[str] = Query(None),
    refresh: Optional[bool] = Query(False),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Agar refresh so'ralgan bo'lsa yoki birinchi marta bo'lsa, MoySklad'dan nativ balanslarni, guruhlarni va statuslarni olib lokal bazaga darhol yangilash
        if refresh:
            try:
                balances_task = ms_client.get_all_balances()
                cps_task = ms_client.get_all_counterparties_cached()
                cp_meta_task = ms_client.get_counterparty_metadata()
                groups_task = ms_client._request("GET", "/entity/group")
                balances, cps, cp_meta, groups_resp = await asyncio.gather(balances_task, cps_task, cp_meta_task, groups_task, return_exceptions=True)

                cp_state_map = {}
                if isinstance(cp_meta, dict):
                    for s in cp_meta.get("states", []):
                        sid = s.get("id") or (s.get("meta", {}).get("href", "").split("/")[-1] if isinstance(s.get("meta"), dict) else "")
                        if sid:
                            cp_state_map[sid] = s.get("name", "")

                group_map = {}
                if isinstance(groups_resp, dict):
                    for g in groups_resp.get("rows", []):
                        gid = g.get("id") or (g.get("meta", {}).get("href", "").split("/")[-1] if isinstance(g.get("meta"), dict) else "")
                        if gid and g.get("name"):
                            group_map[gid] = g["name"]

                cp_dict = {c.get("id"): c for c in cps if isinstance(c, dict)} if isinstance(cps, list) else {}
                all_cps = (await db.execute(select(LocalCounterparty))).scalars().all()
                for cp in all_cps:
                    if isinstance(balances, dict) and cp.id in balances:
                        cp.balance = balances[cp.id]
                    if cp.id in cp_dict:
                        raw_c = cp_dict[cp.id]
                        tags = raw_c.get("tags", [])
                        g_obj = raw_c.get("group", {})
                        gid = g_obj.get("id") or (g_obj.get("meta", {}).get("href", "").split("/")[-1] if isinstance(g_obj, dict) and g_obj.get("meta") else "")
                        g_name = group_map.get(gid, "")
                        group_val = ", ".join(tags) if tags else (g_name or "Основной")

                        st = raw_c.get("state", {})
                        sid = st.get("id") or (st.get("meta", {}).get("href", "").split("/")[-1] if isinstance(st, dict) and st.get("meta") else "")
                        status_val = st.get("name") or cp_state_map.get(sid, "") or "Новый"

                        cp.group = group_val
                        cp.status = status_val
                await db.commit()
            except Exception as re:
                print(f"⚠️ list_customers refresh balances xatosi: {re}")

        # DB Query ni tayyorlash
        query = select(LocalCounterparty)
        
        # 1. Qarz filtri
        if debt_filter == "debtors":
            query = query.where(LocalCounterparty.balance > 0)
        elif debt_filter == "no_debt":
            query = query.where(LocalCounterparty.balance <= 0)
            
        # 2. Qidiruv
        if search:
            search_lower = f"%{search.lower()}%"
            query = query.where(
                or_(
                    func.lower(LocalCounterparty.name).like(search_lower),
                    func.lower(LocalCounterparty.phone).like(search_lower)
                )
            )

        # 3. Guruhlar filtri (1 yoki bir nechta tanlangan)
        if groups:
            group_list = [g.strip() for g in groups.split(",") if g.strip()]
            if group_list:
                group_conds = []
                for g in group_list:
                    if g == "—" or g.lower() == "biriktirilmagan" or g == "none":
                        group_conds.append(or_(LocalCounterparty.group == None, LocalCounterparty.group == "", LocalCounterparty.group == "—"))
                    else:
                        group_conds.append(or_(
                            LocalCounterparty.group == g,
                            LocalCounterparty.group.like(f"%{g}%"),
                            LocalCounterparty.group == g.lower(),
                            LocalCounterparty.group == g.capitalize()
                        ))
                if group_conds:
                    query = query.where(or_(*group_conds))

        # 4. Statuslar filtri (1 yoki bir nechta tanlangan)
        if statuses:
            status_list = [s.strip() for s in statuses.split(",") if s.strip()]
            if status_list:
                status_conds = []
                for st in status_list:
                    if st == "—" or st.lower() == "biriktirilmagan" or st == "none":
                        status_conds.append(or_(LocalCounterparty.status == None, LocalCounterparty.status == "", LocalCounterparty.status == "—"))
                    else:
                        status_conds.append(or_(
                            LocalCounterparty.status == st,
                            LocalCounterparty.status.like(f"%{st}%"),
                            LocalCounterparty.status == st.lower(),
                            LocalCounterparty.status == st.capitalize()
                        ))
                if status_conds:
                    query = query.where(or_(*status_conds))

        # 5. Tartiblash (Sorting)
        sort_column = LocalCounterparty.balance
        if sort_by == "name":
            sort_column = LocalCounterparty.name
        elif sort_by == "phone":
            sort_column = LocalCounterparty.phone
        elif sort_by == "date":
            sort_column = LocalCounterparty.updated_at
        elif sort_by == "group":
            sort_column = LocalCounterparty.group
        elif sort_by == "status":
            sort_column = LocalCounterparty.status

        if sort_dir == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)

        # 6. Global statistika va sahifalash
        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        
        # Global qarz summasini hisoblash (barcha qarzadorlar uchun)
        debt_query = select(func.sum(LocalCounterparty.balance)).where(LocalCounterparty.balance > 0)
        global_total_debt = await db.scalar(debt_query) or 0.0
        
        debtors_count_query = select(func.count(LocalCounterparty.id)).where(LocalCounterparty.balance > 0)
        global_debtors_count = await db.scalar(debtors_count_query) or 0
        
        total_customers_query = select(func.count(LocalCounterparty.id))
        total_customers = await db.scalar(total_customers_query) or 0

        # Mavjud unikal guruhlar va statuslar
        distinct_groups_q = select(LocalCounterparty.group).where(LocalCounterparty.group != None, LocalCounterparty.group != "").distinct()
        distinct_statuses_q = select(LocalCounterparty.status).where(LocalCounterparty.status != None, LocalCounterparty.status != "").distinct()
        avail_groups = [g for g in (await db.execute(distinct_groups_q)).scalars().all() if g and g.strip() and g.strip() != "—"]
        avail_statuses = [s for s in (await db.execute(distinct_statuses_q)).scalars().all() if s and s.strip() and s.strip() != "—"]

        # Sahifalash (Pagination)
        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        rows = result.scalars().all()

        customers = []
        for cp in rows:
            customers.append({
                "id": cp.id,
                "name": cp.name,
                "phone": cp.phone,
                "email": "",
                "description": "",
                "balance": cp.balance,
                "created": "",
                "group": getattr(cp, "group", "") or "—",
                "status": getattr(cp, "status", "") or "—",
            })

        return {
            "success": True,
            "data": customers,
            "meta": {
                "size": total or 0,
                "limit": limit,
                "offset": offset,
                "total_customers": total_customers,
                "total_debt": global_total_debt,
                "debtors_count": global_debtors_count,
                "available_groups": sorted(list(set(avail_groups))),
                "available_statuses": sorted(list(set(avail_statuses))),
            },
        }
    except Exception as e:
        print(f"❌ Customers list xatosi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ================= AKT SVERKA (HISOB-KITOBLAR SOLISHTIRMASI) =================
@router.get("/{customer_id}/akt-sverka")
async def get_customer_akt_sverka(
    customer_id: str,
    date_from: Optional[str] = Query(None, description="Boshlanish sanasi (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Tugash sanasi (YYYY-MM-DD)"),
    refresh: Optional[bool] = Query(False),
):
    """
    Mijoz bilan hisob-kitoblar solishtirma dalolatnomasi (Акт сверки).
    Tezkor RAM va SQLite keshdan 0.01 soniyada javob qaytaradi.
    """
    global _AKT_SVERKA_CACHE
    now_ts = time.time()
    cache_key = f"{customer_id}_{date_from}_{date_to}"

    if not refresh and cache_key in _AKT_SVERKA_CACHE:
        cached_entry = _AKT_SVERKA_CACHE[cache_key]
        if (now_ts - cached_entry.get("timestamp", 0)) < _AKT_SVERKA_CACHE_TTL:
            return cached_entry["data"]
    """
    Mijoz bilan hisob-kitoblar solishtirma dalolatnomasi (Акт сверки).
    - Boshlang'ich saldo (Входящее сальдо)
    - Davrdagi harakatlar: Sotuvlar (Debet) va To'lovlar (Kredit)
    - Yakuniy saldo (Исходящее сальдо)
    """
    try:
        # 1. Mijoz ma'lumotlari
        cp = await ms_client.get_counterparty(customer_id)
        if not cp:
            raise HTTPException(status_code=404, detail="Mijoz topilmadi")

        # 2. Tashkilot ma'lumotlari
        from routers.settings import load_settings
        st_data = load_settings()
        custom_org_name = st_data.get("organization_name")
        org_resp = await ms_client._request("GET", "/entity/organization", params={"limit": 1})
        org = org_resp.get("rows", [])[0] if org_resp.get("rows") else {}
        org_name = custom_org_name or org.get("name", "Said_Baraka")

        target_href = f"/entity/counterparty/{customer_id}"

        # 3. Barcha sotuvlar va to'lovlar
        all_demands = await ms_client.get_all_demands_cached()
        all_payments = await ms_client.get_all_payments_cached()

        raw_ops = []

        # Sotuvlar (Debet - qarz oshishi)
        for d in all_demands:
            agent_href = d.get("agent", {}).get("meta", {}).get("href", "")
            if target_href in agent_href:
                raw_ops.append({
                    "id": d.get("id"),
                    "type": "demand",
                    "type_name": "Sotuv (Отгрузка)",
                    "doc_number": d.get("name", "—"),
                    "moment": d.get("moment", ""),
                    "description": d.get("description", "") or f"Sotuv #{d.get('name')}",
                    "debit": d.get("sum", 0) / 100.0,
                    "credit": 0.0,
                })

        # Naqd to'lovlar (Kredit - qarz kamayishi)
        for c in all_payments.get("cashins", []):
            agent_href = c.get("agent", {}).get("meta", {}).get("href", "")
            if target_href in agent_href:
                rate_obj = c.get("rate") or {}
                rate_val = float(rate_obj.get("value") or 0.0)
                curr_href = rate_obj.get("currency", {}).get("meta", {}).get("href", "")
                is_usd = bool("45062adb" in curr_href or "usd" in curr_href.lower() or rate_val > 1)
                raw_sum = c.get("sum", 0) / 100.0
                usd_amt = raw_sum if is_usd else 0.0
                credit_uzs = (usd_amt * rate_val) if is_usd else raw_sum

                purpose = c.get("paymentPurpose", "") or "Naqd to'lov"
                desc = purpose
                if is_usd:
                    if "$" not in purpose and "Dollar" not in purpose:
                        desc = f"Dollar to'lov: ${usd_amt:,.2f} (kurs: {rate_val:,.0f} so'm). {purpose}".strip()

                raw_ops.append({
                    "id": c.get("id"),
                    "type": "cashin",
                    "type_name": "Kassa kirim (Dollar)" if is_usd else "Kassa kirim (Naqd)",
                    "doc_number": c.get("name", "—"),
                    "moment": c.get("moment", ""),
                    "description": desc,
                    "debit": 0.0,
                    "credit": credit_uzs,
                    "is_usd": is_usd,
                    "usd_amount": usd_amt,
                    "usd_rate": rate_val,
                })

        # Karta / Bank to'lovlar (Kredit - qarz kamayishi)
        for p in all_payments.get("paymentins", []):
            agent_href = p.get("agent", {}).get("meta", {}).get("href", "")
            if target_href in agent_href:
                rate_obj = p.get("rate") or {}
                rate_val = float(rate_obj.get("value") or 0.0)
                curr_href = rate_obj.get("currency", {}).get("meta", {}).get("href", "")
                is_usd = bool("45062adb" in curr_href or "usd" in curr_href.lower() or rate_val > 1)
                raw_sum = p.get("sum", 0) / 100.0
                usd_amt = raw_sum if is_usd else 0.0
                credit_uzs = (usd_amt * rate_val) if is_usd else raw_sum

                purpose = p.get("paymentPurpose", "") or "Bank/karta to'lovi"
                desc = purpose
                if is_usd:
                    if "$" not in purpose and "Dollar" not in purpose:
                        desc = f"Dollar to'lov: ${usd_amt:,.2f} (kurs: {rate_val:,.0f} so'm). {purpose}".strip()

                raw_ops.append({
                    "id": p.get("id"),
                    "type": "paymentin",
                    "type_name": "Bank kirim (Dollar)" if is_usd else "Bank kirim (Karta/Hisob)",
                    "doc_number": p.get("name", "—"),
                    "moment": p.get("moment", ""),
                    "description": desc,
                    "debit": 0.0,
                    "credit": credit_uzs,
                    "is_usd": is_usd,
                    "usd_amount": usd_amt,
                    "usd_rate": rate_val,
                })

        # Korrektirovkalar (counterpartyadjustment)
        try:
            adj_resp = await ms_client._request("GET", "/entity/counterpartyadjustment", params={"limit": 100})
            for adj in adj_resp.get("rows", []):
                agent_href = adj.get("agent", {}).get("meta", {}).get("href", "")
                if target_href in agent_href:
                    adj_sum = adj.get("sum", 0) / 100.0
                    raw_ops.append({
                        "id": adj.get("id"),
                        "type": "adjustment",
                        "type_name": "📊 Korrektirovka",
                        "doc_number": adj.get("name", "—"),
                        "moment": adj.get("moment", ""),
                        "description": adj.get("description", "") or "Balansni tuzatish",
                        "debit": abs(adj_sum) if adj_sum < 0 else 0.0,
                        "credit": adj_sum if adj_sum > 0 else 0.0,
                    })
        except Exception as adje:
            print(f"⚠️ Akt-sverka adjustment xatosi: {adje}")

        # Sanaga qarab tartiblash (xronologik o'sish tartibida)
        raw_ops.sort(key=lambda x: x["moment"])

        # Sana oraliq chegaralari
        start_bound = f"{date_from} 00:00:00" if date_from else None
        end_bound = f"{date_to} 23:59:59" if date_to else None

        initial_debit = 0.0
        initial_credit = 0.0
        period_ops = []

        for op in raw_ops:
            m = op["moment"]
            if start_bound and m < start_bound:
                initial_debit += op["debit"]
                initial_credit += op["credit"]
            elif end_bound and m > end_bound:
                continue
            else:
                period_ops.append(op)

        initial_balance = initial_debit - initial_credit

        # Har bir operatsiyadan keyingi oraliq qoldiqni hisoblash
        running_balance = initial_balance
        total_period_debit = 0.0
        total_period_credit = 0.0

        for op in period_ops:
            running_balance += (op["debit"] - op["credit"])
            op["balance_after"] = running_balance
            total_period_debit += op["debit"]
            total_period_credit += op["credit"]

        closing_balance = running_balance

        # Holat xulosasi
        if closing_balance > 0.01:
            summary_status = "debt"
            summary_text = f"Mijozning qarzdorligi: {closing_balance:,.0f} so'm"
        elif closing_balance < -0.01:
            summary_status = "credit"
            summary_text = f"Mijoz foydasiga haqdorlik: {abs(closing_balance):,.0f} so'm"
        else:
            summary_status = "zero"
            summary_text = "O'zaro hisob-kitoblar teng (0 so'm)"

        result_data = {
            "success": True,
            "data": {
                "organization": {
                    "name": org_name,
                    "inn": org.get("inn", ""),
                    "phone": org.get("phone", ""),
                },
                "counterparty": {
                    "id": cp.get("id"),
                    "name": cp.get("name", "Mijoz"),
                    "phone": cp.get("phone", "") or cp.get("mobile", ""),
                    "email": cp.get("email", ""),
                },
                "period": {
                    "date_from": date_from or (period_ops[0]["moment"][:10] if period_ops else "—"),
                    "date_to": date_to or (period_ops[-1]["moment"][:10] if period_ops else "—"),
                },
                "initial_balance": initial_balance,
                "operations": period_ops,
                "summary": {
                    "initial_balance": initial_balance,
                    "total_debit": total_period_debit,
                    "total_credit": total_period_credit,
                    "closing_balance": closing_balance,
                    "status": summary_status,
                    "status_text": summary_text,
                    "operations_count": len(period_ops),
                },
            }
        }

        _AKT_SVERKA_CACHE[cache_key] = {
            "data": result_data,
            "timestamp": now_ts
        }
        return result_data
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Akt-sverka xatosi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correction")
async def create_correction(correction: CorrectionRequest, db: AsyncSession = Depends(get_db)):
    """Korrektirovka (counterpartyadjustment) — tezkor va aniq"""
    try:
        # 1. Joriy balansni lokal DB dan tezkor olish
        cp = await db.scalar(select(LocalCounterparty).where(LocalCounterparty.id == correction.counterparty_id))
        if not cp:
            try:
                rep_single = await ms_client._request("GET", f"/report/counterparty/{correction.counterparty_id}")
                current_balance = -(float(rep_single.get("balance", 0)) / 100.0)
            except Exception:
                current_balance = 0.0
        else:
            current_balance = float(cp.balance or 0.0)

        # 2. Yangi balans va farq (diff)
        if correction.adjustment_amount is not None:
            diff = float(correction.adjustment_amount)
            final_new_balance = round(current_balance + diff, 2)
        elif correction.new_balance is not None:
            final_new_balance = float(correction.new_balance)
            diff = round(final_new_balance - current_balance, 2)
        else:
            diff = 0.0
            final_new_balance = current_balance

        print(f"📊 Korreksiya: joriy={current_balance:,.2f}, yangi={final_new_balance:,.2f}, farq={diff:,.2f}")

        if abs(diff) < 0.005:
            return {
                "success": True,
                "data": {"message": "Balans o'zgarmagan", "balance": current_balance}
            }

        # 3. Tashkilot olish
        org_resp = await ms_client._request("GET", "/entity/organization", params={"limit": 1})
        org = org_resp.get("rows", [])[0] if org_resp.get("rows") else None
        if not org:
            raise HTTPException(status_code=400, detail="Tashkilot topilmadi")

        agent_meta = {
            "href": f"{ms_client.base_url}/entity/counterparty/{correction.counterparty_id}",
            "type": "counterparty",
            "mediaType": "application/json"
        }
        org_meta = org.get("meta", {})

        # Sana va vaqt (Mahalliy O'zbekiston vaqti)
        if correction.moment:
            try:
                cleaned = correction.moment.replace("T", " ").strip()
                if len(cleaned) == 16:  # YYYY-MM-DD HH:MM
                    cleaned += ":00"
                elif len(cleaned) == 10:  # YYYY-MM-DD
                    current_time_str = datetime.now().strftime("%H:%M:%S")
                    cleaned += f" {current_time_str}"
                datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
                moment_str = cleaned
            except Exception:
                moment_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            moment_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        purpose = f"КОРРЕКТИРОВКА: {correction.reason}"

        # 4. MoySklad counterpartyadjustment
        # MoySklad-da: sum > 0 bo'lsa qarz kamayadi (haqdorlik oshadi), sum < 0 bo'lsa qarz oshadi.
        # Bizning ilovada diff > 0 (qarz oshishi) bo'lsa, MoySklad'ga -diff yuborilishi shart!
        ms_adj_sum_tiyin = int(round(-diff * 100))

        adjustment_data = {
            "agent": {"meta": agent_meta},
            "organization": {"meta": org_meta},
            "sum": ms_adj_sum_tiyin,
            "moment": moment_str,
            "description": purpose,
        }

        result = await ms_client._request("POST", "/entity/counterpartyadjustment", json_data=adjustment_data)
        print(f"✅ Корректировка взаиморасчетов: farq={diff:,.2f} so'm, MoySklad sum={ms_adj_sum_tiyin/100:,.2f}")

        # 5. Mahalliy DB ni darhol yangilash (tezkor javob berish uchun)
        if cp:
            cp.balance = final_new_balance
            await db.commit()

        # 6. Keshlarni tozalash
        invalidate_akt_sverka_cache(correction.counterparty_id)
        ms_client.invalidate_payments_cache()
        _balances_cache["data"] = None
        _balances_cache["timestamp"] = 0

        return {
            "success": True,
            "data": {
                "old_balance": current_balance,
                "new_balance": final_new_balance,
                "difference": diff,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Correction xatosi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class GroupCreateRequest(BaseModel):
    name: str


@router.post("/groups")
async def create_group(group: GroupCreateRequest):
    """Yangi guruh yaratish"""
    try:
        data = {"name": group.name}
        result = await ms_client._request("POST", "/entity/group", json_data=data)
        
        # Metadata keshini tozalash (yangi guruh ko'rinishi uchun)
        return {"success": True, "data": result}
    except Exception as e:
        print(f"❌ Group create xatosi: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/groups-tags")
async def get_groups_tags(db: AsyncSession = Depends(get_db)):
    """Mavjud barcha kontragent guruhlari (teglari) ro'yxati"""
    try:
        tags_set = set(["mijozlar"])
        try:
            from models_db import LocalCounterparty
            stmt = select(LocalCounterparty.group).where(LocalCounterparty.group != None, LocalCounterparty.group != "").distinct()
            local_groups = (await db.execute(stmt)).scalars().all()
            for g in local_groups:
                if g:
                    tags_set.add(g)
        except Exception:
            pass

        try:
            cps = await ms_client.get_all_counterparties_cached()
            for c in cps:
                for t in c.get("tags", []):
                    if t:
                        tags_set.add(t)
        except Exception:
            pass

        return {"success": True, "data": sorted(list(tags_set))}
    except Exception as e:
        print(f"groups-tags xatosi: {e}")
        return {"success": True, "data": ["mijozlar"]}


@router.get("/{customer_id}")
async def get_customer_detail(customer_id: str):
    try:
        target_href = f"/entity/counterparty/{customer_id}"
        agent_url = f"{ms_client.base_url}{target_href}"

        # 1. MoySklad ma'lumotlari va DB so'rovlarini parallel (bir vaqtda) olish — tezlikni 4 barobar oshiradi (<0.15s)
        cp_task = ms_client.get_counterparty(customer_id)
        adj_task = ms_client._request(
            "GET",
            "/entity/counterpartyadjustment",
            params={"filter": f"agent={agent_url}", "limit": 50}
        )
        meta_task = ms_client.get_counterparty_metadata()

        from database import AsyncSessionLocal
        from models_db import LocalDemand, LocalPayment, LocalCounterparty

        async with AsyncSessionLocal() as db:
            local_cp_task = db.scalar(select(LocalCounterparty).where(LocalCounterparty.id == customer_id))
            d_rows_task = db.execute(
                select(LocalDemand).where(LocalDemand.agent_id == customer_id).order_by(desc(LocalDemand.moment))
            )
            p_rows_task = db.execute(
                select(LocalPayment).where(LocalPayment.agent_id == customer_id).order_by(desc(LocalPayment.moment))
            )
            tags_task = db.execute(
                select(LocalCounterparty.group).where(LocalCounterparty.group != None, LocalCounterparty.group != "").distinct()
            )

            cp, adj_resp, metadata, local_cp, d_res, p_res, tags_res = await asyncio.gather(
                cp_task, adj_task, meta_task, local_cp_task, d_rows_task, p_rows_task, tags_task,
                return_exceptions=True
            )

        if isinstance(cp, Exception) or not cp:
            raise HTTPException(status_code=404, detail="Mijoz topilmadi")

        if isinstance(adj_resp, Exception):
            adj_resp = {}
        if isinstance(metadata, Exception):
            metadata = {}

        # 2. Sotuvlar ro'yxati
        formatted_demands = []
        if not isinstance(d_res, Exception) and d_res:
            d_rows = d_res.scalars().all()
            for d in d_rows:
                formatted_demands.append({
                    "id": d.id, "name": d.name, "moment": d.moment,
                    "sum": d.sum, "payed_sum": d.payed_sum, "remaining": d.remaining,
                    "status": d.payment_status, "status_name": d.payment_status_name,
                })

        # 3. To'lovlar ro'yxati
        payments = []
        if not isinstance(p_res, Exception) and p_res:
            p_rows = p_res.scalars().all()
            for p in p_rows:
                payments.append({
                    "id": p.id,
                    "name": p.name,
                    "type": p.type,
                    "type_name": "💲 Dollar" if p.is_usd else ("💵 Naqd" if p.type == "cash" else "💳 Karta"),
                    "amount": p.sum,
                    "moment": p.moment,
                    "is_usd": bool(p.is_usd),
                    "usd_amount": p.usd_amount or 0.0,
                    "usd_rate": p.usd_rate or 0.0,
                    "purpose": p.purpose or "",
                    "demand_id": p.demand_id or "",
                    "linked_demand_id": p.demand_id or "",
                })

        # 4. Korrektirovkalar ro'yxati
        adjustments = []
        for adj in adj_resp.get("rows", []):
            agent_href = adj.get("agent", {}).get("meta", {}).get("href", "")
            if target_href in agent_href or customer_id in agent_href:
                adj_sum = adj.get("sum", 0) / 100.0
                adjustments.append({
                    "id": adj.get("id"),
                    "name": adj.get("name", "—"),
                    "type": "adjustment",
                    "type_name": "📊 Korrektirovka",
                    "amount": adj_sum,
                    "moment": adj.get("moment", ""),
                    "purpose": adj.get("description", "") or "Korrektirovka",
                    "is_usd": False,
                    "usd_amount": 0.0,
                    "usd_rate": 0.0,
                })

        all_payments_and_adj = payments + adjustments
        all_payments_and_adj.sort(key=lambda x: x.get("moment", ""), reverse=True)

        total_sales = sum(d["sum"] for d in formatted_demands)
        total_paid = sum(p["amount"] for p in payments)

        balance = local_cp.balance if (local_cp and not isinstance(local_cp, Exception)) else 0.0

        # Kontragent teglari (Guruhlar)
        cp_tags = cp.get("tags", [])
        active_group = cp_tags[0] if cp_tags else (getattr(local_cp, 'group', '') if (local_cp and not isinstance(local_cp, Exception)) else "")

        # Guruhlar ro'yxati
        available_tags = set(["mijozlar"])
        if not isinstance(tags_res, Exception) and tags_res:
            for g in tags_res.scalars().all():
                if g: available_tags.add(g)
        for t in cp_tags:
            if t: available_tags.add(t)

        # State va boshqa metadata
        state = cp.get("state")
        all_states = [
            {"id": s.get("id"), "name": s.get("name", "")}
            for s in metadata.get("states", []) if isinstance(s, dict)
        ]
        current_state_href = state.get("meta", {}).get("href", "") if isinstance(state, dict) else ""
        state_id = current_state_href.split("/")[-1] if current_state_href else None
        state_name = next((s["name"] for s in all_states if s["id"] == state_id), (state.get("name", "") if isinstance(state, dict) else ""))

        return {
            "success": True,
            "data": {
                "id": cp.get("id"),
                "name": cp.get("name"),
                "phone": cp.get("phone", "") or cp.get("mobile", ""),
                "email": cp.get("email", ""),
                "description": cp.get("description", ""),
                "balance": balance,
                "group": active_group,
                "tags": cp_tags,
                "available_tags": sorted(list(available_tags)),
                "state": state_name,
                "state_id": state_id,
                "all_states": all_states,
                "demands": formatted_demands,
                "payments": all_payments_and_adj,
                "total_sales": total_sales,
                "total_paid": total_paid,
                "demands_count": len(formatted_demands),
                "avg_sale": (total_sales / len(formatted_demands)) if formatted_demands else 0,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Customer detail xatosi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        print(f"❌ Customer detail xatosi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{customer_id}")
async def update_customer(customer_id: str, data: dict):
    try:
        ms_payload = {}
        if "name" in data:
            ms_payload["name"] = data["name"]
        if "phone" in data:
            ms_payload["phone"] = data["phone"]
        if "tags" in data:
            ms_payload["tags"] = data["tags"]
        elif "group" in data:
            grp = data["group"]
            if isinstance(grp, str):
                ms_payload["tags"] = [grp.strip()] if grp.strip() else []
            elif isinstance(grp, dict):
                ms_payload["group"] = grp

        if "state_id" in data and data["state_id"]:
            ms_payload["state"] = {
                "meta": {
                    "href": f"{ms_client.base_url}/entity/counterparty/metadata/states/{data['state_id']}",
                    "type": "state",
                    "mediaType": "application/json"
                }
            }

        result = await ms_client.update_counterparty(customer_id, ms_payload)
        ms_client.invalidate_counterparties_cache()

        # Lokal bazani yangilash
        try:
            from database import AsyncSessionLocal
            from models_db import LocalCounterparty
            async with AsyncSessionLocal() as db:
                cp = await db.scalar(select(LocalCounterparty).where(LocalCounterparty.id == customer_id))
                if cp:
                    if "name" in data:
                        cp.name = data["name"]
                    if "phone" in data:
                        cp.phone = data["phone"]
                    if hasattr(cp, "group"):
                        if "group" in data and isinstance(data["group"], str):
                            cp.group = data["group"].strip()
                        elif "tags" in data and isinstance(data["tags"], list) and len(data["tags"]) > 0:
                            cp.group = data["tags"][0]
                    if hasattr(cp, "status"):
                        if "state_name" in data and data["state_name"]:
                            cp.status = data["state_name"]
                        elif "status" in data and data["status"]:
                            cp.status = data["status"]
                    await db.commit()
        except Exception as dbe:
            print(f"⚠️ LocalCounterparty yangilash xatosi: {dbe}")

        return {"success": True, "data": result}
    except Exception as e:
        print(f"❌ Customer update xatosi: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{customer_id}/unpaid-demands")
async def get_customer_unpaid_demands(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Mijozning to'lanmagan (qarzdor) sotuv hujjatlari ro'yxati (bog'lash uchun)"""
    try:
        from models_db import LocalDemand
        stmt = (
            select(LocalDemand)
            .where(LocalDemand.agent_id == customer_id, LocalDemand.remaining > 0.01)
            .order_by(LocalDemand.moment.asc())
        )
        rows = (await db.execute(stmt)).scalars().all()

        unpaid = []
        for d in rows:
            unpaid.append({
                "id": d.id,
                "name": d.name,
                "moment": d.moment,
                "sum": d.sum,
                "paid_sum": d.payed_sum,
                "remaining": d.remaining,
                "state_name": d.payment_status_name or "To'lanmagan",
            })
        return {"success": True, "data": unpaid}
    except Exception as e:
        print(f"Unpaid demands xatosi: {e}")
        return {"success": True, "data": []}


def _match_payment_to_demand(payment: dict, payments_by_demand: dict, demand_names: dict):
    amount = payment.get("sum", 0) / 100.0
    matched = False
    operations = payment.get("operations", [])
    if isinstance(operations, list):
        for op in operations:
            if isinstance(op, dict):
                op_href = op.get("meta", {}).get("href", "")
                if "/entity/demand/" in op_href:
                    did = op_href.split("/")[-1]
                    if did in payments_by_demand:
                        payments_by_demand[did] += amount
                        matched = True
                        break
    if not matched:
        demand_ref = payment.get("demand") or {}
        if isinstance(demand_ref, dict):
            href = demand_ref.get("meta", {}).get("href", "")
            if "/entity/demand/" in href:
                did = href.split("/")[-1]
                if did in payments_by_demand:
                    payments_by_demand[did] += amount
                    matched = True
    if not matched:
        purpose = payment.get("paymentPurpose", "") or ""
        for dname, did in demand_names.items():
            if dname and f"Sotuv {dname}" in purpose:
                payments_by_demand[did] += amount
                break


@router.delete("/{customer_id}")
async def delete_customer(customer_id: str):
    try:
        result = await ms_client._request("DELETE", f"/entity/counterparty/{customer_id}")
        ms_client.invalidate_counterparties_cache()
        _balances_cache["data"] = None
        _balances_cache["timestamp"] = 0
        return {"success": True, "data": result}
    except Exception as e:
        print(f"❌ Customer delete xatosi: {e}")
        raise HTTPException(status_code=500, detail=str(e))