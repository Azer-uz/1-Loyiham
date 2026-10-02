from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import json
import uuid
import asyncio
import time
from moysklad_client import ms_client

router = APIRouter()

SETTINGS_FILE = Path(__file__).parent.parent / "data" / "payment_settings.json"


def load_settings() -> Dict[str, Any]:
    """Sozlamalarni JSON fayldan o'qish"""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[Settings load error] {e}")

    return {
        "payment_methods": [
            {
                "id": "cash",
                "name": "Naqd pul",
                "icon": "💵",
                "currency": "UZS",
                "linked_account_ids": ["cash_default"],
                "is_active": true,
                "is_system": true,
                "description": "Asosiy naqd kassa orqali so'mda to'lov"
            },
            {
                "id": "card",
                "name": "Karta / Bank",
                "icon": "💳",
                "currency": "UZS",
                "linked_account_ids": [],
                "is_active": true,
                "is_system": true,
                "description": "Bank hisob raqamlari orqali to'lov"
            },
            {
                "id": "usd",
                "name": "Dollar (USD)",
                "icon": "💵",
                "currency": "USD",
                "linked_account_ids": [],
                "is_active": true,
                "is_system": true,
                "default_rate": 12800.0,
                "description": "Kelishilgan kurs bo'yicha dollar to'lovi"
            }
        ],
        "corrections": {},
        "reference_usd_rate": 12800.0
    }


def save_settings(data: Dict[str, Any]):
    """Sozlamalarni JSON faylga saqlash"""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class PaymentMethodCreateRequest(BaseModel):
    name: str
    icon: Optional[str] = "💵"
    currency: str = "UZS"  # 'UZS' yoki 'USD'
    linked_account_ids: List[str] = []
    is_active: bool = True
    default_rate: Optional[float] = 12800.0
    description: Optional[str] = ""


class PaymentMethodUpdateRequest(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    currency: Optional[str] = None
    linked_account_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None
    default_rate: Optional[float] = None
    description: Optional[str] = None


class BalanceAdjustmentRequest(BaseModel):
    account_id: str
    new_balance: Optional[float] = None
    corrected_balance: Optional[float] = None
    reason: Optional[str] = "Korrektirovka (Kassa sanash)"


# ===== TO'LOV TURLARI API =====
@router.get("/payment-methods")
async def get_payment_methods():
    """Barcha to'lov turlarini va ularga bog'langan hisob raqamlarni olish"""
    settings = load_settings()
    methods = settings.get("payment_methods", [])

    # Tashkilot hisoblarini olish (nomlarni chiroyli ko'rsatish uchun)
    org_accounts = []
    try:
        org = await ms_client.get_organization()
        if org.get("id") and org.get("id") != "default":
            org_accounts = await asyncio.wait_for(ms_client.get_organization_accounts(org.get("id")), timeout=2.0)
    except Exception as e:
        pass

    acc_map = {
        "cash_default": {
            "id": "cash_default",
            "name": "💵 Asosiy Naqd Kassa (UZS)",
            "currency": "UZS",
            "type": "cash"
        }
    }
    if org_accounts:
        for a in org_accounts:
            a_id = a.get("id")
            a_name = a.get("name") or a.get("accountnumber") or "Bank hisobi"
            is_dol = "dollar" in (a_name + " " + a.get("accountnumber", "")).lower()
            acc_map[a_id] = {
                "id": a_id,
                "name": f"{'💵' if is_dol else '🏦'} {a_name}",
                "currency": "USD" if is_dol else "UZS",
                "type": "dollar" if is_dol else "bank"
            }
    else:
        lka = settings.get("last_known_accounts", {}).get("accounts", [])
        for a in lka:
            a_id = a.get("id")
            if not a_id or a_id == "cash_default":
                continue
            is_dol = bool(a.get("is_dollar") or a.get("currency") == "USD" or a.get("type") == "dollar")
            acc_map[a_id] = {
                "id": a_id,
                "name": a.get("name") if str(a.get("name", "")).startswith(("💵", "🏦", "💳", "💲")) else f"{'💵' if is_dol else '🏦'} {a.get('name')}",
                "currency": "USD" if is_dol else "UZS",
                "type": "dollar" if is_dol else "bank"
            }

    # Har bir to'lov turiga hisoblar tafsilotini biriktirish
    enriched = []
    for m in methods:
        m_copy = dict(m)
        linked_details = [acc_map[acc_id] for acc_id in m.get("linked_account_ids", []) if acc_id in acc_map]
        m_copy["linked_accounts_detail"] = linked_details
        enriched.append(m_copy)

    return {
        "success": True,
        "data": {
            "methods": enriched,
            "available_accounts": list(acc_map.values()),
            "reference_usd_rate": settings.get("reference_usd_rate", 12800.0)
        }
    }


@router.post("/payment-methods")
async def create_payment_method(req: PaymentMethodCreateRequest):
    """Yangi to'lov turi yaratish"""
    name_clean = req.name.strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="To'lov turi nomi kiritilishi shart")

    settings = load_settings()
    methods = settings.get("payment_methods", [])

    new_id = f"custom_{uuid.uuid4().hex[:8]}"
    new_method = {
        "id": new_id,
        "name": name_clean,
        "icon": req.icon or "💵",
        "currency": req.currency.upper(),
        "linked_account_ids": req.linked_account_ids,
        "is_active": req.is_active,
        "is_system": False,
        "default_rate": req.default_rate or 12800.0,
        "description": req.description or ""
    }

    methods.append(new_method)
    settings["payment_methods"] = methods
    save_settings(settings)

    return {
        "success": True,
        "message": f"'{name_clean}' to'lov turi muvaffaqiyatli qo'shildi",
        "data": new_method
    }


