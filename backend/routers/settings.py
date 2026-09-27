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
    global _ACCOUNTS_CACHE, _ACCOUNTS_CACHE_TIME
    _ACCOUNTS_CACHE = None
    _ACCOUNTS_CACHE_TIME = 0.0


# ===== HISOBLAR BALANSI VA KORREKTIROVKA API =====
@router.get("/accounts")
async def get_accounts_with_corrections():
    """Barcha hisoblarning asl valyutasidagi qoldiqlari va korrektirovkalari (0.01s tezkor kesh)"""
    global _ACCOUNTS_CACHE, _ACCOUNTS_CACHE_TIME
    now = time.time()
    if _ACCOUNTS_CACHE is not None and (now - _ACCOUNTS_CACHE_TIME) < _ACCOUNTS_CACHE_TTL:
        return _ACCOUNTS_CACHE

    settings = load_settings()
    corrections = settings.get("corrections", {})
    ref_rate = settings.get("reference_usd_rate", 12800.0)

    # Kassa operatsiyalari orqali xom balansni olish (Tezkor 1.5s timeout bilan)
    from routers.payments import get_cashflow
    raw_balances = []
    try:
        cf_resp = await asyncio.wait_for(get_cashflow(), timeout=2.5)
        summary = cf_resp.get("data", {}).get("summary", {})
    except Exception as e:
        raw_balances = []

    # Tashkilot hisoblarini olish va raw_balances ga qo'shish
    try:
        org = await ms_client.get_organization()
        if org.get("id") and org.get("id") != "default":
            org_accs = await asyncio.wait_for(ms_client.get_organization_accounts(org.get("id")), timeout=2.0)
            existing_ids = {a.get("id") for a in raw_balances}
            for oa in org_accs:
                oa_id = oa.get("id")
                if oa_id and oa_id not in existing_ids:
                    oa_name = oa.get("name") or oa.get("accountnumber") or "Bank hisobi"
                    is_dol = "dollar" in (oa_name + " " + oa.get("accountnumber", "")).lower()
                    raw_balances.append({
                        "id": oa_id,
                        "name": f"{'💵' if is_dol else '🏦'} {oa_name}",
                        "raw_name": oa_name,
                        "accountnumber": oa.get("accountnumber"),
                        "type": "dollar" if is_dol else "bank",
                        "currency": "USD" if is_dol else "UZS",
                        "is_dollar": is_dol,
                        "balance": 0.0,
                        "usd_balance": 0.0
                    })
    except Exception as e:
        pass

    if not raw_balances:
        raw_balances = [
            {"id": "cash_default", "name": "💵 Asosiy Naqd Kassa (UZS)", "currency": "UZS", "current_balance": 0.0, "is_dollar": False},
            {"id": "card_default", "name": "💳 Bank Hisobi (UZS)", "currency": "UZS", "current_balance": 0.0, "is_dollar": False},
            {"id": "usd_default", "name": "💵 Dollar Kassa (USD)", "currency": "USD", "current_balance": 0.0, "is_dollar": True},
        ]

    adjusted_accounts = []
    total_uzs_balance = 0.0
    total_usd_balance = 0.0

    for acc in raw_balances:
        a_id = acc.get("id")
        is_dollar = acc.get("is_dollar", False)
        currency = "USD" if is_dollar else "UZS"

        # Korrektirovka bormi?
        corr = corrections.get(a_id)
        if corr and "adjusted_balance" in corr:
            final_balance = float(corr["adjusted_balance"])
            has_correction = True
            corr_info = corr
        else:
            # Agar Dollar hisob bo'lsa, xom summasini o'ziga xos hisoblash
            # MoySklad operatsiyalarida UZS bo'lsa, usd_balance olamiz
            if is_dollar:
                final_balance = acc.get("usd_balance", 0.0)
            else:
                final_balance = acc.get("balance", 0.0)
            has_correction = False
            corr_info = None

        if is_dollar:
            total_usd_balance += final_balance
        else:
            total_uzs_balance += final_balance

        adjusted_accounts.append({
            "id": a_id,
            "name": acc.get("name"),
            "raw_name": acc.get("raw_name"),
            "accountnumber": acc.get("accountnumber"),
            "type": acc.get("type"),
            "currency": currency,
            "is_dollar": is_dollar,
            "current_balance": final_balance,
            "raw_balance": acc.get("usd_balance" if is_dollar else "balance", 0.0),
            "has_correction": has_correction,
            "correction": corr_info,
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
    _ACCOUNTS_CACHE = res
    _ACCOUNTS_CACHE_TIME = time.time()
    return res


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
    settings["reference_usd_rate"] = rate
    save_settings(settings)
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
