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
from sqlalchemy import select, func, or_, desc, asc, delete
from database import get_db
from models_db import LocalDemand, LocalAssortment, SyncQueue, LocalDemandPosition, LocalPayment
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


class QuickReturnRequest(BaseModel):
    position_id: str
    return_quantity: float
    reason: Optional[str] = "Mijozdan qaytarildi"
    cash_action: Optional[str] = None  # "cashout" | None
    cash_account_id: Optional[str] = None
    cash_amount: Optional[float] = None


class QuickSwapRequest(BaseModel):
    position_id: str
    new_assortment_id: str
    quantity: float
    new_price: Optional[float] = None
    reason: Optional[str] = "Tovar adashib ketganligi sababli almashtirildi"
    cash_action: Optional[str] = None  # "cashin" | "cashout" | None
    cash_account_id: Optional[str] = None
    cash_amount: Optional[float] = None


class DemandUpdateRequest(BaseModel):
    agent_id: Optional[str] = None
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
    sort_by: Optional[str] = Query(None, description="name, moment, agent_name, sum, remaining, state_name, payment_status"),
    sort_dir: Optional[str] = Query("desc", description="asc yoki desc"),
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

            # Ustun bo'yicha server-side saralash (butun baza bo'yicha)
            sort_map = {
                "name": LocalDemand.name,
                "moment": LocalDemand.moment,
                "agent_name": LocalDemand.agent_name,
                "sum": LocalDemand.sum,
                "remaining": LocalDemand.remaining,
                "state_name": LocalDemand.state_name,
                "payment_status": LocalDemand.payment_status,
            }
            order_col = sort_map.get(sort_by, LocalDemand.moment)
            order_expr = asc(order_col) if sort_dir and sort_dir.lower() == "asc" else desc(order_col)

            total_filtered = (await db.scalar(count_query)) or 0
            results = (await db.execute(
                query.order_by(order_expr).offset(clean_offset).limit(clean_limit)
            )).scalars().all()

            formatted_results = [
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
            ]

            # Agar qidiruv (search) berilgan bo'lsa va 1-sahifada bo'lsa,
            # MoySklad API dan ham parallel qidirib, lokal DB da bo'lmagan sotuvlarni qo'shamiz
            if search and clean_offset == 0:
                try:
                    s_clean = search.strip()
                    api_search_resp = await ms_client._request(
                        "GET",
                        "/entity/demand",
                        params={"search": s_clean, "limit": 20, "order": "moment,desc", "expand": "agent,state"}
                    )
                    api_search_rows = api_search_resp.get("rows", [])
                    existing_result_ids = {item["id"] for item in formatted_results}
                    newly_found = []
                    new_api_demands = []

                    for ad in api_search_rows:
                        adid = ad.get("id")
                        if not adid or adid in existing_result_ids:
                            continue

                        agent_obj = ad.get("agent", {}) if isinstance(ad.get("agent"), dict) else {}
                        agent_href = agent_obj.get("meta", {}).get("href", "")
                        agent_id = agent_href.rstrip("/").split("/")[-1] if agent_href else ""
                        agent_name = agent_obj.get("name") or "Noma'lum"

                        state_obj = ad.get("state", {}) if isinstance(ad.get("state"), dict) else {}
                        state_name = state_obj.get("name", "—")
                        state_href = state_obj.get("meta", {}).get("href", "")
                        state_id = state_href.rstrip("/").split("/")[-1] if state_href else ""

                        d_sum = ad.get("sum", 0) / 100.0
                        d_payed = ad.get("payedSum", 0) / 100.0
                        d_rem = max(0.0, d_sum - d_payed)
                        if d_rem <= 0.01:
                            p_status = "paid"
                            p_status_name = "To'langan"
                        elif d_payed > 0:
                            p_status = "partial"
                            p_status_name = "Qisman"
                        else:
                            p_status = "unpaid"
                            p_status_name = "To'lanmagan"

                        new_item = {
                            "id": adid,
                            "name": ad.get("name", ""),
                            "moment": ad.get("moment", ""),
                            "sum": d_sum,
                            "payed_sum": d_payed,
                            "remaining": d_rem,
                            "payment_status": p_status,
                            "payment_status_name": p_status_name,
                            "state_name": state_name,
                            "state_color": "#009fe3",
                            "state_id": state_id,
                            "state_href": state_href,
                            "agent_name": agent_name,
                            "agent_id": agent_id,
                            "description": ad.get("description", "") or "",
                        }
                        newly_found.append(new_item)
                        new_api_demands.append(ad)

                    if newly_found:
                        formatted_results.extend(newly_found)
                        formatted_results.sort(key=lambda x: x.get("moment", ""), reverse=True)
                        total_filtered += len(newly_found)
                        from routers.customers import persist_missing_demands_to_db
                        asyncio.create_task(persist_missing_demands_to_db(new_api_demands, "", ""))
                except Exception as ex:
                    pass

            return {
                "success": True,
                "data": formatted_results,
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
            order="moment,desc",
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

# ================= TOVAR QIDIRISH (ANIQ VA TEZKOR RELEVANCE REYTING) =================
def calculate_product_relevance(item: dict, q_clean: str) -> int:
    q_lower = q_clean.lower()
    code = (item.get("code") or "").strip()
    article = (item.get("article") or "").strip()
    barcode = (item.get("barcode") or "").strip()
    name = (item.get("name") or "").strip()
    name_lower = name.lower()
    
    code_lower = code.lower()
    art_lower = article.lower()
    bc_lower = barcode.lower()

    # 1. 100% Aniq moslik (Exact Match) -> 10,000 ball (Mutlaq birinchi o'rinda)
    if code_lower == q_lower or art_lower == q_lower or bc_lower == q_lower:
        return 10000
    if name_lower == q_lower:
        return 9500

    # 2. Agar foydalanuvchi nollar bilan kod yozgan bo'lsa (masalan "00144"):
    # Qat'iy qoida: faqat aynan '00144' bilan boshlanadigan yoki ichida to'liq bo'lganlar!
    # Hech qachon 01144, 01440, 01443 kabi boshqa kodlarni chiqarmaymiz (Score = 0)
    if q_clean.startswith("0"):
        if code_lower.startswith(q_lower) or art_lower.startswith(q_lower):
            return 8000 - len(code)
        if bc_lower.startswith(q_lower):
            return 7000
        if name_lower.startswith(q_lower):
            return 6000
        if q_lower in code_lower or q_lower in art_lower:
            return 5000 - len(code)
        if q_lower in bc_lower or q_lower in name_lower:
            return 4000
        return 0

    # 3. Agar toza son bo'lsa (boshida 0 yo'q, masalan "144"):
    if q_clean.isdigit():
        q_int = int(q_clean)
        if code.isdigit() and int(code) == q_int:
            return 9000 - len(code)
        if article.isdigit() and int(article) == q_int:
            return 8900 - len(article)

    # 4. Boshlanish mosligi (Prefix Match)
    if code_lower.startswith(q_lower) or art_lower.startswith(q_lower):
        return 7000 - len(code)
    if bc_lower.startswith(q_lower):
        return 6500
    if name_lower.startswith(q_lower):
        return 6000
    words = name_lower.split()
    if any(w.startswith(q_lower) for w in words):
        return 5000

    # 5. Qisman moslik (Substring Match - faqat to'liq matn mavjud bo'lsa)
    if q_lower in code_lower or q_lower in art_lower:
        return 3000 - len(code)
    if q_lower in bc_lower:
        return 2500
    if q_lower in name_lower:
        return 2000

    return 0


@router.get("/search/assortment")
async def search_assortment(query: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db)):
    try:
        q_clean = query.strip()
        search_pattern = f"%{q_clean}%"
        
        # 1. DB dan qidiramiz
        conditions = [
            LocalAssortment.name.ilike(search_pattern),
            LocalAssortment.code.ilike(search_pattern),
            LocalAssortment.article.ilike(search_pattern),
            LocalAssortment.barcode.ilike(search_pattern)
        ]
        
        # Agar nolsiz son kiritilgan bo'lsa (masalan "144"), nollar bilan to'ldirilgan variantlarni ham qo'shamiz (masalan "00144")
        if q_clean.isdigit() and not q_clean.startswith("0"):
            for pad in [f"0{q_clean}", f"00{q_clean}", f"000{q_clean}", f"0000{q_clean}"]:
                conditions.append(LocalAssortment.code == pad)
                conditions.append(LocalAssortment.article == pad)

        stmt = select(LocalAssortment).where(or_(*conditions)).limit(60)
        results = (await db.execute(stmt)).scalars().all()

        candidates = []
        seen_ids = set()
        for item in results:
            seen_ids.add(item.id)
            candidates.append({
                "id": item.id,
                "name": item.name or "",
                "code": item.code or "",
                "article": item.article or "",
                "barcode": item.barcode or "",
                "price": item.price,
                "quantity": item.quantity,
            })

        # 2. Agar natijalar kam bo'lsa, to'g'ridan-to'g'ri MoySklad API dan ham qidiramiz
        if len(candidates) < 3:
            try:
                ms_results = await ms_client.search_assortment_enhanced(q_clean)
                for item in ms_results.get("rows", []):
                    item_id = item.get("id")
                    if not item_id or item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    price = 0
                    if item.get("salePrices") and len(item.get("salePrices", [])) > 0:
                        price = item["salePrices"][0].get("value", 0) / 100.0
                    elif item.get("salePrice"):
                        price = item.get("salePrice", 0) / 100.0
                    
                    barcodes = item.get("barcodes", [])
                    barcode = ""
                    if barcodes:
                        bc = barcodes[0]
                        barcode = str(list(bc.values())[0]) if isinstance(bc, dict) and bc else str(bc)

                    code_val = item.get("code") or ""
                    art_val = item.get("article") or ""
                    
                    candidates.append({
                        "id": item_id,
                        "name": item.get("name", ""),
                        "code": code_val,
                        "article": art_val,
                        "barcode": barcode,
                        "price": price,
                        "quantity": item.get("quantity", 0),
                    })

                    try:
                        db.add(LocalAssortment(
                            id=item_id,
                            name=item.get("name", ""),
                            code=code_val,
                            article=art_val,
                            barcode=barcode,
                            price=price,
                            quantity=item.get("quantity", 0)
                        ))
                    except:
                        pass
                await db.commit()
            except Exception as ms_err:
                print(f"⚠️ MoySklad live assortment search xatosi: {ms_err}")

        # 3. Aniq reyting (Relevance Scoring) hisoblash va saralash
        ranked_list = []
        for cand in candidates:
            score = calculate_product_relevance(cand, q_clean)
            if score > 0:
                ranked_list.append((score, cand))

        # Ball bo'yicha kamayish tartibida saralaymiz (Score DESC, len(code) ASC)
        ranked_list.sort(key=lambda x: (-x[0], len(x[1].get("code") or "")))

        formatted = []
        for score, item in ranked_list[:30]:
            code_display = item.get("code") or item.get("article") or "—"
            formatted.append({
                "id": item["id"],
                "name": item["name"],
                "code": code_display,
                "barcode": item.get("barcode") or "—",
                "price": item["price"],
                "quantity": item["quantity"],
                "score": score
            })

        print(f"🔍 Tovar qidiruv '{q_clean}': {len(formatted)} ta saralangan natija")
        return {"success": True, "data": formatted}

    except Exception as e:
        print(f"❌ DB Search assortment xato: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ================= SINX DIAGNOSTIKA =================
@router.get("/sync-debug")
async def sync_debug(
    search_name: Optional[str] = Query(None, description="Sotuv nomi bo'yicha qidirish (masalan: 01273)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Sinxronizatsiya diagnostikasi: MoySklad API va lokal DB ni solishtirish.
    01273 sotuv kelmagan? - Shu endpoint orqali tekshirish mumkin.
    """
    from datetime import datetime, timedelta
    import time as t_mod

    result = {
        "server_time": datetime.now().isoformat(),
        "server_timezone": t_mod.strftime("%z"),
    }

    # 1. Lokal DB da bu sotuv bormi?
    if search_name:
        s_term = f"%{search_name.strip()}%"
        local_query = select(LocalDemand).where(
            or_(LocalDemand.name.ilike(s_term), LocalDemand.description.ilike(s_term))
        )
        local_results = (await db.execute(local_query)).scalars().all()
        result["local_db_found"] = [
            {
                "id": d.id,
                "name": d.name,
                "moment": d.moment,
                "sum": d.sum,
                "agent_name": d.agent_name,
                "state_name": d.state_name,
            }
            for d in local_results
        ]
        result["local_db_count"] = len(local_results)

        # 2. MoySklad API'dan to'g'ridan-to'g'ri qidirish
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            api_resp = await ms_client.get_demands(
                limit=100,
                offset=0,
                moment_from=f"{today_str} 00:00:00",
                moment_to=f"{today_str} 23:59:59",
                order="moment,desc"
            )
            api_rows = api_resp.get("rows", [])
            api_meta = api_resp.get("meta", {})
            
            matched_api = []
            for d in api_rows:
                name = d.get("name", "")
                if search_name.lower() in name.lower():
                    agent = d.get("agent", {})
                    matched_api.append({
                        "id": d.get("id"),
                        "name": name,
                        "moment": d.get("moment"),
                        "sum": d.get("sum", 0) / 100.0,
                        "agent_name": agent.get("name", "?") if isinstance(agent, dict) else "?",
                        "created": d.get("created"),
                        "updated": d.get("updated"),
                    })
            
            result["moysklad_api_today_total"] = api_meta.get("size", 0)
            result["moysklad_api_matched"] = matched_api
            result["moysklad_api_matched_count"] = len(matched_api)
        except Exception as e:
            result["moysklad_api_error"] = str(e)

    # 3. Umumiy statistika
    total_local = await db.scalar(select(func.count(LocalDemand.id)))
    result["total_local_demands"] = total_local or 0

    # 4. Eng oxirgi 5 ta lokal sotuv (moment bo'yicha)
    latest_local = (await db.execute(
        select(LocalDemand).order_by(desc(LocalDemand.moment)).limit(5)
    )).scalars().all()
    result["latest_local_demands"] = [
        {"name": d.name, "moment": d.moment, "agent_name": d.agent_name}
        for d in latest_local
    ]

    # 5. Sync log
    try:
        from models_db import SyncLog
        latest_sync = (await db.execute(
            select(SyncLog).order_by(desc(SyncLog.synced_at)).limit(3)
        )).scalars().all()
        result["latest_sync_logs"] = [
            {
                "entity_type": s.entity_type,
                "records_synced": s.records_synced,
                "status": s.status,
                "message": s.message,
                "synced_at": s.synced_at.isoformat() if s.synced_at else None,
            }
            for s in latest_sync
        ]
    except Exception as e:
        result["sync_log_error"] = str(e)

    return {"success": True, "data": result}


# ================= TO'LIQ ARXIV SINXRONIZATSIYASI =================
@router.post("/sync-full")
async def trigger_full_sync():
    """
    Butun MoySklad bazasidagi barcha sotuvlarni (sana cheklovisiz) to'liq yuklab olish.
    """
    res = await sync_all_data(force_full=True)
    count = res.get("count", 0) if isinstance(res, dict) else 0
    return {
        "success": True,
        "count": count,
        "message": f"To'liq arxiv sinxronlandi. Jami {count} ta sotuv bazaga yuklandi."
    }


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
        
        # Mijozning umumiy balansi (qarzi) - Mahalliy SQLite dan 0.5ms da olish
        agent_balance = 0.0
        if agent_id:
            try:
                async with AsyncSessionLocal() as session:
                    from models_db import LocalCounterparty
                    stmt = select(LocalCounterparty).where(LocalCounterparty.id == agent_id)
                    res = await session.execute(stmt)
                    cp_row = res.scalar_one_or_none()
                    if cp_row:
                        agent_balance = float(cp_row.balance or 0.0)
                        if not agent_phone and cp_row.phone:
                            agent_phone = cp_row.phone
                    else:
                        agent_balance = (agent.get("balance", 0) or 0) / 100.0
            except Exception as be:
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

            item_color = ""
            attributes = assortment.get("attributes", [])
            for attr in attributes:
                if attr.get("name") == "Цвет":
                    val = attr.get("value", "")
                    if isinstance(val, dict):
                        item_color = val.get("name", "")
                    else:
                        item_color = str(val)
                    break

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
                "color": item_color,
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

        demand_payed_sum = float(demand.get("payedSum", 0) or 0) / 100.0
        # MoySkladning payedSum maydoni har doim rasmiy haqiqat manbai (bog'langan to'lovlarning ortiqcha qismini chiqarib tashlaydi)
        if demand_payed_sum > 0:
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


# ================= OTGRUZKANI YARATISH VA TAHRIRLASH =================
@router.post("")
@router.post("/")
async def create_demand_endpoint(update: DemandUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Yangi sotuv (otgruzka) yaratish"""
    try:
        if not update.agent_id:
            raise HTTPException(status_code=400, detail="Mijoz (kontragent) tanlanishi shart")

        org = await ms_client.get_organization()
        org_id = org.get("id") or "default"

        pos_items = []
        all_positions = (update.positions or []) + (update.added_positions or [])
        for item in all_positions:
            assort_id = getattr(item, "assortment_id", None) or getattr(item, "position_id", None)
            if assort_id:
                pos_items.append({
                    "assortment": {
                        "meta": {
                            "href": f"https://api.moysklad.ru/api/remap/1.2/entity/product/{assort_id}",
                            "type": "product",
                            "mediaType": "application/json"
                        }
                    },
                    "quantity": item.quantity,
                    "price": int(item.price * 100),
                    "discount": getattr(item, "discount", 0) or 0
                })

        demand_payload = {
            "organization": {
                "meta": {
                    "href": f"https://api.moysklad.ru/api/remap/1.2/entity/organization/{org_id}",
                    "type": "organization",
                    "mediaType": "application/json"
                }
            },
            "agent": {
                "meta": {
                    "href": f"https://api.moysklad.ru/api/remap/1.2/entity/counterparty/{update.agent_id}",
                    "type": "counterparty",
                    "mediaType": "application/json"
                }
            },
            "positions": pos_items
        }

        if update.state_href:
            demand_payload["state"] = {
                "meta": {
                    "href": update.state_href,
                    "type": "state",
                    "mediaType": "application/json"
                }
            }

        created = await ms_client.create_demand(demand_payload)
        new_id = created.get("id")
        if not new_id:
            raise Exception("MoySklad'da yangi sotuv yaratilmadi")

        # Skidka qo'llash (agar bo'lsa)
        if (update.discount_type in ["sum", "percent"] and update.discount_value is not None) or update.discount is not None:
            try:
                positions_resp = await ms_client.get_demand_positions(new_id)
                positions = positions_resp.get("rows", [])
                if positions:
                    total_sum = sum(p.get("price", 0) * p.get("quantity", 0) for p in positions) / 100.0
                    if update.discount_type == "sum" and update.discount_value is not None:
                        discount_percent = (update.discount_value / total_sum) * 100 if total_sum > 0 else 0
                        discount_percent = min(discount_percent, 99.99)
                        discount_percent = math.floor(discount_percent * 1_000_000) / 1_000_000
                    elif update.discount_type == "percent" and update.discount_value is not None:
                        discount_percent = math.floor(update.discount_value * 1_000_000) / 1_000_000
                    elif update.discount is not None:
                        discount_percent = math.floor(update.discount * 1_000_000) / 1_000_000
                    else:
                        discount_percent = 0

                    batch_data = [{"id": p.get("id"), "discount": discount_percent} for p in positions if p.get("id")]
                    if batch_data:
                        await ms_client.update_demand_positions_batch(new_id, batch_data)
            except Exception as disc_err:
                print(f"   ⚠️ Skidka qo'llash xatosi: {disc_err}")

        # To'lov qabul qilish (agar summa kiritilgan bo'lsa)
        usd_amt = update.usd_amount or 0.0
        usd_rt = update.usd_rate or 12800.0
        total_payment = (update.cash_amount or 0.0) + (update.card_amount or 0.0) + (usd_amt * usd_rt)
        if total_payment > 0:
            try:
                from routers.payments import create_mixed_payment, MixedPaymentRequest
                payment_req = MixedPaymentRequest(
                    demand_id=new_id,
                    cash_amount=update.cash_amount or 0.0,
                    card_amount=update.card_amount or 0.0,
                    usd_amount=usd_amt,
                    usd_rate=usd_rt,
                    usd_account_id=update.usd_account_id,
                    account_id=update.account_id,
                    update_payment_attribute=bool(update.update_payment_attribute),
                )
                await create_mixed_payment(payment_req)
            except Exception as pay_err:
                print(f"   ⚠️ Yangi sotuv to'lov xatosi: {pay_err}")

        ms_client.invalidate_demands_cache()
        ms_client.invalidate_payments_cache()

        # Local DB ga yozish
        try:
            res_doc = await ms_client.get_demand(new_id)
            doc_sum = res_doc.get("sum", 0) / 100.0
            doc_payed = res_doc.get("payedSum", 0) / 100.0
            doc_rem = max(0.0, doc_sum - doc_payed)
            doc_status = "paid" if (doc_rem <= 0 and doc_sum > 0) else ("partial" if doc_payed > 0 else "unpaid")
            doc_status_name = "To'liq to'langan" if doc_status == "paid" else ("Qisman" if doc_status == "partial" else "To'lanmagan")
            
            st = res_doc.get("state", {})
            st_name = st.get("name", "Новый") if isinstance(st, dict) else "Новый"
            st_color = color_int_to_hex(st.get("color", 0) if isinstance(st, dict) else 0, st_name)
            agent_obj = res_doc.get("agent", {})
            agent_name = agent_obj.get("name", "") if isinstance(agent_obj, dict) else ""

            local_d = LocalDemand(
                id=new_id,
                name=res_doc.get("name", ""),
                moment=res_doc.get("moment", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
                sum=doc_sum,
                payed_sum=doc_payed,
                remaining=doc_rem,
                payment_status=doc_status,
                payment_status_name=doc_status_name,
                state_id=extract_id_from_href(st.get("meta", {}).get("href", "")) if isinstance(st, dict) and "meta" in st else "",
                state_name=st_name,
                state_color=st_color,
                state_href=st.get("meta", {}).get("href", "") if isinstance(st, dict) and "meta" in st else "",
                agent_id=update.agent_id,
                agent_name=agent_name,
                organization_id=org_id,
                raw_json=res_doc,
                updated_at=datetime.utcnow()
            )
            db.add(local_d)
            await db.commit()
        except Exception as ldb_err:
            print(f"   ⚠️ Local DB yangi sotuv qo'shish xatosi: {ldb_err}")

        return {
            "success": True,
            "message": "Yangi sotuv muvaffaqiyatli yaratildi",
            "data": {
                "id": new_id,
                "name": created.get("name", "")
            }
        }
    except Exception as e:
        print(f"❌ Yangi sotuv yaratish xatosi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{demand_id}")
async def update_demand(demand_id: str, update: DemandUpdateRequest, db: AsyncSession = Depends(get_db)):
    """
    Otgruzkani yangilash — batch update bilan optimallashtirilgan.
    Agar demand_id == 'new' bo'lsa yangi sotuv yaratadi.
    """
    if demand_id == "new":
        return await create_demand_endpoint(update, db)
    try:
        # Offline-first: Agar tarmoq xatosi bo'lsa, xatoni ushlab SyncQueue ga yozamiz
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

        # 4. Mijoz (Agent) va Status o'zgartirish
        doc_update = {}
        if update.agent_id:
            doc_update["agent"] = {
                "meta": {
                    "href": f"https://api.moysklad.ru/api/remap/1.2/entity/counterparty/{update.agent_id}",
                    "type": "counterparty",
                    "mediaType": "application/json"
                }
            }
            print(f"   👤 Mijoz almashtirilmoqda: {update.agent_id}")

        if update.state_href:
            doc_update["state"] = {
                "meta": {
                    "href": update.state_href,
                    "type": "state",
                    "mediaType": "application/json"
                }
            }
        elif update.state_id:
            doc_update["state"] = {
                "meta": {
                    "href": f"https://api.moysklad.ru/api/remap/1.2/entity/demand/metadata/states/{update.state_id}",
                    "type": "state",
                    "mediaType": "application/json"
                }
            }

        if doc_update:
            await ms_client.update_demand(demand_id, doc_update)

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
        try:
            from routers.payments import invalidate_cashflow_cache
            invalidate_cashflow_cache()
        except Exception:
            pass

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
                if update.agent_id:
                    local_demand.agent_id = update.agent_id
                    agent_obj = result.get("agent", {})
                    if isinstance(agent_obj, dict) and agent_obj.get("name"):
                        local_demand.agent_name = agent_obj.get("name")
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


# ================= TOVAR BO'YICHA SOTUVLARNI QIDIRISH (RETURN FINDER) =================
@router.get("/search/by-product")
async def search_demands_by_product(
    query: str = Query(..., min_length=1),
    assortment_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Tovar kodi, nomi, artikuli yoki shtrixkodi bo'yicha lokal SQLite bazadan 0.001 soniyada
    barcha sotuvlar (mijozlar) ro'yxatini aniq topish
    """
    try:
        q_clean = query.strip()
        matched_assortments = []
        matched_assortment_ids = set()

        # 1. Lokal bazadan tovarlarni qidirish (LocalAssortment)
        # Aniq kod bo'yicha yoki boshlanishi bo'yicha avval qidiramiz
        local_ass_q = select(LocalAssortment).where(
            or_(
                LocalAssortment.code == q_clean,
                LocalAssortment.article == q_clean,
                LocalAssortment.code.ilike(f"{q_clean}%"),
                LocalAssortment.article.ilike(f"{q_clean}%"),
                LocalAssortment.name.ilike(f"%{q_clean}%"),
                LocalAssortment.barcode == q_clean,
            )
        ).limit(15)
        local_ass_res = (await db.execute(local_ass_q)).scalars().all()

        for a in local_ass_res:
            matched_assortment_ids.add(a.id)
            matched_assortments.append({
                "id": a.id,
                "name": a.name,
                "code": a.code or a.article or "—",
                "barcode": a.barcode or "—",
                "price": a.price,
                "quantity": a.quantity
            })

        # 2. LocalDemandPosition jadvalidan sotuvlarni qidirish
        pos_conditions = []
        if assortment_id:
            pos_conditions.append(LocalDemandPosition.assortment_id == assortment_id)
        else:
            search_pattern = f"%{q_clean}%"
            or_clauses = [
                LocalDemandPosition.assortment_code == q_clean,
                LocalDemandPosition.assortment_code.ilike(f"{q_clean}%"),
                LocalDemandPosition.assortment_code.ilike(search_pattern),
                LocalDemandPosition.assortment_article.ilike(search_pattern),
                LocalDemandPosition.assortment_name.ilike(search_pattern),
                LocalDemandPosition.demand_name.ilike(search_pattern),
                LocalDemandPosition.agent_name.ilike(search_pattern),
            ]
            if matched_assortment_ids:
                or_clauses.append(LocalDemandPosition.assortment_id.in_(list(matched_assortment_ids)))
            pos_conditions.append(or_(*or_clauses))

        pos_q = select(LocalDemandPosition).where(*pos_conditions).order_by(
            desc(LocalDemandPosition.moment)
        ).limit(100)

        pos_rows = (await db.execute(pos_q)).scalars().all()

        matched_sales = []
        for p in pos_rows:
            if p.assortment_id not in matched_assortment_ids:
                matched_assortment_ids.add(p.assortment_id)
                matched_assortments.append({
                    "id": p.assortment_id,
                    "name": p.assortment_name,
                    "code": p.assortment_code or p.assortment_article or "—",
                    "barcode": p.assortment_barcode or "—",
                    "price": p.price,
                    "quantity": 0
                })

            matched_sales.append({
                "demand_id": p.demand_id,
                "demand_name": p.demand_name,
                "moment": p.moment,
                "agent_id": p.agent_id,
                "agent_name": p.agent_name or "Noma'lum",
                "state_name": p.state_name or "—",
                "state_color": p.state_color or "#64748b",
                "demand_sum": p.demand_sum,
                "demand_remaining": p.demand_remaining,
                "description": p.description or "",
                "position": {
                    "position_id": p.id,
                    "assortment_id": p.assortment_id,
                    "assortment_name": p.assortment_name,
                    "assortment_code": p.assortment_code or p.assortment_article or "—",
                    "quantity": p.quantity,
                    "price": p.price,
                    "discount": p.discount,
                    "total": p.total
                }
            })

        return {
            "success": True,
            "data": {
                "query": q_clean,
                "assortments": matched_assortments,
                "matched_sales": matched_sales,
                "total_matched": len(matched_sales)
            }
        }
    except Exception as e:
        print(f"❌ search_demands_by_product error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ================= TEZKOR QAYTARISH (QUICK RETURN WITH AUDIT LOG) =================
@router.post("/{demand_id}/quick-return")
async def quick_return_position(
    demand_id: str,
    req: QuickReturnRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Sotuvdan tovar sonini kamaytirish yoki butunlay o'chirish (Vozvrat) va Izohga audit log yozish
    """
    try:
        # 1. Hujjat va pozitsiyalarni olish
        demand_task = ms_client.get_demand(demand_id)
        positions_task = ms_client.get_demand_positions(demand_id)
        demand, positions_resp = await asyncio.gather(demand_task, positions_task)

        positions = positions_resp.get("rows", [])
        target_pos = next((p for p in positions if p.get("id") == req.position_id), None)

        if not target_pos:
            raise HTTPException(status_code=404, detail="Ko'rsatilgan tovar pozitsiyasi ushbu sotuvda topilmadi")

        cur_qty = float(target_pos.get("quantity", 0))
        ret_qty = float(req.return_quantity)

        if ret_qty <= 0:
            raise HTTPException(status_code=400, detail="Qaytarish miqdori 0 dan katta bo'lishi kerak")

        if ret_qty > cur_qty:
            raise HTTPException(status_code=400, detail=f"Qaytarish miqdori mavjud sotuv miqdoridan ({cur_qty:g} ta) ko'p bo'lishi mumkin emas")

        price_raw = target_pos.get("price", 0)
        price_val = price_raw / 100.0
        refund_sum = ret_qty * price_val

        # 2. MoySklad'da pozitsiyani kamaytirish yoki o'chirish
        rem_qty = cur_qty - ret_qty
        if rem_qty <= 0:
            await ms_client.delete_demand_position(demand_id, req.position_id)
            print(f"   🗑️ Pozitsiya o'chirildi (to'liq qaytarildi): {req.position_id}")
        else:
            await ms_client.update_demand_position(
                demand_id,
                req.position_id,
                {"quantity": rem_qty, "price": price_raw}
            )
            print(f"   📉 Pozitsiya miqdori kamaytirildi: {cur_qty} -> {rem_qty}")

        # 3. Audit log tayyorlash va Izohga (description) qo'shish
        now_str = (datetime.now() + timedelta(hours=0)).strftime("%d.%m.%Y %H:%M")
        ass_name = target_pos.get("assortment", {}).get("name", "Tovar")

        reason_text = f" Sabab: {req.reason}." if req.reason else ""
        audit_line = f"🕒 {now_str} • ↩️ QAYTARILDI: \"{ass_name}\" ({ret_qty:g} dona x {price_val:,.0f} so'm = -{refund_sum:,.0f} so'm).{reason_text}"

        existing_desc = (demand.get("description") or "").strip()
        new_desc = f"{existing_desc}\n{audit_line}" if existing_desc else audit_line

        await ms_client.update_demand(demand_id, {"description": new_desc})
        ms_client.invalidate_demands_cache()

        # 4. Yangilangan holatni olish va DB ga sinxronlash
        updated_demand = await ms_client.get_demand(demand_id)
        new_sum = updated_demand.get("sum", 0) / 100.0
        payed_sum = updated_demand.get("payedSum", 0) / 100.0
        remaining = max(0.0, new_sum - payed_sum)

        try:
            ld = await db.scalar(select(LocalDemand).where(LocalDemand.id == demand_id))
            if ld:
                ld.sum = new_sum
                ld.remaining = remaining
                ld.description = new_desc

            # LocalDemandPosition yangilash
            local_pos = await db.scalar(select(LocalDemandPosition).where(LocalDemandPosition.id == req.position_id))
            if local_pos:
                if rem_qty <= 0:
                    await db.delete(local_pos)
                else:
                    local_pos.quantity = rem_qty
                    local_pos.total = rem_qty * price_val * (1 - local_pos.discount / 100.0)
                    local_pos.demand_sum = new_sum
                    local_pos.demand_remaining = remaining

            await db.commit()
        except Exception as dbe:
            print(f"LocalDemand / Position sync error: {dbe}")

        # 5. Kassa chiqimi (agar so'ralgan bo'lsa)
        cash_log = ""
        if req.cash_action == "cashout" and req.cash_amount and req.cash_amount > 0:
            try:
                c_amt = float(req.cash_amount)
                agent_href = demand.get("agent", {}).get("meta", {}).get("href", "")
                org_href = demand.get("organization", {}).get("meta", {}).get("href", "")
                if not org_href:
                    orgs = await ms_client.get_organizations()
                    if orgs:
                        org_href = orgs[0].get("meta", {}).get("href", "")

                p_moment = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                p_desc = f"Tovar qaytarish (Vozvrat) uchun to'landi: {ass_name} ({ret_qty:g} ta). Sotuv #{demand.get('name')}"

                if req.cash_account_id and req.cash_account_id != "cash":
                    pout_data = {
                        "organization": {"meta": {"href": org_href, "type": "organization"}},
                        "agent": {"meta": {"href": agent_href, "type": "counterparty"}},
                        "sum": int(c_amt * 100),
                        "moment": p_moment,
                        "paymentPurpose": p_desc,
                        "organizationAccount": {"meta": {"href": f"https://api.moysklad.ru/api/remap/1.2/entity/organization/{extract_id_from_href(org_href)}/accounts/{req.cash_account_id}", "type": "account"}}
                    }
                    res = await ms_client.create_paymentout(pout_data)
                    p_id = res.get("id")
                    p_type = "card"
                else:
                    cout_data = {
                        "organization": {"meta": {"href": org_href, "type": "organization"}},
                        "agent": {"meta": {"href": agent_href, "type": "counterparty"}},
                        "sum": int(c_amt * 100),
                        "moment": p_moment,
                        "paymentPurpose": p_desc
                    }
                    res = await ms_client.create_cashout(cout_data)
                    p_id = res.get("id")
                    p_type = "cash"

                if p_id:
                    agent_id = extract_id_from_href(agent_href)
                    db.add(LocalPayment(
                        id=p_id,
                        type=p_type,
                        name=res.get("name", ""),
                        sum=c_amt,
                        moment=p_moment,
                        demand_id=demand_id,
                        agent_id=agent_id,
                        purpose=p_desc
                    ))
                    await db.commit()
                    cash_log = f" • 💸 Kassadan chiqim: -{c_amt:,.0f} so'm"
            except Exception as cash_err:
                print(f"⚠️ Quick return cashout error: {cash_err}")

        return {
            "success": True,
            "message": f"✅ {ret_qty:g} dona tovar qaytarildi! Sotuv summasi -{refund_sum:,.0f} so'mga kamaytirildi.{cash_log}",
            "data": {
                "demand_id": demand_id,
                "refund_sum": refund_sum,
                "remaining_quantity": rem_qty,
                "new_demand_sum": new_sum,
                "new_remaining": remaining,
                "audit_entry": audit_line
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ quick_return_position error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ================= TEZKOR ALMASHTIRISH (QUICK SWAP WITH AUDIT LOG) =================
@router.post("/{demand_id}/quick-swap")
async def quick_swap_position(
    demand_id: str,
    req: QuickSwapRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Sotuvdagi tovarni boshqa tovar bilan almashtirish va Izohga audit log yozish
    """
    try:
        demand_task = ms_client.get_demand(demand_id)
        positions_task = ms_client.get_demand_positions(demand_id)
        demand, positions_resp = await asyncio.gather(demand_task, positions_task)

        positions = positions_resp.get("rows", [])
        target_pos = next((p for p in positions if p.get("id") == req.position_id), None)

        if not target_pos:
            raise HTTPException(status_code=404, detail="Almashtiriladigan tovar pozitsiyasi ushbu sotuvda topilmadi")

        old_price_val = (target_pos.get("price", 0)) / 100.0
        old_ass_name = target_pos.get("assortment", {}).get("name", "Eski tovar")

        # 1. Yangi tovar haqida ma'lumot olish
        new_ass_meta = {
            "href": f"https://api.moysklad.ru/api/remap/1.2/entity/product/{req.new_assortment_id}",
            "type": "product",
            "mediaType": "application/json"
        }
        new_ass_name = "Yangi tovar"
        new_ass_code = ""
        new_ass_article = ""
        new_ass_barcode = ""

        # Lokal bazadan yoki MoySklad'dan tekshiramiz
        local_ass = await db.scalar(select(LocalAssortment).where(LocalAssortment.id == req.new_assortment_id))
        if local_ass:
            new_ass_name = local_ass.name
            new_ass_code = local_ass.code
            new_ass_article = local_ass.article
            new_ass_barcode = local_ass.barcode
            if req.new_price is None:
                new_price_val = local_ass.price or old_price_val
            else:
                new_price_val = req.new_price
        else:
            try:
                ass_res = await ms_client._request("GET", f"/entity/assortment/{req.new_assortment_id}")
                new_ass_name = ass_res.get("name", "Yangi tovar")
                new_ass_code = ass_res.get("code", "")
                new_ass_article = ass_res.get("article", "")
                if ass_res.get("meta"):
                    new_ass_meta = ass_res.get("meta")
                if req.new_price is None:
                    if ass_res.get("salePrices") and len(ass_res.get("salePrices", [])) > 0:
                        new_price_val = ass_res["salePrices"][0].get("value", 0) / 100.0
                    else:
                        new_price_val = old_price_val
                else:
                    new_price_val = req.new_price
            except Exception:
                new_price_val = req.new_price or old_price_val

        new_price_raw = int(new_price_val * 100)
        swap_qty = float(req.quantity)

        # 2. Eski pozitsiyani o'chirib, yangisini qo'shamiz
        await ms_client.delete_demand_position(demand_id, req.position_id)

        new_pos_payload = {
            "assortment": {"meta": new_ass_meta},
            "quantity": swap_qty,
            "price": new_price_raw,
            "discount": target_pos.get("discount", 0)
        }
        add_res = await ms_client.add_demand_position(demand_id, new_pos_payload)
        new_pos_id = ""
        if isinstance(add_res, list) and len(add_res) > 0:
            new_pos_id = add_res[0].get("id", "")
        elif isinstance(add_res, dict):
            new_pos_id = add_res.get("id", "")

        # 3. Audit log tayyorlash
        old_total = swap_qty * old_price_val
        new_total = swap_qty * new_price_val
        diff_sum = new_total - old_total

        diff_str = f"Farq: {diff_sum:+,.0f} so'm" if diff_sum != 0 else "Farq: 0 so'm"
        now_str = (datetime.now() + timedelta(hours=0)).strftime("%d.%m.%Y %H:%M")
        reason_text = f" Sabab: {req.reason}." if req.reason else ""

        audit_line = f"🕒 {now_str} • 🔄 ALMASHTIRILDI: \"{old_ass_name}\" ({swap_qty:g} dona, {old_price_val:,.0f} so'm) ➡️ \"{new_ass_name}\" ({swap_qty:g} dona, {new_price_val:,.0f} so'm). {diff_str}.{reason_text}"

        existing_desc = (demand.get("description") or "").strip()
        new_desc = f"{existing_desc}\n{audit_line}" if existing_desc else audit_line

        await ms_client.update_demand(demand_id, {"description": new_desc})
        ms_client.invalidate_demands_cache()

        updated_demand = await ms_client.get_demand(demand_id)
        new_sum = updated_demand.get("sum", 0) / 100.0
        payed_sum = updated_demand.get("payedSum", 0) / 100.0
        remaining = max(0.0, new_sum - payed_sum)

        try:
            ld = await db.scalar(select(LocalDemand).where(LocalDemand.id == demand_id))
            if ld:
                ld.sum = new_sum
                ld.remaining = remaining
                ld.description = new_desc

            # Eski pozitsiyani LocalDemandPosition dan o'chirish
            old_local_pos = await db.scalar(select(LocalDemandPosition).where(LocalDemandPosition.id == req.position_id))
            if old_local_pos:
                await db.delete(old_local_pos)

            # Yangi pozitsiyani LocalDemandPosition ga yozish
            agent_id = extract_id_from_href(demand.get("agent", {}).get("meta", {}).get("href", "")) if demand.get("agent") else ""
            agent_name = demand.get("agent", {}).get("name", "")
            moment = demand.get("moment", "")
            state_name = demand.get("state", {}).get("name", "")

            created_pos = LocalDemandPosition(
                id=new_pos_id or f"{demand_id}_{req.new_assortment_id}",
                demand_id=demand_id,
                demand_name=demand.get("name", ""),
                agent_id=agent_id,
                agent_name=agent_name,
                moment=moment,
                state_name=state_name,
                demand_sum=new_sum,
                demand_remaining=remaining,
                assortment_id=req.new_assortment_id,
                assortment_name=new_ass_name,
                assortment_code=new_ass_code,
                assortment_article=new_ass_article,
                assortment_barcode=new_ass_barcode,
                quantity=swap_qty,
                price=new_price_val,
                discount=target_pos.get("discount", 0),
                total=new_total
            )
            db.add(created_pos)
            await db.commit()
        except Exception as dbe:
            print(f"Swap LocalDemandPosition update error: {dbe}")

        # 4. Kassa kirimi / chiqimi (agar so'ralgan bo'lsa)
        cash_log = ""
        if req.cash_action == "cashin" and req.cash_amount and req.cash_amount > 0:
            try:
                c_amt = float(req.cash_amount)
                agent_href = demand.get("agent", {}).get("meta", {}).get("href", "")
                org_href = demand.get("organization", {}).get("meta", {}).get("href", "")
                if not org_href:
                    orgs = await ms_client.get_organizations()
                    if orgs:
                        org_href = orgs[0].get("meta", {}).get("href", "")

                p_moment = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                p_desc = f"Tovar almashtirish (Swap) farqi uchun to'lov. Sotuv #{demand.get('name')}"

                operations = [{
                    "meta": demand.get("meta", {}),
                    "linkedSum": int(c_amt * 100)
                }]

                if req.cash_account_id and req.cash_account_id != "cash":
                    pin_data = {
                        "organization": {"meta": {"href": org_href, "type": "organization"}},
                        "agent": {"meta": {"href": agent_href, "type": "counterparty"}},
                        "sum": int(c_amt * 100),
                        "moment": p_moment,
                        "paymentPurpose": p_desc,
                        "operations": operations,
                        "organizationAccount": {"meta": {"href": f"https://api.moysklad.ru/api/remap/1.2/entity/organization/{extract_id_from_href(org_href)}/accounts/{req.cash_account_id}", "type": "account"}}
                    }
                    res = await ms_client.create_paymentin(pin_data)
                    p_id = res.get("id")
                    p_type = "card"
                else:
                    cin_data = {
                        "organization": {"meta": {"href": org_href, "type": "organization"}},
                        "agent": {"meta": {"href": agent_href, "type": "counterparty"}},
                        "sum": int(c_amt * 100),
                        "moment": p_moment,
                        "operations": operations,
                        "paymentPurpose": p_desc
                    }
                    res = await ms_client.create_cashin(cin_data)
                    p_id = res.get("id")
                    p_type = "cash"

                if p_id:
                    agent_id = extract_id_from_href(agent_href)
                    db.add(LocalPayment(
                        id=p_id,
                        type=p_type,
                        name=res.get("name", ""),
                        sum=c_amt,
                        moment=p_moment,
                        demand_id=demand_id,
                        agent_id=agent_id,
                        purpose=p_desc
                    ))
                    await db.commit()
                    cash_log = f" • 📥 Kassaga kirim: +{c_amt:,.0f} so'm"
            except Exception as cash_err:
                print(f"⚠️ Quick swap cashin error: {cash_err}")

        elif req.cash_action == "cashout" and req.cash_amount and req.cash_amount > 0:
            try:
                c_amt = float(req.cash_amount)
                agent_href = demand.get("agent", {}).get("meta", {}).get("href", "")
                org_href = demand.get("organization", {}).get("meta", {}).get("href", "")
                if not org_href:
                    orgs = await ms_client.get_organizations()
                    if orgs:
                        org_href = orgs[0].get("meta", {}).get("href", "")

                p_moment = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                p_desc = f"Tovar almashtirish (Swap) farqi qaytarildi. Sotuv #{demand.get('name')}"

                if req.cash_account_id and req.cash_account_id != "cash":
                    pout_data = {
                        "organization": {"meta": {"href": org_href, "type": "organization"}},
                        "agent": {"meta": {"href": agent_href, "type": "counterparty"}},
                        "sum": int(c_amt * 100),
                        "moment": p_moment,
                        "paymentPurpose": p_desc,
                        "organizationAccount": {"meta": {"href": f"https://api.moysklad.ru/api/remap/1.2/entity/organization/{extract_id_from_href(org_href)}/accounts/{req.cash_account_id}", "type": "account"}}
                    }
                    res = await ms_client.create_paymentout(pout_data)
                    p_id = res.get("id")
                    p_type = "card"
                else:
                    cout_data = {
                        "organization": {"meta": {"href": org_href, "type": "organization"}},
                        "agent": {"meta": {"href": agent_href, "type": "counterparty"}},
                        "sum": int(c_amt * 100),
                        "moment": p_moment,
                        "paymentPurpose": p_desc
                    }
                    res = await ms_client.create_cashout(cout_data)
                    p_id = res.get("id")
                    p_type = "cash"

                if p_id:
                    agent_id = extract_id_from_href(agent_href)
                    db.add(LocalPayment(
                        id=p_id,
                        type=p_type,
                        name=res.get("name", ""),
                        sum=c_amt,
                        moment=p_moment,
                        demand_id=demand_id,
                        agent_id=agent_id,
                        purpose=p_desc
                    ))
                    await db.commit()
                    cash_log = f" • 💸 Kassadan chiqim: -{c_amt:,.0f} so'm"
            except Exception as cash_err:
                print(f"⚠️ Quick swap cashout error: {cash_err}")

        return {
            "success": True,
            "message": f"✅ Tovar muvaffaqiyatli almashtirildi! {diff_str}{cash_log}",
            "data": {
                "demand_id": demand_id,
                "price_difference": diff_sum,
                "new_demand_sum": new_sum,
                "new_remaining": remaining,
                "audit_entry": audit_line
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ quick_swap_position error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))