@router.put("/payment-methods/{method_id}")
async def update_payment_method(method_id: str, req: PaymentMethodUpdateRequest):
    """Mavjud to'lov turini tahrirlash"""
    settings = load_settings()
    methods = settings.get("payment_methods", [])

    target = None
    for m in methods:
        if m.get("id") == method_id:
            target = m
            break

    if not target:
        raise HTTPException(status_code=404, detail="To'lov turi topilmadi")

    if req.name is not None:
        target["name"] = req.name.strip()
    if req.icon is not None:
        target["icon"] = req.icon
    if req.currency is not None:
        target["currency"] = req.currency.upper()
    if req.linked_account_ids is not None:
        target["linked_account_ids"] = req.linked_account_ids
    if req.is_active is not None:
        target["is_active"] = req.is_active
    if req.default_rate is not None:
        target["default_rate"] = req.default_rate
    if req.description is not None:
        target["description"] = req.description

    save_settings(settings)
    return {"success": True, "message": "To'lov turi muvaffaqiyatli yangilandi", "data": target}


@router.post("/payment-methods/{method_id}/toggle")
async def toggle_payment_method(method_id: str):
    """To'lov turini faollashtirish / nofaol qilish (Toggle)"""
    settings = load_settings()
    methods = settings.get("payment_methods", [])

    target = None
    for m in methods:
        if m.get("id") == method_id:
            target = m
            break

    if not target:
        raise HTTPException(status_code=404, detail="To'lov turi topilmadi")

    target["is_active"] = not target.get("is_active", True)
    save_settings(settings)

    status_str = "faollashtirildi" if target["is_active"] else "o'chirildi"
    return {
        "success": True,
        "message": f"'{target['name']}' to'lov turi {status_str}",
        "is_active": target["is_active"]
    }


@router.delete("/payment-methods/{method_id}")
async def delete_payment_method(method_id: str):
    """To'lov turini o'chirish (faqat maxsus turlar uchun)"""
    settings = load_settings()
    methods = settings.get("payment_methods", [])

    target_idx = None
    for i, m in enumerate(methods):
        if m.get("id") == method_id:
            if m.get("is_system"):
                raise HTTPException(status_code=400, detail="Tizimli asosiy to'lov turini o'chirib bo'lmaydi (o'rniga nofaol qilishingiz mumkin)")
            target_idx = i
            break

    if target_idx is None:
        raise HTTPException(status_code=404, detail="To'lov turi topilmadi")

    deleted = methods.pop(target_idx)
    save_settings(settings)
    return {"success": True, "message": f"'{deleted['name']}' to'lov turi o'chirildi"}


_ACCOUNTS_CACHE = None
_ACCOUNTS_CACHE_TIME = 0.0
_ACCOUNTS_CACHE_TTL = 120.0  # 2 daqiqa kesh


def invalidate_accounts_cache():
    global _ACCOUNTS_CACHE_TIME
    # Keshni eskirgan deb belgilaymiz, lekin MoySklad xato berganda fallback sifatida saqlab qolamiz
    _ACCOUNTS_CACHE_TIME = 0.0


