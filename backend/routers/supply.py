"""
supply.py — Tovar Kirimi (Приемка) Backend Router
MoySkladga tovarlar va Priemka hujjatini to'g'ridan-to'g'ri API orqali yaratish.
"""

import re
import time
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from moysklad_client import ms_client

router = APIRouter()

# ─────────────────────────────────────────────
#  Codes reference data (from Excel Ruyxat sheet)
# ─────────────────────────────────────────────
SUPPLY_CODES_FILE = Path(__file__).parent.parent / "data" / "supply_codes.json"

def load_supply_codes() -> Dict:
    try:
        with open(SUPPLY_CODES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"season_codes": {}, "group_codes": {}, "colors": [], "color_hex_map": {}}

# ─────────────────────────────────────────────
#  Attribute metadata cache
# ─────────────────────────────────────────────
_attr_meta_cache: Dict = {}
_attr_meta_ts: float = 0.0
ATTR_CACHE_TTL = 600  # 10 min

async def get_attribute_metadata() -> Dict[str, Dict]:
    """Get product attribute metadata keyed by name."""
    global _attr_meta_cache, _attr_meta_ts
    now = time.time()
    if _attr_meta_cache and (now - _attr_meta_ts) < ATTR_CACHE_TTL:
        return _attr_meta_cache

    resp = await ms_client._request("GET", "/entity/product/metadata/attributes")
    attrs: Dict[str, Dict] = {}
    for attr in resp.get("rows", []):
        name = attr.get("name", "")
        attr_id = attr.get("id", "")
        attr_type = attr.get("type", "")

        # Extract the customEntityId from customEntityMeta href
        custom_entity_meta = attr.get("customEntityMeta") or {}
        metadata_href = custom_entity_meta.get("href", "")
        entity_id = None
        if metadata_href:
            m = re.search(r"customEntities/([a-f0-9-]+)", metadata_href)
            if m:
                entity_id = m.group(1)

        attrs[name] = {
            "id": attr_id,
            "type": attr_type,
            "customEntityId": entity_id,
            "metadataHref": metadata_href,
            # Build the attribute meta object needed in product creation
            "attr_meta": {
                "href": f"https://api.moysklad.ru/api/remap/1.2/entity/product/metadata/attributes/{attr_id}",
                "type": "attributemetadata",
                "mediaType": "application/json",
            },
        }

    _attr_meta_cache = attrs
    _attr_meta_ts = now
    return attrs


# ─────────────────────────────────────────────
#  Custom entity values cache
# ─────────────────────────────────────────────
_entity_values_cache: Dict[str, Dict] = {}
ENTITY_CACHE_TTL = 180

async def get_customentity_values(entity_id: str) -> List[Dict]:
    """List all values of a custom entity type."""
    now = time.time()
    cached = _entity_values_cache.get(entity_id, {})
    if cached.get("data") is not None and (now - cached.get("ts", 0)) < ENTITY_CACHE_TTL:
        return cached["data"]

    resp = await ms_client._request(
        "GET", f"/entity/customentity/{entity_id}", params={"limit": 1000}
    )
    values = resp.get("rows", [])
    _entity_values_cache[entity_id] = {"data": values, "ts": now}
    return values


async def get_or_create_customentity_value(entity_id: str, name: str) -> Optional[Dict]:
    """Find or create a custom entity value; return its meta object."""
    name_clean = name.strip()
    if not name_clean:
        return None

    values = await get_customentity_values(entity_id)
    # Case-insensitive match
    for v in values:
        if v.get("name", "").strip().lower() == name_clean.lower():
            return v.get("meta")

    # Not found — create new
    try:
        result = await ms_client._request(
            "POST", f"/entity/customentity/{entity_id}", json_data={"name": name_clean}
        )
        # Invalidate cache
        _entity_values_cache.pop(entity_id, None)
        return result.get("meta")
    except Exception as e:
        print(f"[supply] Cannot create customentity value '{name_clean}' in {entity_id}: {e}")
        return None


# ─────────────────────────────────────────────
#  Currency & price type helpers
# ─────────────────────────────────────────────
_uzs_currency_meta: Optional[Dict] = None
_price_type_meta: Optional[Dict] = None


