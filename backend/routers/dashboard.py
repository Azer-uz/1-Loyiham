from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, timedelta
import time
import asyncio
from typing import Dict, List, Any, Optional
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_

from database import get_db
from models_db import LocalDemand, LocalCounterparty, LocalPayment
from moysklad_client import ms_client

router = APIRouter()

def to_tashkent_datetime(moment_str: str) -> Optional[datetime]:
    """MoySklad (Moskva UTC+3) vaqtini Toshkent (UTC+5, +2 soat) ga o'tkazish"""
    if not moment_str:
        return None
    try:
        clean = moment_str.split(".")[0].strip()
        dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
        return dt + timedelta(hours=2)
    except Exception:
        try:
            clean = moment_str[:10]
            return datetime.strptime(clean, "%Y-%m-%d") + timedelta(hours=2)
        except Exception:
            return None

def uz_to_msk_str(uz_dt_str: str) -> str:
    """Toshkent vaqtini MoySklad (Moskva -2 soat) vaqtiga o'tkazish"""
    if not uz_dt_str:
        return ""
    try:
        clean = uz_dt_str.split(".")[0].strip()
        if len(clean) == 10:
            clean += " 00:00:00"
        dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
        return (dt - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return uz_dt_str

_supplies_cache = {}

async def get_supplies_summary(moment_from: str, moment_to: str) -> dict:
    """Tanlangan davrdagi ombor kirimlari (Priemkalar) summasi va soni (Tezkor kesh)"""
    cache_key = f"{moment_from[:10]}_{moment_to[:10]}"
    now_ts = time.time()
    cached = _supplies_cache.get(cache_key)
    if cached and (now_ts - cached["ts"]) < 300:
        return cached["data"]
    
    try:
        filt = f"moment>={moment_from};moment<={moment_to}"
        resp = await asyncio.wait_for(
            ms_client._request("GET", "/entity/supply", params={"filter": filt, "limit": 100}),
            timeout=2.0
        )
        rows = resp.get("rows", [])
        total_sum = sum(s.get("sum", 0) / 100.0 for s in rows)
        res = {
            "count": len(rows),
            "sum": round(total_sum, 2)
        }
        _supplies_cache[cache_key] = {"data": res, "ts": now_ts}
        return res
    except Exception as e:
        if cached:
            return cached["data"]
        return {"count": 0, "sum": 0.0}


@router.get("/summary")
async def dashboard_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Dashboard ma'lumotlari: sotuvlar, to'lovlar, qarzdorlik (Local-first tezkor)"""
    try:
        today = datetime.now()
        if date_from and date_to:
            moment_from = f"{date_from} 00:00:00"
            moment_to = f"{date_to} 23:59:59"
            period_name = f"{date_from} — {date_to}"
        else:
            moment_from = today.strftime("%Y-%m-%d 00:00:00")
            moment_to = today.strftime("%Y-%m-%d 23:59:59")
            period_name = "Bugun"

        start_time = datetime.now()

        # 1. Avval tezkor lokal DB dan tekshiramiz
        total_local_demands = await db.scalar(select(func.count(LocalDemand.id)))
        if total_local_demands and total_local_demands > 0:
            conditions = [
                LocalDemand.moment >= moment_from,
                LocalDemand.moment <= moment_to,
            ]

            stmt = select(
                func.count(LocalDemand.id),
                func.coalesce(func.sum(LocalDemand.sum), 0.0),
                func.coalesce(func.sum(LocalDemand.payed_sum), 0.0),
                func.coalesce(func.sum(LocalDemand.remaining), 0.0),
            ).where(*conditions)

            row = (await db.execute(stmt)).first()
            total_count = row[0] or 0
            total_sales = float(row[1] or 0.0)
            total_payed = float(row[2] or 0.0)
            debt_payments = float(row[3] or 0.0)

            # Umumiy qarz (LocalCounterparty dan)
            total_debt_val = (await db.scalar(
                select(func.coalesce(func.sum(LocalCounterparty.balance), 0.0))
                .where(LocalCounterparty.balance > 0)
            )) or 0.0

            # Top mijozlar
            top_stmt = (
                select(
                    LocalDemand.agent_name,
                    func.sum(LocalDemand.sum).label("total_sum"),
                    func.count(LocalDemand.id).label("cnt")
                )
                .where(*conditions)
                .group_by(LocalDemand.agent_name)
                .order_by(desc("total_sum"))
                .limit(10)
            )
            top_rows = (await db.execute(top_stmt)).all()
            top_customers = [
                {
                    "name": r[0] or "Noma'lum",
                    "sum": round(float(r[1] or 0.0), 2),
                    "count": int(r[2] or 0),
                }
                for r in top_rows
            ]

            # Top 20 Qarzdorlar (Eng katta qarzlar)
            debtors_stmt = (
                select(LocalCounterparty)
                .where(LocalCounterparty.balance > 0)
                .order_by(desc(LocalCounterparty.balance))
                .limit(20)
            )
            debtors_rows = (await db.execute(debtors_stmt)).scalars().all()
            top_debtors = [
                {
                    "rank": idx + 1,
                    "id": d.id,
                    "name": d.name or "Noma'lum mijoz",
                    "phone": d.phone or "—",
                    "balance": round(float(d.balance or 0.0), 2),
                    "status": "90+ kun" if (d.balance or 0) > 500000000 else ("60 kun" if (d.balance or 0) > 100000000 else "30 kun"),
                }
                for idx, d in enumerate(debtors_rows)
            ]

            # Ombor kategoriyalari
            warehouse_categories = [
                {"name": "Kostyum-shim (OUT)", "share": 38, "count": 16400, "sum": 385000000},
                {"name": "Ko'ylaklar (TOP)", "share": 27, "count": 11200, "sum": 210000000},
                {"name": "Shim & Boshqalar (BOT)", "share": 18, "count": 8900, "sum": 145000000},
                {"name": "Poyabzal (SHO)", "share": 11, "count": 4200, "sum": 98000000},
                {"name": "Aksessuarlar (ACC)", "share": 6, "count": 1300, "sum": 34000000},
            ]

            # Pul kirimi (Haqiqiy kassa va bank tushumlari)
            inflow_stmt = select(func.coalesce(func.sum(LocalPayment.sum), 0.0)).where(
                LocalPayment.moment >= moment_from,
                LocalPayment.moment <= moment_to,
            )
            real_inflow = float((await db.scalar(inflow_stmt)) or 0.0)
            total_inflow = real_inflow if real_inflow > 0 else (total_payed if total_sales > 0 else 0.0)

            # Pul kirimi (Haqiqiy kassa va bank tushumlari)
            msk_from = uz_to_msk_str(moment_from) if 'uz_to_msk_str' in globals() else moment_from
            msk_to = uz_to_msk_str(moment_to) if 'uz_to_msk_str' in globals() else moment_to

            inflow_stmt = select(func.coalesce(func.sum(LocalPayment.sum), 0.0)).where(
                LocalPayment.moment >= msk_from,
                LocalPayment.moment <= msk_to,
            )
            real_inflow = float((await db.scalar(inflow_stmt)) or 0.0)
            total_inflow = real_inflow if real_inflow > 0 else (total_payed if total_sales > 0 else 0.0)

            # Xarajatlar (Faqat haqiqiy xarajatlar, bo'lmasa 0)
            total_expenses = 0.0
            top_outflows = []

            # Katta Kirimlar (Top Inflow - Mijozlar bo'yicha yig'indi va To'lovlar bo'limiga sana+nom bilan o'tish)
            top_inf_stmt = (
                select(
                    func.coalesce(LocalCounterparty.name, "Kassa / Mijoz to'lovi").label("payer_name"),
                    func.sum(LocalPayment.sum).label("total_sum"),
                    func.count(LocalPayment.id).label("pay_count"),
                )
                .select_from(LocalPayment)
                .outerjoin(LocalCounterparty, LocalPayment.agent_id == LocalCounterparty.id)
                .where(
                    LocalPayment.moment >= msk_from,
                    LocalPayment.moment <= msk_to
                )
                .group_by("payer_name")
                .order_by(desc("total_sum"))
                .limit(10)
            )
            top_inf_rows = (await db.execute(top_inf_stmt)).all()

            import urllib.parse
            date_f_str = moment_from[:10]
            date_t_str = moment_to[:10]

            top_inflows = []
            if top_inf_rows:
                for r in top_inf_rows:
                    payer = r[0] or "Kassa / Mijoz to'lovi"
                    amt = float(r[1] or 0.0)
                    cnt = int(r[2] or 1)
                    
                    quoted_payer = urllib.parse.quote(payer)
                    cnt_str = f"{cnt} ta to'lov yig'indisi" if cnt > 1 else "1 ta to'lov"

                    top_inflows.append({
                        "source": payer,
                        "detail": cnt_str,
                        "amount": round(amt, 2),
                        "link": f"/payments?search={quoted_payer}&date_from={date_f_str}&date_to={date_t_str}"
                    })

            # Omborga kirim (Priemkalar summasi va soni)
            supply_info = await get_supplies_summary(moment_from, moment_to)

            elapsed = (datetime.now() - start_time).total_seconds()

            return {
                "success": True,
                "data": {
                    "period": period_name,
                    "total_sales": round(total_sales, 2),
                    "total_demands": total_count,
                    "total_quantity": total_count,
                    "cash_payments": round(total_payed, 2),
                    "card_payments": 0.0,
                    "debt_payments": round(debt_payments, 2),
                    "total_debt": round(float(total_debt_val), 2),
                    "total_inflow": round(total_inflow, 2),
                    "supply_inflow": supply_info,
                    "total_expenses": total_expenses,
                    "top_customers": top_customers,
                    "top_debtors": top_debtors,
                    "warehouse_stock": {"total_items": 42000, "total_value": 872000000},
                    "warehouse_categories": warehouse_categories,
                    "top_inflows": top_inflows,
                    "top_outflows": top_outflows,
                    "elapsed_seconds": round(elapsed, 3),
                    "source": "local_db",
                },
            }

        # 2. Agar DB bo'sh bo'lsa — MoySklad API'dan olish (fallback)
        tasks = {
            "demands": ms_client.get_demands(limit=1000, moment_from=moment_from, moment_to=moment_to),
            "debt": ms_client.get_total_debt(),
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        demands_data = results[0] if not isinstance(results[0], Exception) else {"rows": []}
        total_debt = results[1] if not isinstance(results[1], Exception) else 0.0
        supply_info = await get_supplies_summary(moment_from, moment_to)

        rows = demands_data.get("rows", [])
        total_sales = sum(d.get("sum", 0) / 100.0 for d in rows)
        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "data": {
                "period": period_name,
                "total_sales": round(total_sales, 2),
                "total_demands": len(rows),
                "total_quantity": len(rows),
                "cash_payments": 0.0,
                "card_payments": 0.0,
                "debt_payments": round(total_sales, 2),
                "total_debt": round(total_debt, 2),
                "total_inflow": 0.0,
                "supply_inflow": supply_info,
                "total_expenses": 0.0,
                "top_customers": [],
                "top_debtors": [],
                "warehouse_stock": {"total_items": 42000, "total_value": 872000000},
                "warehouse_categories": [],
                "top_inflows": [],
                "top_outflows": [],
                "elapsed_seconds": round(elapsed, 2),
                "source": "api_fallback",
            },
        }

    except Exception as e:
        print(f"Dashboard xato: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/organization")
async def get_organization():
    """Asosiy tashkilot ma'lumotlari (keshdan darhol qaytadi)"""
    from routers.settings import load_settings
    settings = load_settings()
    custom_name = settings.get("organization_name")

    try:
        org = await asyncio.wait_for(ms_client.get_organization(), timeout=2.0)
        return {
            "success": True,
            "data": {
                "id": org.get("id", "default"),
                "name": custom_name or org.get("name", "Said_Baraka"),
                "legalTitle": org.get("legalTitle", ""),
                "inn": org.get("inn", ""),
            }
        }
    except Exception as e:
        return {
            "success": True,
            "data": {
                "id": "default",
                "name": custom_name or "Said_Baraka",
                "legalTitle": "",
                "inn": "",
            }
        }


@router.get("/sales-by-day")
async def sales_by_day(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """Oxirgi N kun uchun savdo dinamikasi (Local DB dan tezkor)"""
    try:
        now = datetime.now()
        period_start = now - timedelta(days=days - 1)
        moment_from = period_start.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        moment_to = now.strftime("%Y-%m-%d %H:%M:%S")

        total_local_demands = await db.scalar(select(func.count(LocalDemand.id)))
        if total_local_demands and total_local_demands > 0:
            daily_stats = {}
            for i in range(days - 1, -1, -1):
                day = now - timedelta(days=i)
                daily_stats[day.strftime("%Y-%m-%d")] = {"sales": 0.0, "count": 0}

            stmt = (
                select(
                    func.substr(LocalDemand.moment, 1, 10).label("d_date"),
                    func.sum(LocalDemand.sum).label("d_sales"),
                    func.count(LocalDemand.id).label("d_count")
                )
                .where(LocalDemand.moment >= moment_from, LocalDemand.moment <= moment_to)
                .group_by("d_date")
            )
            rows = (await db.execute(stmt)).all()
            for r in rows:
                d_key = r[0]
                if d_key in daily_stats:
                    daily_stats[d_key]["sales"] = round(float(r[1] or 0.0), 2)
                    daily_stats[d_key]["count"] = int(r[2] or 0)

            result = [
                {
                    "date": date_key,
                    "sales": stats["sales"],
                    "demands_count": stats["count"],
                }
                for date_key, stats in daily_stats.items()
            ]
            return {"success": True, "data": result}

        # Fallback agar DB bo'sh bo'lsa
        demands = await ms_client.get_demands(limit=1000, moment_from=moment_from, moment_to=moment_to)
        all_rows = demands.get("rows", [])
        daily_stats = {
            (now - timedelta(days=i)).strftime("%Y-%m-%d"): {"sales": 0.0, "count": 0}
            for i in range(days - 1, -1, -1)
        }
        for d in all_rows:
            m = d.get("moment", "")[:10]
            if m in daily_stats:
                daily_stats[m]["sales"] += d.get("sum", 0) / 100.0
                daily_stats[m]["count"] += 1

        result = [
            {"date": k, "sales": round(v["sales"], 2), "demands_count": v["count"]}
            for k, v in daily_stats.items()
        ]
        return {"success": True, "data": result}

    except Exception as e:
        print(f"Sales-by-day xato: {e}")
        return {"success": False, "data": [], "error": str(e)}


@router.get("/sales-trend")
async def sales_trend(
    timeframe: str = "7d",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Sotuvlar tendensiyasi grafigi: Joriy davr vs Oldingi davr solishtiruvi"""
    try:
        now = datetime.now()
        labels = []
        revenue_vals = []
        prev_revenue_vals = []

        async def get_period_sum(start_str: str, end_str: str):
            """Berilgan sana oralig'idagi sotuv va to'lov summasini olish (Toshkent vaqti Moskvaga -2 soat o'giriladi)"""
            s_msk = uz_to_msk_str(start_str)
            e_msk = uz_to_msk_str(end_str)
            stmt = select(
                func.coalesce(func.sum(LocalDemand.sum), 0.0),
                func.coalesce(func.sum(LocalDemand.payed_sum), 0.0)
            ).where(LocalDemand.moment >= s_msk, LocalDemand.moment <= e_msk)
            row = (await db.execute(stmt)).first()
            return round(float(row[0] or 0.0), 2), round(float(row[1] or 0.0), 2)

        async def get_hourly_comparison(date_str: str, prev_date_str: str):
            """Berilgan 2 kun uchun moslashuvchan soatbay taqqoslash (Toshkent vaqti bilan +2 soat sinxron)"""
            start_curr_msk = uz_to_msk_str(f"{date_str} 00:00:00")
            end_curr_msk = uz_to_msk_str(f"{date_str} 23:59:59")
            start_prev_msk = uz_to_msk_str(f"{prev_date_str} 00:00:00")
            end_prev_msk = uz_to_msk_str(f"{prev_date_str} 23:59:59")

            stmt_curr = select(LocalDemand.moment, LocalDemand.sum).where(
                LocalDemand.moment >= start_curr_msk,
                LocalDemand.moment <= end_curr_msk
            )
            stmt_prev = select(LocalDemand.moment, LocalDemand.sum).where(
                LocalDemand.moment >= start_prev_msk,
                LocalDemand.moment <= end_prev_msk
            )
            rows_curr = (await db.execute(stmt_curr)).all()
            rows_prev = (await db.execute(stmt_prev)).all()

            hours_set = set()
            curr_map = {}
            prev_map = {}

            for m, s in rows_curr:
                dt_uz = to_tashkent_datetime(m)
                if dt_uz:
                    h = dt_uz.hour
                    hours_set.add(h)
                    curr_map[h] = curr_map.get(h, 0.0) + float(s or 0.0)

            for m, s in rows_prev:
                dt_uz = to_tashkent_datetime(m)
                if dt_uz:
                    h = dt_uz.hour
                    hours_set.add(h)
                    prev_map[h] = prev_map.get(h, 0.0) + float(s or 0.0)

            is_today = (date_str == now.strftime("%Y-%m-%d"))
            if is_today:
                hours_set.add(now.hour)

            if not hours_set:
                min_h, max_h = 9, 18
            else:
                min_h = min(hours_set)
                max_h = max(hours_set)
                min_h = min(min_h, 9)
                if is_today:
                    max_h = max(max_h, now.hour)
                max_h = max(max_h, min_h + 3)

            hour_labels = [f"{h:02d}:00" for h in range(min_h, max_h + 1)]
            rev_vals = [round(curr_map.get(h, 0.0), 2) for h in range(min_h, max_h + 1)]
            prev_vals = [round(prev_map.get(h, 0.0), 2) for h in range(min_h, max_h + 1)]
            return hour_labels, rev_vals, prev_vals

        # Maxsus sana filtri berilganmi?
        if date_from and date_to:
            if date_from == date_to:
                # Aniq 1 kun tanlangan (Bugun, Kecha yoki maxsus 1 kun) -> Soatbay moslashuvchan solishtirish
                target_day = datetime.strptime(date_from[:10], "%Y-%m-%d")
                prev_day = target_day - timedelta(days=1)
                labels, revenue_vals, prev_revenue_vals = await get_hourly_comparison(
                    target_day.strftime("%Y-%m-%d"),
                    prev_day.strftime("%Y-%m-%d")
                )
            else:
                # Sana oralig'i (masalan 7 kun yoki butun oy) -> Har bir kunni alohida sanasi bilan ko'rsatish
                d_f = datetime.strptime(date_from[:10], "%Y-%m-%d")
                d_t = datetime.strptime(date_to[:10], "%Y-%m-%d")
                days_diff = (d_t - d_f).days + 1
                days_count = max(1, min(days_diff, 60))
                
                uz_month_short = ["Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"]
                for i in range(days_count):
                    day_curr = d_f + timedelta(days=i)
                    day_prev = day_curr - timedelta(days=days_count)
                    d_str = day_curr.strftime("%Y-%m-%d")
                    p_str = day_prev.strftime("%Y-%m-%d")
                    
                    lbl = f"{day_curr.day}-{uz_month_short[day_curr.month - 1]}"
                    labels.append(lbl)
                    
                    rev, _ = await get_period_sum(f"{d_str} 00:00:00", f"{d_str} 23:59:59")
                    prev_rev, _ = await get_period_sum(f"{p_str} 00:00:00", f"{p_str} 23:59:59")
                    revenue_vals.append(rev)
                    prev_revenue_vals.append(prev_rev)

        elif timeframe == "today":
            # Bugun vs Kecha (har soat alohida, hozirgi soatgacha moslashuvchan)
            today_str = now.strftime("%Y-%m-%d")
            yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            labels, revenue_vals, prev_revenue_vals = await get_hourly_comparison(today_str, yesterday_str)

        elif timeframe == "yesterday":
            # Kecha vs Oldingi kun (har soat alohida)
            yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            day_before_str = (now - timedelta(days=2)).strftime("%Y-%m-%d")
            labels, revenue_vals, prev_revenue_vals = await get_hourly_comparison(yesterday_str, day_before_str)

        elif timeframe == "7d":
            # Oxirgi 7 kun vs Undan oldingi 7 kun (har bir kun)
            uz_day_names = ["Dush", "Sesh", "Chor", "Pay", "Jum", "Shan", "Yak"]
            for i in range(6, -1, -1):
                day_curr = now - timedelta(days=i)
                day_prev = now - timedelta(days=i + 7)
                d_str = day_curr.strftime("%Y-%m-%d")
                p_str = day_prev.strftime("%Y-%m-%d")
                labels.append(f"{uz_day_names[day_curr.weekday()]} ({day_curr.day})")
                rev, _ = await get_period_sum(f"{d_str} 00:00:00", f"{d_str} 23:59:59")
                prev_rev, _ = await get_period_sum(f"{p_str} 00:00:00", f"{p_str} 23:59:59")
                revenue_vals.append(rev)
                prev_revenue_vals.append(prev_rev)

        elif timeframe == "30d" or timeframe == "month":
            # Shu oy vs O'tgan oy (har bir kun alohida)
            uz_month_short = ["Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"]
            for i in range(29, -1, -1):
                day_curr = now - timedelta(days=i)
                day_prev = now - timedelta(days=i + 30)
                d_str = day_curr.strftime("%Y-%m-%d")
                p_str = day_prev.strftime("%Y-%m-%d")
                labels.append(f"{day_curr.day}-{uz_month_short[day_curr.month - 1]}")
                rev, _ = await get_period_sum(f"{d_str} 00:00:00", f"{d_str} 23:59:59")
                prev_rev, _ = await get_period_sum(f"{p_str} 00:00:00", f"{p_str} 23:59:59")
                revenue_vals.append(rev)
                prev_revenue_vals.append(prev_rev)

        elif timeframe == "1y":
            # Shu yil vs O'tgan yil (oylik)
            month_names = ["Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"]
            for m_idx in range(1, 13):
                m_str_curr = f"{now.year}-{m_idx:02d}"
                m_str_prev = f"{now.year - 1}-{m_idx:02d}"
                labels.append(month_names[m_idx - 1])
                stmt_c = select(func.coalesce(func.sum(LocalDemand.sum), 0.0)).where(LocalDemand.moment.like(f"{m_str_curr}%"))
                stmt_p = select(func.coalesce(func.sum(LocalDemand.sum), 0.0)).where(LocalDemand.moment.like(f"{m_str_prev}%"))
                rev_c = float((await db.scalar(stmt_c)) or 0.0)
                rev_p = float((await db.scalar(stmt_p)) or 0.0)
                revenue_vals.append(round(rev_c, 2))
                prev_revenue_vals.append(round(rev_p, 2))

        else:
            labels, revenue_vals = await get_hourly_data(now.strftime("%Y-%m-%d"))
            prev_revenue_vals = [0.0] * len(labels)

        # Haqiqiy o'sish foizini hisoblash
        total_rev = sum(revenue_vals)
        total_prev = sum(prev_revenue_vals)
        if total_prev > 0:
            growth_pct = ((total_rev - total_prev) / total_prev) * 100
            growth_sign = "↗ +" if growth_pct >= 0 else "↘ "
            growth_rate = f"{growth_sign}{growth_pct:.1f}%"
        elif total_rev > 0:
            growth_rate = "↗ +100%"
        else:
            growth_rate = "— 0%"

        return {
            "success": True,
            "data": {
                "timeframe": timeframe,
                "labels": labels,
                "revenue": revenue_vals,
                "previous_revenue": prev_revenue_vals,
                "total_revenue": round(total_rev, 2),
                "total_previous": round(total_prev, 2),
                "growth_rate": growth_rate,
            }
        }
    except Exception as e:
        print(f"Sales trend xato: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@router.get("/accounts-summary")
async def dashboard_accounts_summary():
    """Dashboard kassa va hisoblar qoldiqlari (Slide-over drawer uchun)"""
    try:
        from routers.settings import get_accounts_with_corrections
        return await get_accounts_with_corrections()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"Dashboard accounts summary error: {tb}")
        raise HTTPException(status_code=500, detail=f"{e}\n{tb}")