def set_accounts_cache(cache_obj: dict):
    global _ACCOUNTS_CACHE, _ACCOUNTS_CACHE_TIME
    _ACCOUNTS_CACHE = cache_obj
    _ACCOUNTS_CACHE_TIME = time.time()
    try:
        settings = load_settings()
        if isinstance(cache_obj, dict) and "data" in cache_obj:
            settings["last_known_accounts"] = cache_obj["data"]
            save_settings(settings)
    except Exception:
        pass


# ===== HISOBLAR BALANSI VA KORREKTIROVKA API =====
@router.get("/accounts")
async def get_accounts_with_corrections():
    """Barcha hisoblarning asl valyutasidagi qoldiqlari va korrektirovkalari — MoySklad /report/money/byaccount orqali 100% to'g'ri oladi"""
    global _ACCOUNTS_CACHE, _ACCOUNTS_CACHE_TIME
    now = time.time()
    if _ACCOUNTS_CACHE is not None and (now - _ACCOUNTS_CACHE_TIME) < _ACCOUNTS_CACHE_TTL:
        return _ACCOUNTS_CACHE

    settings = load_settings()
    usd_method = next((m for m in settings.get("payment_methods", []) if m.get("id") == "usd"), None)
    default_rate = usd_method.get("default_rate") if usd_method else None
    ref_rate = float(default_rate or settings.get("reference_usd_rate") or 11800.0)
    corrections = settings.get("corrections", {})

    from moysklad_client import ms_client

    adjusted_accounts = []
    total_uzs_balance = 0.0
    total_usd_balance = 0.0

    try:
        report_data = await ms_client._request("GET", "/report/money/byaccount")
        rows = report_data.get("rows", []) if isinstance(report_data, dict) else []

        for row in rows:
            acc = row.get("account")
            # MoySklad da balans tiyinda/kopiykada keladi -> / 100.0
            raw_bal = float(row.get("balance", 0.0)) / 100.0

            if not acc:
                # Asosiy Tashkilot Naqd Kassasi
                acc_id = "cash_default"
                acc_name = "💵 Asosiy Naqd Kassa"
                raw_name = "Касса организации"
                is_dol = False
                currency = "UZS"
                acc_type = "cash"
            else:
                href = acc.get("meta", {}).get("href", "")
                acc_id = href.split("/")[-1] if href else "bank_account"
                raw_name = acc.get("name", "Bank hisobi")
                is_dol = bool("dollar" in raw_name.lower() or "usd" in raw_name.lower())
                currency = "USD" if is_dol else "UZS"
                acc_type = "dollar" if is_dol else "bank"
                acc_name = f"{'💲' if is_dol else '💳'} {raw_name}"

            # Korrektirovka tekshirish
            corr = corrections.get(acc_id)
            if corr and "adjusted_balance" in corr:
                final_bal = float(corr["adjusted_balance"])
                has_corr = True
            else:
                final_bal = raw_bal
                has_corr = False

            if is_dol:
                total_usd_balance += final_bal
            else:
                total_uzs_balance += final_bal

            adjusted_accounts.append({
                "id": acc_id,
                "name": acc_name,
                "raw_name": raw_name,
                "accountnumber": acc.get("accountnumber", "") if acc else "KASSA-UZS",
                "type": acc_type,
                "currency": currency,
                "is_dollar": is_dol,
                "current_balance": final_bal,
                "raw_balance": raw_bal,
                "has_correction": has_corr,
                "correction": corr,
            })

        consolidated_uzs = total_uzs_balance + (total_usd_balance * ref_rate)

        res = {
            "success": True,
            "data": {
                "accounts": adjusted_accounts,
                "total_uzs_balance": total_uzs_balance,
                "total_usd_balance": total_usd_balance,
                "reference_rate": ref_rate,
                "consolidated_uzs_equivalent": consolidated_uzs,
            }
        }
        if adjusted_accounts:
            _ACCOUNTS_CACHE = res
            _ACCOUNTS_CACHE_TIME = time.time()
            try:
                settings["last_known_accounts"] = res["data"]
                save_settings(settings)
            except Exception:
                pass
        return res

    except Exception as e:
        print(f"[Accounts /report/money/byaccount error] {e}")
        # Agar oldingi to'g'ri xotiradagi kesh bo'lsa, uni asrab qolamiz va qaytaramiz
        if _ACCOUNTS_CACHE is not None:
            return _ACCOUNTS_CACHE

        if settings.get("last_known_accounts"):
            return {
                "success": True,
                "data": settings["last_known_accounts"]
            }

        adjusted_accounts = [
            {"id": "cash_default", "name": "💵 Asosiy Naqd Kassa", "currency": "UZS", "current_balance": 0.0, "is_dollar": False, "has_correction": False},
        ]
        return {
            "success": True,
            "data": {
                "accounts": adjusted_accounts,
                "total_uzs_balance": 0.0,
                "total_usd_balance": 0.0,
                "reference_rate": ref_rate,
                "consolidated_uzs_equivalent": 0.0,
            }
        }


