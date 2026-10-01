from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import httpx
from moysklad_client import ms_client

router = APIRouter()

class UpdateRateRequest(BaseModel):
    rate: float

CBU_API_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"

async def fetch_cbu_usd_rate() -> Optional[Dict]:
    """O'zbekiston Markaziy Banki (CBU) rasmiy dollar kursini olish"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(CBU_API_URL)
            if resp.status_code == 200:
                rates = resp.json()
                for r in rates:
                    if r.get("Ccy") == "USD":
                        return {
                            "rate": float(r.get("Rate", 0)),
                            "diff": r.get("Diff", ""),
                            "date": r.get("Date", ""),
                        }
    except Exception as e:
        print(f"[CBU rate fetch error] {e}")
    return None


@router.get("")
@router.get("/")
async def get_currencies():
    """MoySklad valyutalari va joriy Dollar kursini olish"""
    try:
        raw_currencies = await ms_client.get_currencies()
        
        usd_currency = None
        uzs_currency = None
        currencies_list = []

        for c in raw_currencies:
            iso = c.get("isoCode", "")
            c_info = {
                "id": c.get("id"),
                "name": c.get("name") or iso,
                "fullName": c.get("fullName") or c.get("name"),
                "isoCode": iso,
                "rate": float(c.get("rate", 1.0)),
                "isDefault": c.get("default", False),
            }
            currencies_list.append(c_info)

            if iso == "USD":
                usd_currency = c_info
            elif iso == "UZS" or c.get("default", False):
                uzs_currency = c_info

        # Markaziy Bank kursini ham olish
        cbu_info = await fetch_cbu_usd_rate()

        from routers.settings import load_settings, save_settings
        app_settings = load_settings()
        ref_rate = app_settings.get("reference_usd_rate")
        if ref_rate and float(ref_rate) > 0:
            active_rate = float(ref_rate)
        else:
            active_rate = usd_currency.get("rate", 12800.0) if usd_currency else 12800.0

        return {
            "success": True,
            "data": {
                "usd_rate": active_rate,
                "usd_currency": usd_currency,
                "uzs_currency": uzs_currency,
                "currencies": currencies_list,
                "cbu": cbu_info,
            }
        }
    except Exception as e:
        print(f"[Get currencies error] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/usd-rate")
async def update_usd_rate(req: UpdateRateRequest):
    """MoySklad'dagi va Sozlamalardagi USD kursini bir vaqtda yangilash"""
    if req.rate <= 0:
        raise HTTPException(status_code=400, detail="Kurs 0 dan katta bo'lishi kerak")

    try:
        from routers.settings import load_settings, save_settings
        app_settings = load_settings()
        app_settings["reference_usd_rate"] = req.rate
        for m in app_settings.get("payment_methods", []):
            if m.get("id") == "usd":
                m["default_rate"] = req.rate
        save_settings(app_settings)

        raw_currencies = await ms_client.get_currencies()
        usd_id = None
        for c in raw_currencies:
            if c.get("isoCode") == "USD":
                usd_id = c.get("id")
                break

        updated = None
        if usd_id:
            try:
                updated = await ms_client.update_currency_rate(usd_id, req.rate)
            except Exception as mse:
                print(f"[MS update rate warning]: {mse}")

        return {
            "success": True,
            "message": f"Dollar kursi muvaffaqiyatli yangilandi: 1 USD = {req.rate:,.0f} so'm",
            "data": {
                "usd_id": usd_id,
                "new_rate": req.rate,
                "currency": updated,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Update USD rate error] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-cbu")
async def sync_with_cbu():
    """Markaziy Bank rasmiy dollar kursini olib, MoySklad'ga o'rnatish"""
    cbu_info = await fetch_cbu_usd_rate()
    if not cbu_info or not cbu_info.get("rate"):
        raise HTTPException(status_code=502, detail="Markaziy Bank kursini olib bo'lmadi")

    cbu_rate = cbu_info["rate"]

    try:
        raw_currencies = await ms_client.get_currencies()
        usd_id = None
        for c in raw_currencies:
            if c.get("isoCode") == "USD":
                usd_id = c.get("id")
                break

        if not usd_id:
            raise HTTPException(status_code=404, detail="MoySklad'da USD valyutasi topilmadi")

        updated = await ms_client.update_currency_rate(usd_id, cbu_rate)
        return {
            "success": True,
            "message": f"MoySklad kursi Markaziy Bank bilan sinxronlandi: 1 USD = {cbu_rate:,.2f} so'm ({cbu_info.get('date')})",
            "data": {
                "usd_id": usd_id,
                "new_rate": cbu_rate,
                "cbu_diff": cbu_info.get("diff"),
                "date": cbu_info.get("date"),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Sync CBU error] {e}")
        raise HTTPException(status_code=500, detail=str(e))