async def get_uzs_currency_meta() -> Optional[Dict]:
    global _uzs_currency_meta
    if _uzs_currency_meta:
        return _uzs_currency_meta

    currencies = await ms_client.get_currencies()
    for c in currencies:
        iso = c.get("isoCode", "").upper()
        name_lc = c.get("name", "").lower()
        if iso == "UZS" or "сум" in name_lc or "uzs" in name_lc:
            _uzs_currency_meta = c.get("meta")
            return _uzs_currency_meta
    # Fallback: use first currency (likely base currency)
    if currencies:
        _uzs_currency_meta = currencies[0].get("meta")
    return _uzs_currency_meta


async def get_price_type_meta() -> Optional[Dict]:
    global _price_type_meta
    if _price_type_meta:
        return _price_type_meta
    try:
        resp = await ms_client._request(
            "GET", "/context/companysettings/pricetype", params={"limit": 10}
        )
        rows = resp.get("rows", [])
        for pt in rows:
            if "продаж" in pt.get("name", "").lower():
                _price_type_meta = pt.get("meta")
                return _price_type_meta
        if rows:
            _price_type_meta = rows[0].get("meta")
    except Exception as e:
        print(f"[supply] Price type fetch error: {e}")
    return _price_type_meta


# ─────────────────────────────────────────────
#  Last articul number helper
# ─────────────────────────────────────────────
async def find_last_articul_number() -> int:
    """Scan MoySklad products to find the maximum 5-digit counter in article codes."""
    try:
        # Get all products (sorted by updated desc to quickly find recent ones)
        resp = await ms_client._request(
            "GET", "/entity/product",
            params={"limit": 1000, "fields": "article", "order": "updated,desc"}
        )
        max_num = 0
        for prod in resp.get("rows", []):
            article = prod.get("article") or ""
            # Pattern: look for 5 consecutive digits in the article code
            # Examples: A26TOP00405BRG → 00405 → 405
            matches = re.findall(r"\d{5}", article)
            for m in matches:
                num = int(m)
                if num > max_num:
                    max_num = num
        return max_num
    except Exception as e:
        print(f"[supply] find_last_articul_number error: {e}")
        return 0