@router.post("/accounts/adjust-balance")
async def adjust_account_balance(req: BalanceAdjustmentRequest):
    """Hisob qoldig'ini to'g'irlash (Korrektirovka kiritish)"""
    invalidate_accounts_cache()
    settings = load_settings()
    corrections = settings.get("corrections", {})

    target_val = req.new_balance if req.new_balance is not None else (req.corrected_balance or 0.0)

    corrections[req.account_id] = {
        "adjusted_balance": float(target_val),
        "reason": req.reason or "Kassa sanash",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    settings["corrections"] = corrections
    save_settings(settings)

    return {
        "success": True,
        "message": f"Hisob qoldig'i {target_val:,.2f} ga muvaffaqiyatli korrektirovka qilindi",
        "data": corrections[req.account_id]
    }


# ===== CHEK SOZLAMALARI API (Serverda saqlash — barcha qurilmalarda bir xil) =====
@router.get("/receipt")
async def get_receipt_settings():
    """Chek shablon sozlamalarini olish (serverda saqlanadi)"""
    settings = load_settings()
    receipt = settings.get("receipt_settings", {
        "storeName": "MODERN MEN'S WEAR",
        "slogan": "Erkaklar kiyimlarining ulgurji savdosi",
        "phones": "+998 90 123-45-67",
        "address": "Toshkent sh., Abu Saxiy bozori",
        "footerNote": "Xaridingiz uchun rahmat! Sotilgan tovarlar 3 kun ichida chek bilan almashtiriladi.",
        "fontSize": "large"
    })
    return {"success": True, "data": receipt}


@router.post("/receipt")
async def save_receipt_settings(req: Dict[str, Any]):
    """Chek shablon sozlamalarini saqlash (serverda doimiy)"""
    settings = load_settings()
    settings["receipt_settings"] = {
        "storeName": (req.get("storeName") or "").strip() or "MODERN MEN'S WEAR",
        "slogan": (req.get("slogan") or "").strip(),
        "phones": (req.get("phones") or "").strip(),
        "address": (req.get("address") or "").strip(),
        "footerNote": (req.get("footerNote") or "").strip(),
        "fontSize": req.get("fontSize") or "large",
    }
    save_settings(settings)
    return {"success": True, "message": "Chek sozlamalari muvaffaqiyatli saqlandi!"}


@router.get("/reference-rate")
async def get_reference_rate():
    """Umumiy hisob dollar kursini olish"""
    settings = load_settings()
    rate = settings.get("reference_usd_rate", 12850.0)
    return {"success": True, "rate": rate, "data": {"rate": rate}}


@router.post("/reference-rate")
async def update_reference_rate(req: Dict[str, float]):
    """Umumiy konsolidatsiyalash uchun standart hisob dollar kursini saqlash"""
    rate = req.get("rate")
    if not rate or rate <= 0:
        raise HTTPException(status_code=400, detail="Noto'g'ri kurs qiymati")

    settings = load_settings()
    settings["reference_usd_rate"] = float(rate)
    for m in settings.get("payment_methods", []):
        if m.get("id") == "usd":
            m["default_rate"] = float(rate)
    save_settings(settings)
    invalidate_accounts_cache()
    try:
        from routers.payments import invalidate_cashflow_cache
        invalidate_cashflow_cache()
    except Exception:
        pass
    return {"success": True, "message": f"Hisob kursi yangilandi: 1 USD = {rate:,.0f} so'm", "rate": rate, "data": {"rate": rate}}


@router.get("/organization")
async def get_organization_setting():
    """Bizning tashkilot nomini olish"""
    settings = load_settings()
    name = settings.get("organization_name", "Said_Baraka")
    return {"success": True, "name": name, "organization_name": name, "data": {"name": name, "organization_name": name}}


@router.post("/organization")
async def update_organization_setting(req: Dict[str, str]):
    """Bizning tashkilot nomini saqlash"""
    name = (req.get("organization_name") or req.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tashkilot nomi bo'sh bo'lmasligi kerak")

    settings = load_settings()
    settings["organization_name"] = name
    save_settings(settings)
    return {"success": True, "message": f"Tashkilot nomi saqlandi: {name}", "name": name, "organization_name": name, "data": {"name": name, "organization_name": name}}
