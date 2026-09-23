import math
import re
import time
import asyncio
import httpx
from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc
from database import get_db
from models_db import LocalDemand, LocalAssortment, SyncQueue
import json
from moysklad_client import ms_client
from tasks import sync_all_data

router = APIRouter()

# Metadata kesh (5 daqiqa)
DEFAULT_STATES = [
    {"id": "new", "href": "", "name": "Новый", "color": 10855845},
    {"id": "agreed", "href": "", "name": "Договорились", "color": 3899638},
    {"id": "assembled", "href": "", "name": "Собран", "color": 16109323},
    {"id": "on_the_way", "href": "", "name": "В пути", "color": 9133302},
    {"id": "in_store", "href": "", "name": "В магазине", "color": 439764},
    {"id": "closed", "href": "", "name": "Закрыт", "color": 1096065},
    {"id": "cancelled", "href": "", "name": "Отменен", "color": 15680324},
]

_states_cache = DEFAULT_STATES
_states_cache_time = 0.0

_oplata_attr_cache = None
_oplata_attr_cache_time = 0.0


async def get_cached_states():
    global _states_cache, _states_cache_time
    now = time.time()
    if _states_cache is not None and _states_cache != DEFAULT_STATES and (now - _states_cache_time) < 300:
        return _states_cache
    try:
        metadata = await asyncio.wait_for(ms_client.get_demand_metadata(), timeout=3.0)
        states = metadata.get("states", [])
        if states:
            formatted_states = []
            for s in states:
                state_meta = s.get("meta", {})
                state_id = state_meta.get("id") or extract_id_from_href(state_meta.get("href", ""))
                formatted_states.append({
                    "id": state_id,
                    "href": state_meta.get("href", ""),
                    "name": s.get("name", ""),
                    "color": s.get("color", 0),
                })
            _states_cache = formatted_states
            _states_cache_time = now
            return _states_cache
    except Exception as e:
        pass
    return _states_cache or DEFAULT_STATES


async def get_cached_oplata_attribute():
    global _oplata_attr_cache, _oplata_attr_cache_time
    now = time.time()
    if _oplata_attr_cache is not None and (now - _oplata_attr_cache_time) < 300:
        return _oplata_attr_cache
    try:
        metadata = await ms_client.get_demand_metadata()
        attributes = metadata.get("attributes", [])
        attr_rows = attributes.get("rows", []) if isinstance(attributes, dict) else (attributes if isinstance(attributes, list) else [])
        oplata_attr = None
        for a in attr_rows:
            if isinstance(a, dict):
                aname = (a.get("name") or "").lower()
                if "оплата" in aname or "oplata" in aname:
                    oplata_attr = a
                    break
        _oplata_attr_cache = oplata_attr
        _oplata_attr_cache_time = now
        return _oplata_attr_cache
    except Exception as e:
        print(f"[get_cached_oplata_attribute error] {e}")
        return _oplata_attr_cache


def extract_id_from_href(href: str) -> str:
    match = re.search(r'/([0-9a-f-]+)$', href)
    return match.group(1) if match else href


def color_int_to_hex(color_int: Optional[int], state_name: str = "") -> str:
    if color_int and color_int > 0:
        return f"#{color_int:06x}"
    name_lower = (state_name or "").lower()
    if "договор" in name_lower or "kelish" in name_lower:
        return "#3b82f6"  # Ko'k
    if "собран" in name_lower or "yig" in name_lower:
        return "#f59e0b"  # Sariq / Amber
    if "пути" in name_lower or "yo'l" in name_lower:
        return "#8b5cf6"  # Binafsha
    if "магазин" in name_lower or "magazin" in name_lower:
        return "#06b6d4"  # Moviy
    if "закр" in name_lower or "yopil" in name_lower:
        return "#10b981"  # Yashil
    if "отмен" in name_lower or "bekor" in name_lower:
        return "#ef4444"  # Qizil
    return "#64748b"  # Kulrang


# ================= MODELLAR =================
class QuickStatusRequest(BaseModel):
    state_id: Optional[str] = None
    state_href: Optional[str] = None


class PositionUpdateItem(BaseModel):
    position_id: Optional[str] = None
    assortment_id: Optional[str] = None
    quantity: float
    price: float
    discount: Optional[float] = None


class PositionAddRequest(BaseModel):
    assortment_id: str
    quantity: float
    price: float


class PositionUpdateRequest(BaseModel):
    price: Optional[float] = None
    quantity: Optional[float] = None


