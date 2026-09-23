import asyncio
import time
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
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


class CorrectionRequest(BaseModel):
    counterparty_id: str
    new_balance: Optional[float] = None
    adjustment_amount: Optional[float] = None
    reason: str = "Balansni tuzatish"
    moment: Optional[str] = None  # "YYYY-MM-DD" formati, bo'sh bo'lsa hozirgi vaqt


@router.get("/")
async def list_customers(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    sort_by: str = Query("balance"),
    sort_dir: str = Query("desc"),
    debt_filter: Optional[str] = Query("all"),
    db: AsyncSession = Depends(get_db)
):
    try:
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

        # 3. Tartiblash (Sorting)
        sort_column = LocalCounterparty.balance
        if sort_by == "name":
            sort_column = LocalCounterparty.name
        elif sort_by == "phone":
            sort_column = LocalCounterparty.phone
        elif sort_by == "date":
            sort_column = LocalCounterparty.updated_at

        if sort_dir == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)

        # 4. Global statistika va sahifalash
        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        
        # Global qarz summasini hisoblash (barcha qarzadorlar uchun)
        debt_query = select(func.sum(LocalCounterparty.balance)).where(LocalCounterparty.balance > 0)
        global_total_debt = await db.scalar(debt_query) or 0.0
        
        debtors_count_query = select(func.count(LocalCounterparty.id)).where(LocalCounterparty.balance > 0)
        global_debtors_count = await db.scalar(debtors_count_query) or 0
        
        total_customers_query = select(func.count(LocalCounterparty.id))
        total_customers = await db.scalar(total_customers_query) or 0

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
                "group": "—",
                "status": "—",
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
):
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

        return {
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
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Akt-sverka xatosi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correction")
async def create_correction(correction: CorrectionRequest):
    """Korrektirovka — cashin yoki cashout orqali"""
    try:
        # Joriy balansni aniq hisoblash (keshsiz!)
        
        # Barcha sotuvlar va to'lovlarni olib, aniq balansni hisoblash
        all_demands = await ms_client.get_all_demands_cached()
        all_payments = await ms_client.get_all_payments_cached()
        target_href = f"/entity/counterparty/{correction.counterparty_id}"
        
        total_sales = 0.0
        for d in all_demands:
            agent_href = d.get("agent", {}).get("meta", {}).get("href", "")
            if target_href in agent_href:
                total_sales += d.get("sum", 0) / 100.0
        
        total_paid = 0.0
        for c in all_payments["cashins"]:
            agent_href = c.get("agent", {}).get("meta", {}).get("href", "")
            if target_href in agent_href:
                total_paid += c.get("sum", 0) / 100.0
        for p in all_payments["paymentins"]:
            agent_href = p.get("agent", {}).get("meta", {}).get("href", "")
            if target_href in agent_href:
                total_paid += p.get("sum", 0) / 100.0

        current_balance = total_sales - total_paid
        
        # Mahalliy bazadan aniq qoldiqni olish (chunki avvalgi korrektirovkalar bor bo'lishi mumkin)
        from database import AsyncSessionLocal
        from sqlalchemy import select
        from models_db import LocalCounterparty
        async with AsyncSessionLocal() as db:
            cp = await db.scalar(select(LocalCounterparty).where(LocalCounterparty.id == correction.counterparty_id))
            if cp and cp.balance is not None:
                current_balance = cp.balance
        
        if correction.adjustment_amount is not None:
            diff = -correction.adjustment_amount
            final_new_balance = current_balance + diff
        elif correction.new_balance is not None:
            final_new_balance = correction.new_balance
            diff = final_new_balance - current_balance
        else:
            diff = 0.0
            final_new_balance = current_balance

        print(f"📊 Korreksiya: joriy={current_balance:,.0f}, yangi={final_new_balance:,.0f}, farq={diff:,.0f}")
        
        if abs(diff) < 0.01:
            return {
                "success": True,
                "data": {"message": "Balans o'zgarmagan", "balance": current_balance}
            }
        
        # Tashkilot olish
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
        moment_str = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        
        purpose = f"КОРРЕКТИРОВКА: {correction.reason}"

        # Sana va vaqt: agar ko'rsatilgan bo'lsa, uni to'liq soati bilan ishlatamiz
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
                moment_str = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            moment_str = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

        # Корректировка взаиморасчетов (counterpartyadjustment)
        adjustment_data = {
            "agent": {"meta": agent_meta},
            "organization": {"meta": org_meta},
            "sum": int(diff * 100),  # diff manfiy bo'lsa qarz kamayadi, musbat bo'lsa oshadi
            "moment": moment_str,
            "description": purpose,
        }
        
        try:
            result = await ms_client._request("POST", "/entity/counterpartyadjustment", json_data=adjustment_data)
            print(f"✅ Корректировка взаиморасчетов: {diff:,.0f} so'm o'zgartirildi")
            
            # Update local DB for instant feedback
            from database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                from models_db import LocalCounterparty
                cp = await db.scalar(select(LocalCounterparty).where(LocalCounterparty.id == correction.counterparty_id))
                if cp:
                    cp.balance = final_new_balance
                    await db.commit()
        except Exception as e:
            print(f"⚠️ counterpartyadjustment xatosi: {e}")
            raise
        
        # Keshlarni tozalash
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
        # 1. Mijoz ma'lumotlari
        cp = await ms_client.get_counterparty(customer_id)
        if not cp:
            raise HTTPException(status_code=404, detail="Mijoz topilmadi")

        target_href = f"/entity/counterparty/{customer_id}"

        # 2. Sotuvlar va to'lovlarni SQLite lokal bazasidan o'ta tezkor olish (0.05s)
        formatted_demands = []
        payments = []
        from database import AsyncSessionLocal
        from models_db import LocalDemand, LocalPayment, LocalCounterparty

        async with AsyncSessionLocal() as db:
            local_cp = await db.scalar(select(LocalCounterparty).where(LocalCounterparty.id == customer_id))

            d_rows = (await db.execute(
                select(LocalDemand).where(LocalDemand.agent_id == customer_id).order_by(desc(LocalDemand.moment))
            )).scalars().all()
            for d in d_rows:
                formatted_demands.append({
                    "id": d.id, "name": d.name, "moment": d.moment,
                    "sum": d.sum, "payed_sum": d.payed_sum, "remaining": d.remaining,
                    "status": d.payment_status, "status_name": d.payment_status_name,
                })

            p_rows = (await db.execute(
                select(LocalPayment).where(LocalPayment.agent_id == customer_id).order_by(desc(LocalPayment.moment))
            )).scalars().all()
            for p in p_rows:
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
                })

        # Agar lokal DB da hali bo'lmasa, MoySklad keshidan zaxira olish
        if not formatted_demands and not payments:
            all_demands = await ms_client.get_all_demands_cached()
            for d in all_demands:
                agent_href = d.get("agent", {}).get("meta", {}).get("href", "")
                if target_href not in agent_href:
                    continue
                demand_sum = d.get("sum", 0) / 100.0
                payed_sum = d.get("payedSum", 0) / 100.0
                remaining = max(0.0, demand_sum - payed_sum)
                if remaining <= 0.01:
                    status, status_name = "paid", "To'langan"
                elif payed_sum > 0:
                    status, status_name = "partial", "Qisman"
                else:
                    status, status_name = "unpaid", "To'lanmagan"
                formatted_demands.append({
                    "id": d.get("id"), "name": d.get("name"), "moment": d.get("moment"),
                    "sum": demand_sum, "payed_sum": payed_sum, "remaining": remaining,
                    "status": status, "status_name": status_name,
                })
            formatted_demands.sort(key=lambda x: x["moment"], reverse=True)

            all_payments = await ms_client.get_all_payments_cached()
            for c in all_payments.get("cashins", []):
                if target_href in c.get("agent", {}).get("meta", {}).get("href", ""):
                    rate_obj = c.get("rate") or {}
                    rate_val = float(rate_obj.get("value") or 0.0)
                    curr_href = rate_obj.get("currency", {}).get("meta", {}).get("href", "")
                    is_usd = bool("45062adb" in curr_href or "usd" in curr_href.lower() or rate_val > 1)
                    raw_sum = c.get("sum", 0) / 100.0
                    usd_amt = raw_sum if is_usd else 0.0
                    sum_uzs = (usd_amt * rate_val) if is_usd else raw_sum
                    payments.append({
                        "id": c.get("id"), "type": "cash",
                        "type_name": "💲 Dollar" if is_usd else "💵 Naqd",
                        "amount": sum_uzs, "moment": c.get("moment"),
                        "is_usd": is_usd, "usd_amount": usd_amt, "usd_rate": rate_val,
                        "purpose": c.get("paymentPurpose", "") or "",
                    })
            for p in all_payments.get("paymentins", []):
                if target_href in p.get("agent", {}).get("meta", {}).get("href", ""):
                    rate_obj = p.get("rate") or {}
                    rate_val = float(rate_obj.get("value") or 0.0)
                    curr_href = rate_obj.get("currency", {}).get("meta", {}).get("href", "")
                    is_usd = bool("45062adb" in curr_href or "usd" in curr_href.lower() or rate_val > 1)
                    raw_sum = p.get("sum", 0) / 100.0
                    usd_amt = raw_sum if is_usd else 0.0
                    sum_uzs = (usd_amt * rate_val) if is_usd else raw_sum
                    payments.append({
                        "id": p.get("id"), "type": "card",
                        "type_name": "💲 Dollar" if is_usd else "💳 Karta",
                        "amount": sum_uzs, "moment": p.get("moment"),
                        "is_usd": is_usd, "usd_amount": usd_amt, "usd_rate": rate_val,
                        "purpose": p.get("paymentPurpose", "") or "",
                    })

        # 3. Korrektirovkalar ro'yxatini olish (/entity/counterpartyadjustment)
        adjustments = []
        try:
            adj_resp = await ms_client._request("GET", "/entity/counterpartyadjustment", params={"limit": 100})
            for adj in adj_resp.get("rows", []):
                agent_href = adj.get("agent", {}).get("meta", {}).get("href", "")
                if target_href in agent_href:
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
        except Exception as adje:
            print(f"⚠️ Adjustment detail xatosi: {adje}")

        all_payments_and_adj = payments + adjustments
        all_payments_and_adj.sort(key=lambda x: x.get("moment", ""), reverse=True)

        total_sales = sum(d["sum"] for d in formatted_demands)
        total_paid = sum(p["amount"] for p in payments)

        # Balans to'g'ridan-to'g'ri Local DB dan olinadi (sinxronlangan MoySklad nativ balansi)
        balance = local_cp.balance if local_cp else 0.0

        # Kontragent teglari (Guruhlar)
        cp_tags = cp.get("tags", [])
        active_group = cp_tags[0] if cp_tags else (getattr(local_cp, 'group', '') if local_cp else "")

        # State va boshqa metadata
        state = cp.get("state")
        metadata = await ms_client.get_counterparty_metadata()
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