# ─────────────────────────────────────────────
#  GET /references  — All form data in one call
# ─────────────────────────────────────────────
@router.get("/references")
async def get_supply_references():
    """
    Returns all reference data needed for the supply form:
    - productFolders, attribute values (each customentity type), organization, suppliers
    - season_codes, group_codes, colors with hex values and codes
    - last articul number
    """
    codes = load_supply_codes()

    try:
        # Fetch data concurrently
        folders_task = ms_client._request("GET", "/entity/productfolder", params={"limit": 100})
        attr_task = get_attribute_metadata()
        orgs_task = ms_client._request("GET", "/entity/organization", params={"limit": 5})
        suppliers_task = ms_client._request(
            "GET", "/entity/counterparty",
            params={"limit": 200, "filter": "supplier=true"}
        )
        last_num_task = find_last_articul_number()

        folders_resp, attr_meta, orgs_resp, suppliers_resp, last_num = await asyncio.gather(
            folders_task, attr_task, orgs_task, suppliers_task, last_num_task,
            return_exceptions=True
        )

        # Product folders
        folders = []
        if not isinstance(folders_resp, Exception):
            for pf in folders_resp.get("rows", []):
                folders.append({
                    "id": pf.get("id"),
                    "name": pf.get("name"),
                    "path": pf.get("pathName", ""),
                    "meta": pf.get("meta"),
                })

        # Organization
        organization = None
        if not isinstance(orgs_resp, Exception) and orgs_resp.get("rows"):
            o = orgs_resp["rows"][0]
            organization = {"id": o.get("id"), "name": o.get("name"), "meta": o.get("meta")}

        # Suppliers (kontragentlar – yetkazib beruvchilar)
        suppliers = []
        if not isinstance(suppliers_resp, Exception):
            for s in suppliers_resp.get("rows", []):
                suppliers.append({
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "meta": s.get("meta"),
                })

        # Last articul number
        last_articul = last_num if not isinstance(last_num, Exception) else 0

        # Load all custom entity values for each attribute
        entity_values: Dict[str, List] = {}
        if not isinstance(attr_meta, Exception):
            for attr_name, attr_info in attr_meta.items():
                entity_id = attr_info.get("customEntityId")
                if entity_id:
                    try:
                        values = await get_customentity_values(entity_id)
                        entity_values[attr_name] = [
                            {"id": v.get("id"), "name": v.get("name"), "meta": v.get("meta")}
                            for v in values
                        ]
                    except Exception as e:
                        entity_values[attr_name] = []
                        print(f"[supply] fetch values for '{attr_name}' error: {e}")

        return {
            "success": True,
            "data": {
                "folders": folders,
                "attributes": attr_meta if not isinstance(attr_meta, Exception) else {},
                "entity_values": entity_values,
                "organization": organization,
                "suppliers": suppliers,
                "last_articul_number": last_articul,
                "next_articul_number": last_articul + 1,
                # Codes from supply_codes.json
                "season_codes": codes.get("season_codes", {}),
                "group_codes": codes.get("group_codes", {}),
                "colors": codes.get("colors", []),
                "color_hex_map": codes.get("color_hex_map", {}),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"References yuklashda xato: {str(e)}")


# ─────────────────────────────────────────────
#  GET /last-articul
# ─────────────────────────────────────────────
@router.get("/last-articul")
async def get_last_articul():
    """Quick endpoint: return current last articul number."""
    last = await find_last_articul_number()
    return {"success": True, "last_number": last, "next_number": last + 1}


# ─────────────────────────────────────────────
#  Pydantic models
# ─────────────────────────────────────────────
class ColorEntry(BaseModel):
    color_name: str       # Display name (Turkish), e.g. "K.Bordo"
    color_code: str       # 3-letter code, e.g. "BRG"
    color_ru: str = ""    # Russian name for MoySklad attribute, e.g. "Бордовый"
    quantity: int


class CreateSupplyRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    # Folder (group)
    product_folder_id: str
    product_folder_meta: Dict
    product_folder_name: str = ""

    # Attributes — values as text (will be looked up / created in MS)
    product_type: str       # Вид товара:    "Свитер"
    category: str           # Категория:     "Свитеры и кардиганы"
    collection: str         # Коллекция:     "AW26"
    season: str             # Сезон:         "Весна-Осень"
    brand: str              # Бренд:         "LIWALI"
    size_range: str         # Размерный ряд: "M-3XL"
    series: str             # Серия:         "5"
    model_code: str         # Код модели:    "1M21241-1587"
    description: str = ""   # Описание

    # Pricing (UZS)
    purchase_price: float   # Закупочная цена
    sale_price: float       # Цена продажи

    # Generated articul values
    model_articul: str      # e.g. "A26TOP00405"
    product_name: str       # e.g. "Свитер варот замок мадел LIWALI 1M21241-1587"

    # Supplier (optional but recommended)
    supplier_meta: Optional[Dict] = None
    supplier_name: str = ""

    # Note for the supply document
    note: str = ""

    # Colors with quantities
    colors: List[ColorEntry]


# ─────────────────────────────────────────────
#  POST /create  — Main supply creation
# ─────────────────────────────────────────────
@router.post("/create")
async def create_supply(req: CreateSupplyRequest):
    """
    1) Get/create custom entity values for each product attribute
    2) For each color (qty > 0): check if product exists, create if not
    3) Create Приемка (supply) document with all product positions
    """
    colors_with_qty = [c for c in req.colors if c.quantity > 0]
    if not colors_with_qty:
        raise HTTPException(status_code=400, detail="Kamida bitta rangda miqdor kiritilishi shart")

    # ── 1. Organization ───────────────────────────────────────────
    orgs_resp = await ms_client._request("GET", "/entity/organization", params={"limit": 1})
    if not orgs_resp.get("rows"):
        raise HTTPException(status_code=500, detail="MoySkladda tashkilot topilmadi")
    org_meta = orgs_resp["rows"][0].get("meta")

    # ── 2. Currency & price type ──────────────────────────────────
    uzs_meta = await get_uzs_currency_meta()
    price_type_meta = await get_price_type_meta()

    # ── 3. Attribute metadata ─────────────────────────────────────
    attr_meta = await get_attribute_metadata()

    # ── 4. Build common attribute values ─────────────────────────
    # Map: attribute_name -> (value_text, use_this_for_all_colors)
    common_attrs_map = {
        "Вид товара":    req.product_type,
        "Категория":     req.category,
        "Коллекция":     req.collection,
        "Сезон":         req.season,
        "Бренд":         req.brand,
        "Серия":         req.series,
        "Размерный ряд": req.size_range,
        "Код модели":    req.model_code,
        "Модель":        req.model_articul,   # e.g. "A26TOP00405"
    }

    # Resolve each attribute value to its MS customentity meta
    attr_value_metas: Dict[str, Optional[Dict]] = {}
    for attr_name, value_text in common_attrs_map.items():
        if not value_text or attr_name not in attr_meta:
            continue
        entity_id = attr_meta[attr_name].get("customEntityId")
        if entity_id:
            meta = await get_or_create_customentity_value(entity_id, value_text)
            attr_value_metas[attr_name] = meta

    def build_attributes(color_name: str = None, color_ru: str = None) -> List[Dict]:
        """Build the attributes list for a product."""
        result = []
        for attr_name, value_meta in attr_value_metas.items():
            if value_meta is None:
                continue
            ai = attr_meta.get(attr_name)
            if not ai:
                continue
            result.append({
                "meta": ai["attr_meta"],
                "value": {"meta": value_meta},
            })

        # Add color attribute
        color_attr = attr_meta.get("Цвет")
        if color_attr and color_attr.get("customEntityId") and color_name:
            # Use Russian name for color (cleaner in MoySklad)
            color_display = color_ru if color_ru else color_name
            # Run synchronously impossible here — we need to await
            # This function will be called with pre-resolved color meta
            pass  # Handled per-color below

        return result

    # ── 5. Create product for each color ─────────────────────────
    created_products = []
    errors = []

    # Price in kopecks (MoySklad stores × 100)
    purchase_price_kopecks = int(req.purchase_price * 100)
    sale_price_kopecks = int(req.sale_price * 100)

    for color_entry in colors_with_qty:
        color_name = color_entry.color_name.strip()
        color_code = color_entry.color_code.strip()
        color_ru = color_entry.color_ru.strip() if color_entry.color_ru else color_name
        quantity = color_entry.quantity
        article = req.model_articul + color_code

        # Check if product already exists in MoySklad
        try:
            existing = await ms_client._request(
                "GET", "/entity/product", params={"filter": f"article={article}"}
            )
            existing_rows = existing.get("rows", [])
        except Exception:
            existing_rows = []

        if existing_rows:
            # Product exists — just use it
            product = existing_rows[0]
            created_products.append({
                "article": article,
                "color_name": color_name,
                "color_ru": color_ru,
                "quantity": quantity,
                "product_id": product.get("id"),
                "product_meta": product.get("meta"),
                "product_name": req.product_name,
                "is_new": False,
                "purchase_price": req.purchase_price,
                "sale_price": req.sale_price,
            })
            continue

        # Build attributes list (common + color)
        attributes = build_attributes()

        # Resolve color value
        color_attr_info = attr_meta.get("Цвет")
        if color_attr_info and color_attr_info.get("customEntityId"):
            color_meta = await get_or_create_customentity_value(
                color_attr_info["customEntityId"], color_ru
            )
            if color_meta:
                attributes.append({
                    "meta": color_attr_info["attr_meta"],
                    "value": {"meta": color_meta},
                })

        # Build product payload
        product_payload: Dict[str, Any] = {
            "name": req.product_name,
            "article": article,
            "description": req.description,
            "productFolder": {"meta": req.product_folder_meta},
            "buyPrice": {
                "value": purchase_price_kopecks,
                "currency": {"meta": uzs_meta} if uzs_meta else {},
            },
            "salePrices": [],
        }

        # Sale price
        sale_price_entry: Dict[str, Any] = {
            "value": sale_price_kopecks,
            "currency": {"meta": uzs_meta} if uzs_meta else {},
        }
        if price_type_meta:
            sale_price_entry["priceType"] = {"meta": price_type_meta}
        product_payload["salePrices"] = [sale_price_entry]

        if attributes:
            product_payload["attributes"] = attributes

        try:
            new_product = await ms_client._request("POST", "/entity/product", json_data=product_payload)
            created_products.append({
                "article": article,
                "color_name": color_name,
                "color_ru": color_ru,
                "quantity": quantity,
                "product_id": new_product.get("id"),
                "product_meta": new_product.get("meta"),
                "product_name": req.product_name,
                "is_new": True,
                "purchase_price": req.purchase_price,
                "sale_price": req.sale_price,
            })
        except Exception as e:
            errors.append(f"'{color_name}' ({article}): {str(e)}")
            print(f"[supply] Product creation error for {article}: {e}")

    if not created_products:
        raise HTTPException(
            status_code=500,
            detail=f"Hech bir tovar yaratilmadi. Xatolar: {'; '.join(errors)}"
        )

    # ── 6. Build supply (Приемка) document ────────────────────────
    positions = []
    for cp in created_products:
        if cp.get("product_meta"):
            positions.append({
                "quantity": cp["quantity"],
                "price": purchase_price_kopecks,
                "overhead": {"sum": 0},
                "assortment": {"meta": cp["product_meta"]},
            })

    supply_payload: Dict[str, Any] = {
        "organization": {"meta": org_meta},
        "positions": positions,
    }
    if req.supplier_meta:
        supply_payload["agent"] = {"meta": req.supplier_meta}
    if req.note:
        supply_payload["description"] = req.note

    # Try to create supply document
    supply_id = None
    supply_name = None
    supply_url = None

    try:
        supply_doc = await ms_client._request("POST", "/entity/supply", json_data=supply_payload)
        supply_id = supply_doc.get("id")
        supply_name = supply_doc.get("name", "")
        supply_url = f"https://online.moysklad.ru/app/#supply/edit?id={supply_id}"
    except Exception as e:
        # Partial success: products created but supply doc failed
        return {
            "success": True,
            "partial": True,
            "message": (
                f"{len(created_products)} ta tovar yaratildi, lekin "
                f"Priemka hujjatida xato: {str(e)}"
            ),
            "supply_id": None,
            "supply_url": None,
            "supply_name": None,
            "products": created_products,
            "errors": errors,
            "total_qty": sum(c.quantity for c in colors_with_qty),
        }

    total_qty = sum(c["quantity"] for c in created_products)
    new_count = sum(1 for c in created_products if c["is_new"])

    return {
        "success": True,
        "partial": False,
        "message": (
            f"✅ {new_count} ta yangi tovar yaratildi, "
            f"jami {total_qty} dona Priemka hujjatiga kiritildi!"
        ),
        "supply_id": supply_id,
        "supply_url": supply_url,
        "supply_name": supply_name,
        "products": created_products,
        "errors": errors,
        "total_qty": total_qty,
    }


# ─────────────────────────────────────────────
#  GET /list  — Recent supply documents
# ─────────────────────────────────────────────
@router.get("/list")
async def get_supply_list(limit: int = 50):
    """List recent Приемка documents from MoySklad."""
    try:
        resp = await ms_client._request(
            "GET", "/entity/supply",
            params={
                "limit": limit,
                "order": "moment,desc",
                "expand": "agent,organization",
            },
        )
        supplies = []
        for s in resp.get("rows", []):
            supplies.append({
                "id": s.get("id"),
                "name": s.get("name", ""),
                "moment": s.get("moment", ""),
                "description": s.get("description", ""),
                "agent_name": (s.get("agent") or {}).get("name", ""),
                "org_name": (s.get("organization") or {}).get("name", ""),
                "sum": s.get("sum", 0),
                "positions_count": s.get("positions", {}).get("meta", {}).get("size", 0),
            })
        return {"success": True, "data": supplies, "total": resp.get("meta", {}).get("size", 0)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