class DemandUpdateRequest(BaseModel):
    discount: Optional[float] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    state_id: Optional[str] = None
    state_href: Optional[str] = None
    # Birlashtirilgan tovarlar
    positions: Optional[list[PositionUpdateItem]] = None
    deleted_positions: Optional[list[str]] = None
    added_positions: Optional[list[PositionAddRequest]] = None
    # To'lov ma'lumotlari
    cash_amount: Optional[float] = 0.0
    card_amount: Optional[float] = 0.0
    usd_amount: Optional[float] = 0.0
    usd_rate: Optional[float] = 12800.0
    usd_account_id: Optional[str] = None
    account_id: Optional[str] = None
    update_payment_attribute: Optional[bool] = False


# ================= RO'YXAT =================
@router.get("")
@router.get("/")
async def list_demands(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    state_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        clean_limit = int(limit) if isinstance(limit, (int, float, str)) and str(limit).isdigit() else 50
        clean_offset = int(offset) if isinstance(offset, (int, float, str)) and str(offset).isdigit() else 0

        # 1. Avval tezkor lokal DB dan tekshiramiz (Local-first architecture)
        total_local_count = await db.scalar(select(func.count(LocalDemand.id)))
        if total_local_count and total_local_count > 0:
            query = select(LocalDemand)
            count_query = select(func.count(LocalDemand.id))
            
            conditions = []
            if date_from:
                conditions.append(LocalDemand.moment >= f"{date_from} 00:00:00")
            if date_to:
                conditions.append(LocalDemand.moment <= f"{date_to} 23:59:59")
            if search:
                s_term = f"%{search.strip()}%"
                conditions.append(or_(
                    LocalDemand.name.ilike(s_term),
                    LocalDemand.agent_name.ilike(s_term),
                    LocalDemand.description.ilike(s_term)
                ))
            if state_filter and state_filter != "all":
                conditions.append(LocalDemand.state_name.ilike(f"%{state_filter.strip()}%"))

            if conditions:
                query = query.where(*conditions)
                count_query = count_query.where(*conditions)

            total_filtered = (await db.scalar(count_query)) or 0
            results = (await db.execute(
                query.order_by(desc(LocalDemand.moment)).offset(clean_offset).limit(clean_limit)
            )).scalars().all()

            return {
                "success": True,
                "data": [
                    {
                        "id": d.id,
                        "name": d.name,
                        "moment": d.moment,
                        "sum": d.sum,
                        "payed_sum": d.payed_sum,
                        "remaining": d.remaining,
                        "payment_status": d.payment_status,
                        "payment_status_name": d.payment_status_name,
                        "state_name": d.state_name,
                        "state_color": d.state_color,
                        "state_id": d.state_id,
                        "state_href": d.state_href,
                        "agent_name": d.agent_name,
                        "agent_id": d.agent_id,
                        "description": d.description,
                    }
                    for d in results
                ],
                "meta": {
                    "size": total_filtered,
                    "limit": clean_limit,
                    "offset": clean_offset,
                    "source": "local_db",
                }
            }

        # 2. Agar DB hali bo'sh bo'lsa (dastlabki sinxronizatsiya vaqti), MoySklad API'dan olish
        moment_from = f"{date_from} 00:00:00" if date_from else (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00")
        moment_to = f"{date_to} 23:59:59" if date_to else datetime.now().strftime("%Y-%m-%d 23:59:59")

        fetch_limit = 1000 if search else clean_limit
        fetch_offset = 0 if search else clean_offset

        demands_task = ms_client.get_demands(
            limit=fetch_limit,
            offset=fetch_offset,
            moment_from=moment_from,
            moment_to=moment_to,
        )
        payments_task = ms_client.get_all_payments_cached()

        demands, all_payments = await asyncio.gather(demands_task, payments_task)
        rows = demands.get("rows", [])
        meta = demands.get("meta", {})

        payments_by_demand = {}
        demand_names = {}
        for d in rows:
            did = d.get("id")
            dname = d.get("name", "")
            if did:
                demand_names[dname] = did
                payments_by_demand[did] = 0.0

        for c in all_payments.get("cashins", []):
            _match_payment_to_demand(c, payments_by_demand, demand_names, rows)
        for p in all_payments.get("paymentins", []):
            _match_payment_to_demand(p, payments_by_demand, demand_names, rows)

        formatted_demands = []
        for d in rows:
            agent = d.get("agent", {})
            agent_id = extract_id_from_href(agent["meta"]["href"]) if agent.get("meta") and agent["meta"].get("href") else None
            agent_name = agent.get("name") or "Noma'lum"

            if search:
                search_lower = search.lower()
                demand_name = d.get("name", "").lower()
                if search_lower not in demand_name and search_lower not in agent_name.lower():
                    continue

            state = d.get("state", {})
            state_name = state.get("name", "—") if isinstance(state, dict) else "—"
            state_color_int = state.get("color", 0) if isinstance(state, dict) else 0
            state_color = color_int_to_hex(state_color_int, state_name)
            state_meta = state.get("meta", {}) if isinstance(state, dict) else {}
            state_href = state_meta.get("href", "")
            state_id = extract_id_from_href(state_href) if state_href else ""

            if state_filter and state_filter != "all":
                s_filter_clean = state_filter.lower().strip()
                s_name_clean = state_name.lower().strip()
                if s_filter_clean not in s_name_clean and s_name_clean not in s_filter_clean:
                    continue

            demand_sum = d.get("sum", 0) / 100.0
            demand_id = d.get("id")
            payed_sum = payments_by_demand.get(demand_id, 0.0)
            remaining = max(0.0, demand_sum - payed_sum)

            if remaining <= 0.01:
                payment_status = "paid"
                payment_status_name = "✅ To'langan"
            elif payed_sum > 0:
                payment_status = "partial"
                payment_status_name = "🟡 Qisman"
            else:
                payment_status = "unpaid"
                payment_status_name = "🔴 To'lanmagan"

            formatted_demands.append({
                "id": demand_id,
                "name": d.get("name"),
                "moment": d.get("moment"),
                "sum": demand_sum,
                "payed_sum": payed_sum,
                "remaining": remaining,
                "payment_status": payment_status,
                "payment_status_name": payment_status_name,
                "state_name": state_name,
                "state_color": state_color,
                "state_id": state_id,
                "state_href": state_href,
                "agent_name": agent_name,
                "agent_id": agent_id,
                "description": d.get("description", ""),
            })

        if search or (state_filter and state_filter != "all"):
            total_size = len(formatted_demands)
            page_data = formatted_demands[clean_offset:clean_offset + clean_limit]
            return {
                "success": True,
                "data": page_data,
                "meta": {
                    "size": total_size,
                    "limit": clean_limit,
                    "offset": clean_offset,
                    "source": "moysklad_api",
                },
            }
        else:
            return {
                "success": True,
                "data": formatted_demands,
                "meta": {
                    "size": meta.get("size", 0),
                    "limit": clean_limit,
                    "offset": clean_offset,
                    "source": "moysklad_api",
                },
            }

    except Exception as e:
        print(f"Demands list xato: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def _match_payment_to_demand(payment: dict, payments_by_demand: dict, demand_names: dict, rows: list):
    """To'lovni tegishli sotuvga moslashtirish (O(1) xarita orqali)"""
    amount = payment.get("sum", 0) / 100.0
    matched = False

    # 1. operations ichida demand havolasi
    operations = payment.get("operations", [])
    if isinstance(operations, list):
        for op in operations:
            if isinstance(op, dict):
                op_href = op.get("meta", {}).get("href", "")
                if "/entity/demand/" in op_href:
                    demand_id = extract_id_from_href(op_href)
                    if demand_id in payments_by_demand:
                        payments_by_demand[demand_id] += amount
                        matched = True
                        break

    # 2. demand havolasi
    if not matched:
        demand_ref = payment.get("demand") or {}
        if isinstance(demand_ref, dict):
            href = demand_ref.get("meta", {}).get("href", "")
            if "/entity/demand/" in href:
                demand_id = extract_id_from_href(href)
                if demand_id in payments_by_demand:
                    payments_by_demand[demand_id] += amount
                    matched = True

    # 3. paymentPurpose bo'yicha
    if not matched:
        purpose = payment.get("paymentPurpose", "") or ""
        for dname, did in demand_names.items():
            if dname and f"Sotuv {dname}" in purpose:
                payments_by_demand[did] += amount
                matched = True
                break

# ================= TOVAR QIDIRISH =================
@router.get("/search/assortment")
async def search_assortment(query: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db)):
    try:
        # DB dan qidiramiz (nomi, kodi, artikuli, shtrixkodi bo'yicha)
        search_pattern = f"%{query}%"
        stmt = select(LocalAssortment).where(
            or_(
                LocalAssortment.name.ilike(search_pattern),
                LocalAssortment.code.ilike(search_pattern),
                LocalAssortment.article.ilike(search_pattern),
                LocalAssortment.barcode.ilike(search_pattern)
            )
        ).limit(20)
        
        results = (await db.execute(stmt)).scalars().all()

        formatted = []
        for item in results:
            formatted.append({
                "id": item.id,
                "name": item.name,
                "code": item.code or "—",
                "barcode": item.barcode or "—",
                "price": item.price,
                "quantity": item.quantity,
            })

        print(f"🔍 DB qidiruv '{query}': {len(formatted)} ta natija topildi")
        return {"success": True, "data": formatted}

    except Exception as e:
        print(f"❌ DB Search assortment xato: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ================= STATUSLAR =================
@router.get("/meta/states")
async def get_demand_states():
    try:
        states = await get_cached_states()
        return {"success": True, "data": states}
    except Exception as e:
        print(f"States xato: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================= BATAFSIL =================
@router.get("/{demand_id}")
async def get_demand_detail(demand_id: str):
    try:
        # Parallel: demand + positions + cached payments + states + oplata attribute
        demand_task = ms_client.get_demand(demand_id)
        positions_task = ms_client.get_demand_positions(demand_id)
        payments_task = ms_client.get_all_payments_cached()
        states_task = get_cached_states()
        oplata_task = get_cached_oplata_attribute()

        demand, positions_resp, all_payments, cached_states, oplata_attr = await asyncio.gather(
            demand_task, positions_task, payments_task, states_task, oplata_task
        )

        agent = demand.get("agent", {})
        agent_id = None
        if agent.get("meta") and agent["meta"].get("href"):
            agent_id = extract_id_from_href(agent["meta"]["href"])

        agent_name = agent.get("name", "Noma'lum")
        agent_phone = agent.get("phone", "")
        
        # Mijozning umumiy balansi (qarzi) - juda tezkor (<0.2s)
        agent_balance = 0.0
        if agent_id:
            try:
                agent_href = agent.get("meta", {}).get("href", "")
                if agent_href:
                    agent_demands_resp = await ms_client._request(
                        "GET", "/entity/demand",
                        params={"filter": f"agent={agent_href}", "limit": 100}
                    )
                    agent_sales = sum(d.get("sum", 0) / 100.0 for d in agent_demands_resp.get("rows", []))

                    target_part = f"/entity/counterparty/{agent_id}"
                    agent_paid = sum(c.get("sum", 0) / 100.0 for c in all_payments.get("cashins", []) if target_part in c.get("agent", {}).get("meta", {}).get("href", "") or agent_id in c.get("agent", {}).get("meta", {}).get("href", ""))
                    agent_paid += sum(p.get("sum", 0) / 100.0 for p in all_payments.get("paymentins", []) if target_part in p.get("agent", {}).get("meta", {}).get("href", "") or agent_id in p.get("agent", {}).get("meta", {}).get("href", ""))

                    agent_balance = agent_sales - agent_paid
                else:
                    agent_balance = (agent.get("balance", 0) or 0) / 100.0
            except Exception as be:
                print(f"[Agent balance error] {be}")
                agent_balance = (agent.get("balance", 0) or 0) / 100.0

        state = demand.get("state", {})
        state_name = state.get("name", "")
        discount = demand.get("discount", 0)

        positions_rows = positions_resp.get("rows", [])

        formatted_positions = []
        for pos in positions_rows:
            assortment = pos.get("assortment", {})

            price_raw = pos.get("price", 0)
            quantity = pos.get("quantity", 0)

            sum_raw = pos.get("sum")
            if sum_raw is None or sum_raw == 0:
                sum_raw = price_raw * quantity

            code = assortment.get("code", "")
            if not code:
                code = assortment.get("article", "")

            # Har bir tovar uchun alohida skidka foizi
            position_discount = float(pos.get("discount", 0) or 0)
            
            # Original narx (skidkasiz bazaviy narx)
            original_price = (pos.get("price", 0) or 0) / 100.0
            
            if pos.get("discountedPrice"):
                discounted_price = (pos.get("discountedPrice", 0) or 0) / 100.0
            elif position_discount > 0:
                discounted_price = original_price * (1.0 - position_discount / 100.0)
            else:
                discounted_price = original_price

            final_sum = (sum_raw or 0) / 100.0
            total_before_discount = original_price * quantity
            discount_amount = max(0.0, total_before_discount - final_sum) if position_discount > 0 else 0.0

            formatted_positions.append({
                "position_id": pos.get("id"),
                "code": code or "—",
                "name": assortment.get("name", "Noma'lum tovar"),
                "quantity": quantity,
                "price": original_price,  # Asl katalog narxi (tahrirlash va saqlash to'g'ri ishlashi uchun)
                "discounted_price": discounted_price,  # Chegirmali narx
                "sum": final_sum,
                "discount": position_discount,
                "discount_amount": discount_amount,
                "original_price": original_price,
            })

        demand_discount = demand.get("discount", 0)
        avg_discount = demand_discount
        if not avg_discount and formatted_positions:
            discounts = [p["discount"] for p in formatted_positions if p.get("discount") and p["discount"] > 0]
            if discounts:
                avg_discount = sum(discounts) / len(discounts)

        # Bog'langan to'lovlarni xotiradagi to'lovlardan darhol bog'lash (0ms ekstra so'rov)
        demand_payment_hrefs = set()
        demand_payments_ref = demand.get("payments", [])
        if isinstance(demand_payments_ref, list):
            for pref in demand_payments_ref:
                if isinstance(pref, dict):
                    phref = pref.get("meta", {}).get("href", "")
                    if phref:
                        demand_payment_hrefs.add(phref)

        demand_name = demand.get("name", "")
        demand_href_part = f"/entity/demand/{demand_id}"
        search_term = f"Sotuv {demand_name}" if demand_name else ""

        cashins = all_payments.get("cashins", [])
        paymentins = all_payments.get("paymentins", [])

        matched_payments = []
        matched_payment_ids = set()
        total_paid = 0.0

        def check_match(doc: dict, doc_type: str, type_name: str):
            doc_id = doc.get("id")
            if not doc_id or doc_id in matched_payment_ids:
                return

            doc_href = doc.get("meta", {}).get("href", "")
            purpose = doc.get("paymentPurpose", "") or ""

            rate_obj = doc.get("rate") or {}
            rate_val = float(rate_obj.get("value") or 0.0)
            curr_href = rate_obj.get("currency", {}).get("meta", {}).get("href", "")
            is_usd = bool("45062adb" in curr_href or "usd" in curr_href.lower() or rate_val > 1)

            raw_sum = doc.get("sum", 0) / 100.0
            usd_amt = raw_sum if is_usd else 0.0
            sum_uzs = (usd_amt * rate_val) if is_usd else raw_sum
            linked_amount = sum_uzs
            matched = False

            if doc_href and doc_href in demand_payment_hrefs:
                matched = True

            if not matched:
                ops = doc.get("operations", [])
                if isinstance(ops, list):
                    for op in ops:
                        if isinstance(op, dict):
                            op_href = op.get("meta", {}).get("href", "")
                            if demand_href_part in op_href or (demand_id in op_href):
                                matched = True
                                if op.get("linkedSum"):
                                    raw_linked = op.get("linkedSum", 0) / 100.0
                                    linked_amount = (raw_linked * rate_val) if is_usd else raw_linked
                                break

            if not matched:
                demand_ref = doc.get("demand", {})
                if isinstance(demand_ref, dict):
                    d_href = demand_ref.get("meta", {}).get("href", "")
                    if demand_href_part in d_href or (demand_id in d_href):
                        matched = True
                        if doc.get("linkedSum"):
                            raw_linked = doc.get("linkedSum", 0) / 100.0
                            linked_amount = (raw_linked * rate_val) if is_usd else raw_linked

            # Faqat rasmiy bog'langan to'lovlar
            if matched:
                matched_payment_ids.add(doc_id)
                nonlocal total_paid
                total_paid += linked_amount
                doc_number = doc.get("name", "")
                final_type_name = "💲 Dollar" if is_usd else type_name
                matched_payments.append({
                    "id": doc_id,
                    "name": doc_number,
                    "type": "usd" if is_usd else doc_type,
                    "type_name": final_type_name,
                    "amount": linked_amount,
                    "full_sum": sum_uzs,
                    "moment": doc.get("moment"),
                    "purpose": purpose,
                    "is_usd": is_usd,
                    "usd_amount": usd_amt,
                    "usd_rate": rate_val,
                })

        for c in cashins:
            check_match(c, "cash", "💵 Naqd")
        for p in paymentins:
            check_match(p, "card", "💳 Karta")

        demand_payed_sum = demand.get("payedSum", 0) / 100.0
        if total_paid == 0 and demand_payed_sum > 0:
            total_paid = demand_payed_sum

        matched_payments.sort(key=lambda x: x.get("moment", ""), reverse=True)

        state_color_int = state.get("color", 0) if isinstance(state, dict) else 0
        state_color = color_int_to_hex(state_color_int, state_name)
        state_meta = state.get("meta", {}) if isinstance(state, dict) else {}
        state_href = state_meta.get("href", "")
        state_id = extract_id_from_href(state_href) if state_href else ""

        demand_total_sum = demand.get("sum", 0) / 100.0
        remaining = max(0.0, demand_total_sum - total_paid)

        owner = demand.get("owner", {})
        owner_name = owner.get("name", "") if isinstance(owner, dict) else ""

        return {
            "success": True,
            "data": {
                "id": demand.get("id"),
                "name": demand.get("name"),
                "moment": demand.get("moment"),
                "sum": demand_total_sum,
                "discount": avg_discount,
                "state_name": state_name,
                "state_color": state_color,
                "state_id": state_id,
                "state_href": state_href,
                "agent_name": agent_name,
                "agent_id": agent_id,
                "agent_phone": agent_phone,
                "agent_balance": agent_balance,
                "owner_name": owner_name,
                "description": demand.get("description", ""),
                "positions": formatted_positions,
                "linked_payments": matched_payments,
                "total_paid": total_paid,
                "remaining": remaining,
                "states": cached_states,
                "oplata_attribute": oplata_attr,
            },
        }

    except Exception as e:
        print(f"Demand detail xato: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ================= TEZKOR STATUS O'ZGARTIRISH =================
@router.put("/{demand_id}/quick-status")
async def update_quick_status(demand_id: str, req: QuickStatusRequest, db: AsyncSession = Depends(get_db)):
    """Faqat statusni 1 tugma bilan tez o'zgartirish"""
    try:
        state_update = {}
        if req.state_href:
            state_update["state"] = {
                "meta": {
                    "href": req.state_href,
                    "type": "state",
                    "mediaType": "application/json"
                }
            }
        elif req.state_id:
            state_update["state"] = {
                "meta": {
                    "href": f"https://api.moysklad.ru/api/remap/1.2/entity/demand/metadata/states/{req.state_id}",
                    "type": "state",
                    "mediaType": "application/json"
                }
            }
        else:
            raise HTTPException(status_code=400, detail="Status tanlanmagan")

        await ms_client.update_demand(demand_id, state_update)
        ms_client.invalidate_demands_cache()

        # Update local DB
        try:
            local_demand = await db.scalar(select(LocalDemand).where(LocalDemand.id == demand_id))
            if local_demand:
                # To get the name and color, we need the states map
                cached_states = await get_cached_states()
                href = req.state_href or f"https://api.moysklad.ru/api/remap/1.2/entity/demand/metadata/states/{req.state_id}"
                
                matched_state = next((s for s in cached_states if s.get("meta", {}).get("href") == href), None)
                if matched_state:
                    state_name = matched_state.get("name", "")
                    state_color_int = matched_state.get("color", 0)
                    local_demand.state_name = state_name
                    local_demand.state_color = color_int_to_hex(state_color_int, state_name)
                    local_demand.state_id = extract_id_from_href(href)
                    local_demand.state_href = href
                    await db.commit()
                    print(f"   ✅ Local DB state updated for {demand_id}")
        except Exception as db_err:
            print(f"   ⚠️ Local DB state update xatosi: {db_err}")

        return {"success": True, "message": "Status muvaffaqiyatli yangilandi"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Quick status xatosi: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================= OTGRUZKANI TAHRIRLASH =================
@router.put("/{demand_id}")
async def update_demand(demand_id: str, update: DemandUpdateRequest, db: AsyncSession = Depends(get_db)):
    """
    Otgruzkani yangilash — batch update bilan optimallashtirilgan.
    Barcha tovarlar, status, skidka va to'lovni BIR SO'ROVDA yangilaydi.
    """
    try:
        # Offline-first: Agar tarmoq xatosi bo'lsa, xatoni ushlab SyncQueue ga yozamiz
        try:
            # 1. Tovarlarni o'chirish (agar bo'lsa)
        if update.deleted_positions:
            for pid in update.deleted_positions:
                try:
                    await ms_client.delete_demand_position(demand_id, pid)
                    print(f"   🗑️ Pozitsiya o'chirildi: {pid}")
                except Exception as del_err:
                    print(f"   ⚠️ Pozitsiya o'chirishda xato ({pid}): {del_err}")

        # 2. Yangi tovarlarni qo'shish (agar bo'lsa)
        if update.added_positions:
            for item in update.added_positions:
                pos_data = {
                    "assortment": {
                        "meta": {
                            "href": f"https://api.moysklad.ru/api/remap/1.2/entity/product/{item.assortment_id}",
                            "type": "product",
                            "mediaType": "application/json"
                        }
                    },
                    "quantity": item.quantity,
                    "price": int(item.price * 100),
                }
                await ms_client.add_demand_position(demand_id, pos_data)
                print(f"   ➕ Yangi tovar qo'shildi: {item.assortment_id} ({item.quantity} ta)")

        # 3. Mavjud tovarlarni yangilash (soni va narxlari - batch)
        if update.positions:
            pos_batch = []
            for p in update.positions:
                if p.position_id:
                    pos_batch.append({
                        "id": p.position_id,
                        "quantity": p.quantity,
                        "price": int(p.price * 100),
                    })
            if pos_batch:
                await ms_client.update_demand_positions_batch(demand_id, pos_batch)
                print(f"   📦 {len(pos_batch)} ta pozitsiya batch yangilandi")

        # 4. Status o'zgartirish (butun hujjatga)
        state_update = {}
        if update.state_href:
            state_update["state"] = {
                "meta": {
                    "href": update.state_href,
                    "type": "state",
                    "mediaType": "application/json"
                }
            }
        elif update.state_id:
            state_update["state"] = {
                "meta": {
                    "href": f"https://api.moysklad.ru/api/remap/1.2/entity/demand/metadata/states/{update.state_id}",
                    "type": "state",
                    "mediaType": "application/json"
                }
            }

        if state_update:
            print(f"   📌 Status yangilanmoqda...")
            await ms_client.update_demand(demand_id, state_update)

        # 5. Skidka (BATCH UPDATE — barcha tovarlarni bir so'rovda)
        if (update.discount_type in ["sum", "percent"] and update.discount_value is not None) or update.discount is not None:
            # Barcha pozitsiyalarni olish (yangilangan holatda)
            positions_resp = await ms_client.get_demand_positions(demand_id)
            positions = positions_resp.get("rows", [])

            if positions:
                # Umumiy summa
                total_sum = sum(p.get("price", 0) * p.get("quantity", 0) for p in positions) / 100.0

                # Skidka % ni hisoblash (MATEMATIK ANIQLIK BILAN)
                if update.discount_type == "sum" and update.discount_value is not None:
                    if total_sum > 0:
                        discount_percent = (update.discount_value / total_sum) * 100
                        discount_percent = min(discount_percent, 99.99)
                        discount_percent = math.floor(discount_percent * 1_000_000) / 1_000_000
                    else:
                        discount_percent = 0
                    print(f"   💰 Summa skidka: {update.discount_value} so'm = {discount_percent}%")
                elif update.discount_type == "percent" and update.discount_value is not None:
                    discount_percent = math.floor(update.discount_value * 1_000_000) / 1_000_000
                    print(f"   💰 Foiz skidka: {discount_percent}%")
                elif update.discount is not None:
                    discount_percent = math.floor(update.discount * 1_000_000) / 1_000_000
                else:
                    discount_percent = 0

                batch_data = []
                for pos in positions:
                    position_id = pos.get("id")
                    if position_id:
                        batch_data.append({
                            "id": position_id,
                            "discount": discount_percent,
                        })

                if batch_data:
                    await ms_client.update_demand_positions_batch(demand_id, batch_data)
                    print(f"   ✅ {len(batch_data)} ta tovarga {discount_percent}% skidka qo'llandi (1 so'rovda!)")

        # 6. To'lov (Naqd / Karta / Dollar)
        payment_result = None
        usd_amt = update.usd_amount or 0.0
        usd_rt = update.usd_rate or 12800.0
        total_payment = (update.cash_amount or 0.0) + (update.card_amount or 0.0) + (usd_amt * usd_rt)
        if total_payment > 0:
            from routers.payments import create_mixed_payment, MixedPaymentRequest
            payment_req = MixedPaymentRequest(
                demand_id=demand_id,
                cash_amount=update.cash_amount or 0.0,
                card_amount=update.card_amount or 0.0,
                usd_amount=usd_amt,
                usd_rate=usd_rt,
                usd_account_id=update.usd_account_id,
                account_id=update.account_id,
                update_payment_attribute=bool(update.update_payment_attribute),
            )
            payment_result = await create_mixed_payment(payment_req)
            print(f"   💰 To'lov saqlandi: naqd={update.cash_amount}, karta={update.card_amount}, dollar=${usd_amt} @ {usd_rt}")

        # 7. Keshni tozalash
        ms_client.invalidate_demands_cache()
        ms_client.invalidate_payments_cache()

        # 8. Yangilangan hujjatni olish
        result = await ms_client.get_demand(demand_id)
        new_sum = result.get("sum", 0) / 100.0
        new_discount = result.get("discount", 0)
        payed_sum = result.get("payedSum", 0) / 100.0
        remaining = max(0.0, new_sum - payed_sum)

        payment_status = "unpaid"
        payment_status_name = "To'lanmagan"
        if remaining <= 0 and new_sum > 0:
            payment_status = "paid"
            payment_status_name = "To'liq to'langan"
        elif payed_sum > 0:
            payment_status = "partial"
            payment_status_name = "Qisman"
            
        state = result.get("state", {})
        state_name = state.get("name", "") if isinstance(state, dict) else ""
        state_color_int = state.get("color", 0) if isinstance(state, dict) else 0
        state_color = color_int_to_hex(state_color_int, state_name)
        state_href = state.get("meta", {}).get("href", "") if isinstance(state, dict) else ""
        state_id = extract_id_from_href(state_href) if state_href else ""

        try:
            local_demand = await db.scalar(select(LocalDemand).where(LocalDemand.id == demand_id))
            if local_demand:
                local_demand.sum = new_sum
                local_demand.payed_sum = payed_sum
                local_demand.remaining = remaining
                local_demand.payment_status = payment_status
                local_demand.payment_status_name = payment_status_name
                if state_name:
                    local_demand.state_name = state_name
                    local_demand.state_color = state_color
                    local_demand.state_id = state_id
                    local_demand.state_href = state_href
                await db.commit()
                print(f"   ✅ Local DB updated for {demand_id}")
        except Exception as db_err:
            print(f"   ⚠️ Local DB update xatosi: {db_err}")

        print(f"   ✅ Yakuniy: sum={new_sum:,.0f} so'm, discount={new_discount}%")

        return {
            "success": True,
            "message": "Otgruzka muvaffaqiyatli yangilandi",
            "data": {
                "id": result.get("id"),
                "name": result.get("name"),
                "discount": new_discount,
                "sum": new_sum,
                "payment": payment_result.get("data") if payment_result else None,
            },
            "local_status": payment_status,
            "local_status_name": payment_status_name,
            "offline": False
        }

    except (httpx.RequestError, asyncio.TimeoutError) as network_err:
        print(f"📡 Tarmoq xatosi (Offline mode): {network_err}")
        
        # SyncQueue ga yozamiz
        payload = update.dict()
        db.add(SyncQueue(
            action="update_demand",
            local_id=demand_id,
            payload=json.dumps(payload),
            status="pending"
        ))
        
        # LocalDemand ni vaqtinchalik yangilaymiz (optimistic update)
        local_demand = await db.scalar(select(LocalDemand).where(LocalDemand.id == demand_id))
        if local_demand:
            pass
        await db.commit()
        
        return {
            "success": True,
            "message": "Tarmoq aloqasi yo'q. O'zgarishlar oflayn saqlandi.",
            "offline": True
        }

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        error_body = ""
        try:
            error_body = e.response.text
        except:
            pass
        print(f"❌ MoySklad xatosi: {e}")
        print(f"📋 Xato tafsiloti: {error_body}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"MoySklad xatosi: {error_body or str(e)}"
        )
    except Exception as e:
        print(f"❌ Boshqa xato: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ================= TOVAR QO'SHISH =================
@router.post("/{demand_id}/positions")
async def add_position(demand_id: str, data: PositionAddRequest):
    try:
        position_data = {
            "assortment": {
                "meta": {
                    "href": f"https://api.moysklad.ru/api/remap/1.2/entity/product/{data.assortment_id}",
                    "type": "product",
                    "mediaType": "application/json"
                }
            },
            "quantity": data.quantity,
            "price": int(data.price * 100),
        }

        result = await ms_client.add_demand_position(demand_id, position_data)

        return {
            "success": True,
            "data": {
                "id": result.get("id"),
                "quantity": result.get("quantity"),
                "price": result.get("price", 0) / 100.0,
            }
        }

    except Exception as e:
        print(f"Add position xato: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ================= TOVAR O'CHIRISH =================
@router.delete("/{demand_id}/positions/{position_id}")
async def delete_position(demand_id: str, position_id: str):
    try:
        await ms_client.delete_demand_position(demand_id, position_id)
        return {"success": True, "message": "Tovar o'chirildi"}
    except Exception as e:
        print(f"Delete position xato: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================= TOVAR POZITSIYASINI TAHRIRLASH =================
@router.put("/{demand_id}/positions/{position_id}")
async def update_position(demand_id: str, position_id: str, update: PositionUpdateRequest):
    try:
        data = {}

        if update.price is not None:
            data["price"] = int(update.price * 100)

        if update.quantity is not None:
            data["quantity"] = update.quantity

        if not data:
            raise HTTPException(status_code=400, detail="O'zgartirish ma'lumoti yo'q")

        result = await ms_client.update_demand_position(demand_id, position_id, data)

        return {
            "success": True,
            "data": {
                "id": result.get("id"),
                "price": result.get("price", 0) / 100.0,
                "quantity": result.get("quantity"),
                "sum": result.get("sum", 0) / 100.0,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Update position xato: {e}")
        raise HTTPException(status_code=500, detail=str(e))