from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
from database import get_db, AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from models_db import SyncQueue
import json
from sqlalchemy import select
from moysklad_client import ms_client
import asyncio
import httpx
from fastapi import APIRouter, HTTPException, Depends

router = APIRouter()


class MixedPaymentRequest(BaseModel):
    demand_id: str
    cash_amount: float = 0.0
    card_amount: float = 0.0
    usd_amount: float = 0.0
    usd_rate: float = 12800.0
    usd_account_id: Optional[str] = None
    account_id: Optional[str] = None
    description: Optional[str] = None
    update_payment_attribute: bool = False
    # Qolgan qarz (linked sum cheklash uchun)
    demand_remaining: Optional[float] = None


# ===== TO'LOV TARIXI =====
@router.get("/demand/{demand_id}")
async def get_demand_payments(demand_id: str):
    """Sotuvga bog'langan barcha to'lovlar (operations, payments ref, demand ref, purpose bo'yicha)"""
    try:
        # 1. Sotuv ma'lumotlarini olish
        demand = await ms_client.get_demand(demand_id)
        demand_name = demand.get("name", "")
        demand_href_part = f"/entity/demand/{demand_id}"
        search_term = f"Sotuv {demand_name}" if demand_name else ""

        # Demand ichidagi payments havolalari
        demand_payment_hrefs = set()
        demand_payments_ref = demand.get("payments", [])
        if isinstance(demand_payments_ref, list):
            for pref in demand_payments_ref:
                if isinstance(pref, dict):
                    phref = pref.get("meta", {}).get("href", "")
                    if phref:
                        demand_payment_hrefs.add(phref)

        # 2. Barcha to'lovlarni olish (keshdan tezkor)
        all_payments = await ms_client.get_all_payments_cached()
        cashins = all_payments.get("cashins", [])
        paymentins = all_payments.get("paymentins", [])

        matched_payments = []
        matched_payment_ids = set()
        total_paid = 0.0

        def check_payment_match(doc: dict, doc_type: str, type_name: str):
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

            # Shart 1: demand.payments ichida ushbu to'lov havolasi bormi?
            if doc_href and doc_href in demand_payment_hrefs:
                matched = True

            # Shart 2: operations ichida ushbu demand bormi?
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

            # Shart 3: demand havolasi bormi?
            if not matched:
                demand_ref = doc.get("demand", {})
                if isinstance(demand_ref, dict):
                    d_href = demand_ref.get("meta", {}).get("href", "")
                    if demand_href_part in d_href or (demand_id in d_href):
                        matched = True
                        if doc.get("linkedSum"):
                            raw_linked = doc.get("linkedSum", 0) / 100.0
                            linked_amount = (raw_linked * rate_val) if is_usd else raw_linked

            # Faqat rasmiy bog'langan to'lovlar (demand.payments yoki operations)
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
            check_payment_match(c, "cash", "💵 Naqd")

        for p in paymentins:
            check_payment_match(p, "card", "💳 Karta")

        # Agar MoySklad payedSum qaytargan bo'lsa va total_paid 0 bo'lsa
        demand_payed_sum = demand.get("payedSum", 0) / 100.0
        if total_paid == 0 and demand_payed_sum > 0:
            total_paid = demand_payed_sum

        # Sana bo'yicha saralash
        matched_payments.sort(key=lambda x: x.get("moment", ""), reverse=True)

        print(f"✅ Sotuv {demand_name} to'lovlari: {len(matched_payments)} ta, jami {total_paid:,.0f} so'm")
        return {
            "success": True,
            "data": {
                "payments": matched_payments,
                "total_paid": total_paid,
            }
        }
    except Exception as e:
        print(f"❌ To'lov tarixi xatosi: {e}")
        import traceback
        traceback.print_exc()
        return {"success": True, "data": {"payments": [], "total_paid": 0}}

# ===== MIJOZ BALANSI =====
@router.get("/balance/{counterparty_id}")
async def get_counterparty_balance(counterparty_id: str):
    """Mijoz balansi"""
    try:
        balance = await ms_client.get_counterparty_balance_report(counterparty_id)
        cp = await ms_client.get_counterparty(counterparty_id)
        return {
            "success": True,
            "data": {
                "name": cp.get("name", "Noma'lum"),
                "balance": balance,
            }
        }
    except Exception as e:
        print(f"❌ Balans xatosi: {e}")
        return {"success": True, "data": {"name": "", "balance": 0}}


# ===== HISOB RAQAMLAR & KASSALAR =====
@router.get("/accounts/{org_id}")
async def get_org_accounts(org_id: str):
    """Tashkilot hisob raqamlari va kassalari"""
    try:
        accounts = await ms_client.get_organization_accounts(org_id)
        formatted = []

        # 1. Asosiy naqd kassa
        formatted.append({
            "id": "cash_default",
            "name": "💵 Asosiy Naqd Kassa (UZS)",
            "rawName": "Asosiy Naqd Kassa",
            "accountnumber": "KASSA-UZS",
            "bankName": "Kassa",
            "isDefault": False,
            "isDollar": False,
            "type": "cash",
        })

        # 2. Bank va Valyuta hisob raqamlari
        for i, a in enumerate(accounts):
            bank = a.get("bankName", "")
            num = a.get("accountnumber", "")
            name = a.get("name", "")

            is_dollar = "dollar" in (name + " " + num).lower()

            if not name or name in ("None", "undefined", "", "Hisob"):
                if num:
                    name = f"Hisob: {num}"
                elif bank:
                    name = bank
                else:
                    name = f"Hisob {i+1}"

            if is_dollar:
                icon = "💵"
                acc_type = "dollar"
                display_name = f"Dollar ({num or name})" if "dollar" not in name.lower() else name
            else:
                icon = "🏦"
                acc_type = "bank"
                display_name = name

            if bank and bank not in display_name and not is_dollar:
                display_name = f"{display_name} ({bank})"

            formatted.append({
                "id": a.get("id"),
                "name": f"{icon} {display_name}",
                "rawName": display_name,
                "accountnumber": num,
                "bankName": bank,
                "isDefault": a.get("isDefault", False),
                "isDollar": is_dollar,
                "type": acc_type,
            })

        return {"success": True, "data": formatted}
    except Exception as e:
        print(f"[Accounts endpoint error] {e}")
        return {"success": True, "data": []}


# ===== ОПЛАТА ATRIBUTI =====
@router.get("/attributes/{demand_id}")
async def get_demand_attributes(demand_id: str):
    """Demand qo'shimcha maydonlarini olish (Оплата ID uchun)"""
    try:
        attrs_resp = await ms_client._request("GET", "/entity/demand/metadata/attributes")

        print(f"🔬 Attributes response kalitlari: {list(attrs_resp.keys())}")

        attrs_list = attrs_resp.get("rows", [])
        print(f"🔬 Attributes soni: {len(attrs_list)}")
        print(f"🔬 Attributes: {[a.get('name') for a in attrs_list if isinstance(a, dict)]}")

        oplata_attr = None
        for a in attrs_list:
            if not isinstance(a, dict):
                continue

            attr_name = a.get("name", "").lower()
            attr_id = a.get("id", "")

            if "оплат" in attr_name or "oplata" in attr_name:
                # ⬅️ MUHIM: meta href ni ham saqlash
                attr_meta = a.get("meta", {})
                attr_href = attr_meta.get("href", f"{ms_client.base_url}/entity/demand/metadata/attributes/{attr_id}")

                oplata_attr = {
                    "id": attr_id,
                    "name": a.get("name"),
                    "type": a.get("type", "long"),
                    "href": attr_href,
                }
                print(f"✅ 'Оплата' atributi topildi: {a.get('name')} (ID: {attr_id})")
                break

        if not oplata_attr:
            names = [a.get('name') for a in attrs_list if isinstance(a, dict)]
            print(f"⚠️ 'Оплата' topilmadi. Mavjud: {names}")

        return {"success": True, "data": oplata_attr}
    except Exception as e:
        print(f"❌ Attributes xatosi: {e}")
        import traceback
        traceback.print_exc()
        return {"success": True, "data": None}


# ===== ARALASH TO'LOV YARATISH =====
@router.post("/mixed")
async def create_mixed_payment(payment: MixedPaymentRequest, db: AsyncSession = Depends(get_db)):
    """Naqd + Karta aralash to'lov yaratish"""
    try:
        demand_id = payment.demand_id

        # 1. Sotuv ma'lumotlarini olish (retry bilan)
        demand = None
        for attempt in range(3):
            try:
                demand = await ms_client.get_demand(demand_id)
                break
            except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                print(f"   ⚠️ Timeout (urinish {attempt+1}/3), qayta urinilmoqda...")
                await asyncio.sleep(2)
            except Exception as e:
                raise

        if not demand:
            raise HTTPException(status_code=500, detail="Sotuv ma'lumotlarini olib bo'lmadi (timeout)")

        demand_sum = demand.get("sum", 0) / 100.0
        demand_href = demand.get("meta", {}).get("href", f"{ms_client.base_url}/entity/demand/{demand_id}")

        agent = demand.get("agent", {})
        agent_meta = agent.get("meta", {})
        agent_id = agent.get("id") or agent_meta.get("href", "").split("/")[-1]

        org = demand.get("organization", {})
        org_meta = org.get("meta", {})
        org_id = org.get("id") or org_meta.get("href", "").split("/")[-1]

        # Eski balans
        old_balance = await ms_client.get_counterparty_balance_report(agent_id)
        print(f"👤 Eski balans: {old_balance:,.0f} so'm")

        print(f"\n💰 ARALASH TO'LOV:")
        print(f"   💵 Naqd: {payment.cash_amount:,.0f} so'm")
        print(f"   💳 Karta: {payment.card_amount:,.0f} so'm")

        # Vaqt zonasi (Moskva vaqti UTC+3)
        moment_str = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

        # Qolgan qarzni aniqlash (связанные документы uchun linkedSum cheklash)
        # Agar demand_remaining berilmagan bo'lsa, demand.payedSum dan hisoblaymiz
        demand_payed_already = demand.get("payedSum", 0) / 100.0
        demand_remaining_before = max(0.0, demand_sum - demand_payed_already)

        # Joriy to'lov jami (UZS)
        usd_amt_for_calc = payment.usd_amount or 0.0
        usd_rt_for_calc = payment.usd_rate if payment.usd_rate and payment.usd_rate > 0 else 12800.0
        total_new_payment = (payment.cash_amount or 0.0) + (payment.card_amount or 0.0) + (usd_amt_for_calc * usd_rt_for_calc)

        # Связанные документы uchun har bir to'lov linked summasini hisoblash
        # Agar jami to'lov > qarz bo'lsa, linked_sum = qarz (ortiqcha qism bog'lanmaydi)
        remaining_to_link = demand_remaining_before

        demand_op_meta = {
            "meta": {
                "href": demand_href,
                "type": "demand",
                "mediaType": "application/json"
            }
        }

        # 2. NAQD to'lov (связанные документы)
        cash_result = None
        if payment.cash_amount > 0:
            cash_linked = min(payment.cash_amount, max(0.0, remaining_to_link))
            remaining_to_link = max(0.0, remaining_to_link - payment.cash_amount)
            cash_data = {
                "agent": {"meta": agent_meta},
                "organization": {"meta": org_meta},
                "sum": int(payment.cash_amount * 100),
                "moment": moment_str,
                "paymentPurpose": payment.description or f"Sotuv {demand.get('name')} uchun naqd",
                "operations": [
                    {
                        "meta": demand_op_meta["meta"],
                        "linkedSum": int(cash_linked * 100),
                    }
                ],
            }
            print(f"   💵 Naqd to'lov yaratilmoqda... linked={cash_linked:,.0f}")
            cash_result = await ms_client.create_cashin(cash_data)

        # 3. KARTA to'lov (связанные документы)
        card_result = None
        if payment.card_amount > 0:
            card_linked = min(payment.card_amount, max(0.0, remaining_to_link))
            remaining_to_link = max(0.0, remaining_to_link - payment.card_amount)
            card_data = {
                "agent": {"meta": agent_meta},
                "organization": {"meta": org_meta},
                "sum": int(payment.card_amount * 100),
                "moment": moment_str,
                "paymentPurpose": payment.description or f"Sotuv {demand.get('name')} uchun karta",
                "operations": [
                    {
                        "meta": demand_op_meta["meta"],
                        "linkedSum": int(card_linked * 100),
                    }
                ],
            }

            # Hisob raqami
            if payment.account_id and org_id and payment.account_id != "cash_default":
                account_href = f"{ms_client.base_url}/entity/organization/{org_id}/accounts/{payment.account_id}"
                acc_meta_obj = {
                    "meta": {
                        "href": account_href,
                        "type": "account",
                        "mediaType": "application/json"
                    }
                }
                card_data["account"] = acc_meta_obj
                card_data["organizationAccount"] = acc_meta_obj

            print(f"   💳 Karta to'lov yaratilmoqda... linked={card_linked:,.0f}")
            card_result = await ms_client.create_paymentin(card_data)

        # 3.5 DOLLAR to'lov (связанные документы)
        usd_result = None
        usd_sum_uzs = 0.0
        if payment.usd_amount > 0:
            rate = payment.usd_rate if payment.usd_rate > 0 else 12800.0
            usd_sum_uzs = payment.usd_amount * rate  # UZS da
            usd_linked = min(usd_sum_uzs, max(0.0, remaining_to_link))
            remaining_to_link = max(0.0, remaining_to_link - usd_sum_uzs)
            target_usd_acc = payment.usd_account_id or "1749a7d1-ab4b-11f1-0a80-08ba00832cc6"
            usd_desc = payment.description or f"Sotuv {demand.get('name')} uchun dollar (${payment.usd_amount:,.2f} @ {rate:,.0f} so'm)"

            usd_curr_meta = await ms_client.get_usd_currency_meta()

            usd_payment_data = {
                "agent": {"meta": agent_meta},
                "organization": {"meta": org_meta},
                "sum": int(payment.usd_amount * 100),  # Asl valyutada (USD)
                "moment": moment_str,
                "paymentPurpose": usd_desc,
                "operations": [
                    {
                        "meta": demand_op_meta["meta"],
                        "linkedSum": int(usd_linked * 100),
                    }
                ],
            }
            
            if usd_curr_meta:
                usd_payment_data["rate"] = {
                    "currency": {"meta": usd_curr_meta},
                    "value": float(rate)
                }
            if target_usd_acc and org_id:
                account_href = f"{ms_client.base_url}/entity/organization/{org_id}/accounts/{target_usd_acc}"
                usd_acc_meta = {
                    "meta": {
                        "href": account_href,
                        "type": "account",
                        "mediaType": "application/json"
                    }
                }
                usd_payment_data["account"] = usd_acc_meta
                usd_payment_data["organizationAccount"] = usd_acc_meta

            print(f"   💵 Dollar to'lov: ${payment.usd_amount} @ {rate} = {usd_sum_uzs:,.0f} so'm (linked={usd_linked:,.0f})")
            usd_result = await ms_client.create_paymentin(usd_payment_data)

        # 4. new_payed hisoblash (ESKI TO'LOVLAR + YANGI)
        # MoySklad'dan qayta so'rov qilishdan oldin 2 soniya kutish
        # (yangi to'lovlar MoySklad'da paydo bo'lishi uchun)
        await asyncio.sleep(2)
        
        old_payments = await ms_client.get_demand_payments(demand_id)
        old_payed = 0.0
        for c in old_payments.get("cashins", []):
            old_payed += c.get("sum", 0) / 100.0
        for p in old_payments.get("paymentins", []):
            old_payed += p.get("sum", 0) / 100.0
        
        new_payed = old_payed
        new_cash = payment.cash_amount
        new_card = payment.card_amount
        new_usd = usd_sum_uzs

        # Yangi to'lovlar allaqachon oldingi to'lovlarga qo'shilganmi tekshirish
        if cash_result and cash_result.get("id"):
            cash_already = any(
                c.get("id") == cash_result.get("id")
                for c in old_payments.get("cashins", [])
            )
            if cash_already:
                new_cash = 0  # allaqachon hisoblangan

        if card_result and card_result.get("id"):
            card_already = any(
                p.get("id") == card_result.get("id")
                for p in old_payments.get("paymentins", [])
            )
            if card_already:
                new_card = 0  # allaqachon hisoblangan

        if usd_result and usd_result.get("id"):
            usd_already = any(
                p.get("id") == usd_result.get("id")
                for p in old_payments.get("paymentins", [])
            )
            if usd_already:
                new_usd = 0  # allaqachon hisoblangan

        new_payed = old_payed + new_cash + new_card + new_usd
        new_remaining = demand_sum - new_payed

        print(f"   💰 Hisoblash: old={old_payed:,.0f} + cash={new_cash:,.0f} + card={new_card:,.0f} + usd={new_usd:,.0f} = {new_payed:,.0f}")

        # 5. "Оплата" qo'shimcha maydonini yangilash
        print(f"🔬 update_payment_attribute = {payment.update_payment_attribute}, new_payed = {new_payed}")

        if payment.update_payment_attribute and new_payed > 0:
            try:
                print(f"   📝 'Оплата' yangilanmoqda...")
                attrs_resp = await ms_client._request("GET", "/entity/demand/metadata/attributes")
                attrs_list = attrs_resp.get("rows", [])

                oplata_attr = None
                for a in attrs_list:
                    if isinstance(a, dict):
                        name = a.get("name", "").lower()
                        if "оплат" in name or "oplata" in name:
                            oplata_attr = a
                            print(f"   ✅ 'Оплата' topildi: {a.get('name')} (ID: {a.get('id')})")
                            break

                if oplata_attr and oplata_attr.get("id"):
                    demand_url = f"{ms_client.base_url}/entity/demand/{demand_id}"
                    oplata_value = int(round(new_payed))

                    # ⬅️ MUHIM: MoySklad uchun meta kerak!
                    attr_id = oplata_attr.get("id")
                    attr_href = oplata_attr.get("meta", {}).get(
                        "href",
                        f"{ms_client.base_url}/entity/demand/metadata/attributes/{attr_id}"
                    )

                    update_data = {
                        "attributes": [
                            {
                                "meta": {
                                    "href": attr_href,
                                    "type": "attributemetadata",
                                    "mediaType": "application/json"
                                },
                                "value": oplata_value,
                            }
                        ]
                    }

                    print(f"   📤 Yuborilayotgan: {update_data}")

                    async with ms_client.semaphore:
                        await ms_client.rate_limiter.acquire()
                        response = await ms_client._client.request(
                            "PUT",
                            demand_url,
                            headers=ms_client.headers,
                            json=update_data,
                        )

                        if response.status_code == 200:
                            print(f"   ✅ 'Оплата' yangilandi: {oplata_value} so'm")
                        else:
                            print(f"   ⚠️ 'Оплата' yangilanmadi: status={response.status_code}")
                            print(f"   Response: {response.text[:500]}")
                else:
                    print(f"   ⚠️ 'Оплата' maydoni topilmadi")
            except Exception as e:
                print(f"   ❌ 'Оплата' yangilash xatosi: {e}")
                import traceback
                traceback.print_exc()

        # 6. Yangi balans
        new_balance = await ms_client.get_counterparty_balance_report(agent_id)

        print(f"\n✅ YAKUNIY:")
        print(f"   To'landi: {new_payed:,.0f} / {demand_sum:,.0f} so'm")
        print(f"   Qoldi: {new_remaining:,.0f} so'm")
        print(f"   Balans: {old_balance:,.0f} → {new_balance:,.0f} so'm")

        return {
            "success": True,
            "data": {
                "total_paid": new_payed,
                "remaining": new_remaining,
                "demand_sum": demand_sum,
                "old_balance": old_balance,
                "new_balance": new_balance,
                "cash_result": {"id": cash_result.get("id")} if cash_result else None,
                "card_result": {"id": card_result.get("id")} if card_result else None,
            },
            "offline": False
        }
    except (httpx.RequestError, asyncio.TimeoutError) as network_err:
        print(f"📡 Tarmoq xatosi (Offline mode To'lov): {network_err}")
        # SyncQueue ga yozamiz
        payload = payment.dict()
        db.add(SyncQueue(
            action="create_mixed_payment",
            local_id=payment.demand_id,
            payload=json.dumps(payload),
            status="pending"
        ))
        await db.commit()
        return {
            "success": True,
            "message": "Tarmoq aloqasi yo'q. To'lov oflayn saqlandi.",
            "offline": True,
            "data": {
                "total_paid": 0,
                "remaining": 0,
                "demand_sum": 0,
                "old_balance": 0,
                "new_balance": 0,
                "cash_result": None,
                "card_result": None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ To'lov xatosi:")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class CustomerPaymentRequest(BaseModel):
    counterparty_id: str
    cash_amount: float = 0.0
    card_amount: float = 0.0
    usd_amount: float = 0.0
    usd_rate: float = 12800.0
    usd_account_id: Optional[str] = None
    account_id: Optional[str] = None
    demand_id: Optional[str] = None
    demand_ids: Optional[List[str]] = None
    linked_demands: Optional[List[Dict[str, Any]]] = None  # [{"demand_id": "...", "amount": 1000.0}]
    auto_fifo: Optional[bool] = False
    description: Optional[str] = ""


@router.post("/customer")
@router.post("/customer-payment")
async def create_customer_payment(payment: CustomerPaymentRequest):
    """Mijozga to'lov kiritish (sotuvlarga FIFO bo'yicha bog'lash imkoniyati bilan)"""
    try:
        # Mijoz va tashkilot ma'lumotlari
        cp = await ms_client.get_counterparty(payment.counterparty_id)
        org_resp = await ms_client._request("GET", "/entity/organization", params={"limit": 1})
        org = org_resp.get("rows", [])[0] if org_resp.get("rows") else None
        
        if not org:
            raise HTTPException(status_code=400, detail="Tashkilot topilmadi")
        
        agent_meta = {
            "href": f"{ms_client.base_url}/entity/counterparty/{payment.counterparty_id}",
            "type": "counterparty",
            "mediaType": "application/json"
        }
        org_meta = org.get("meta", {})
        
        moment_str = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

        # Jami UZS summasi
        usd_rate = payment.usd_rate if payment.usd_rate and payment.usd_rate > 0 else 12800.0
        usd_sum_uzs = (payment.usd_amount or 0.0) * usd_rate
        total_payment_uzs = (payment.cash_amount or 0.0) + (payment.card_amount or 0.0) + usd_sum_uzs

        # Bog'lanadigan sotuvlar ro'yxatini (pool) shakllantirish (FIFO)
        to_link_pool = []
        if payment.linked_demands:
            for item in payment.linked_demands:
                did = item.get("demand_id")
                amt = float(item.get("amount") or 0.0)
                if did and amt > 0.01:
                    to_link_pool.append({
                        "demand_id": did,
                        "amount": amt,
                        "remaining_to_allocate": amt,
                        "total_allocated": 0.0
                    })
        elif payment.demand_id:
            to_link_pool.append({
                "demand_id": payment.demand_id,
                "amount": total_payment_uzs,
                "remaining_to_allocate": total_payment_uzs,
                "total_allocated": 0.0
            })
        elif payment.demand_ids or payment.auto_fifo:
            # Lokal DB dan mijozning to'lanmagan sotuvlarini eskidan yangiga (FIFO) tartibda olish
            from database import AsyncSessionLocal
            from models_db import LocalDemand
            async with AsyncSessionLocal() as db:
                stmt = (
                    select(LocalDemand)
                    .where(LocalDemand.agent_id == payment.counterparty_id, LocalDemand.remaining > 0.01)
                    .order_by(LocalDemand.moment.asc())
                )
                unpaid_rows = (await db.execute(stmt)).scalars().all()
                if payment.demand_ids:
                    filter_ids = set(payment.demand_ids)
                    unpaid_rows = [d for d in unpaid_rows if d.id in filter_ids]

                budget = total_payment_uzs
                for d in unpaid_rows:
                    if budget <= 0.01:
                        break
                    alloc = min(budget, float(d.remaining or 0.0))
                    if alloc > 0.01:
                        to_link_pool.append({
                            "demand_id": d.id,
                            "amount": alloc,
                            "remaining_to_allocate": alloc,
                            "total_allocated": 0.0
                        })
                        budget -= alloc

        def extract_operations(pay_amount_uzs: float):
            """To'lov hujjati (cashin / paymentin) uchun MoySklad operations array yaratish"""
            ops = []
            avail = pay_amount_uzs
            for item in to_link_pool:
                if avail <= 0.01:
                    break
                needed = item["remaining_to_allocate"]
                if needed <= 0.01:
                    continue
                take = min(avail, needed)
                item["remaining_to_allocate"] -= take
                item["total_allocated"] += take
                avail -= take
                ops.append({
                    "meta": {
                        "href": f"{ms_client.base_url}/entity/demand/{item['demand_id']}",
                        "type": "demand",
                        "mediaType": "application/json"
                    },
                    "linkedSum": int(round(take * 100))
                })
            return ops

        # 1. Naqd to'lov (cashin)
        if payment.cash_amount > 0:
            cash_ops = extract_operations(payment.cash_amount)
            cash_data = {
                "agent": {"meta": agent_meta},
                "organization": {"meta": org_meta},
                "sum": int(round(payment.cash_amount * 100)),
                "moment": moment_str,
                "paymentPurpose": payment.description or "Mijozdan to'lov (Naqd)",
            }
            if cash_ops:
                cash_data["operations"] = cash_ops
            await ms_client.create_cashin(cash_data)

        # 2. Karta / Bank to'lov (paymentin)
        if payment.card_amount > 0:
            card_ops = extract_operations(payment.card_amount)
            card_data = {
                "agent": {"meta": agent_meta},
                "organization": {"meta": org_meta},
                "sum": int(round(payment.card_amount * 100)),
                "moment": moment_str,
                "paymentPurpose": payment.description or "Mijozdan to'lov (Karta/Bank)",
            }
            if card_ops:
                card_data["operations"] = card_ops

            if payment.account_id and payment.account_id != "cash_default" and org.get("id"):
                account_href = f"{ms_client.base_url}/entity/organization/{org.get('id')}/accounts/{payment.account_id}"
                acc_meta_obj = {
                    "meta": {
                        "href": account_href,
                        "type": "account",
                        "mediaType": "application/json"
                    }
                }
                card_data["account"] = acc_meta_obj
                card_data["organizationAccount"] = acc_meta_obj

            await ms_client.create_paymentin(card_data)

        # 3. Dollar to'lov (paymentin USD)
        if payment.usd_amount > 0:
            usd_ops = extract_operations(usd_sum_uzs)
            target_usd_acc = payment.usd_account_id
            usd_desc = payment.description or f"Dollar to'lov (${payment.usd_amount:,.2f} @ {usd_rate:,.0f} so'm)"
            usd_curr_meta = await ms_client.get_usd_currency_meta()

            usd_data = {
                "agent": {"meta": agent_meta},
                "organization": {"meta": org_meta},
                "sum": int(round(payment.usd_amount * 100)),  # USD valyutasida (sentlarda)
                "moment": moment_str,
                "paymentPurpose": usd_desc,
            }
            if usd_curr_meta:
                usd_data["rate"] = {
                    "currency": {"meta": usd_curr_meta},
                    "value": float(usd_rate)
                }
            if usd_ops:
                usd_data["operations"] = usd_ops

            if target_usd_acc and org.get("id"):
                account_href = f"{ms_client.base_url}/entity/organization/{org.get('id')}/accounts/{target_usd_acc}"
                usd_acc_meta = {
                    "meta": {
                        "href": account_href,
                        "type": "account",
                        "mediaType": "application/json"
                    }
                }
                usd_data["account"] = usd_acc_meta
                usd_data["organizationAccount"] = usd_acc_meta

            await ms_client.create_paymentin(usd_data)

        # 4. Lokal DB ni darhol yangilash (tezkor javob berish uchun)
        try:
            from database import AsyncSessionLocal
            from models_db import LocalDemand, LocalCounterparty
            async with AsyncSessionLocal() as db:
                for item in to_link_pool:
                    alloc_amt = item.get("total_allocated", 0.0)
                    if alloc_amt > 0.01:
                        d_obj = await db.scalar(select(LocalDemand).where(LocalDemand.id == item["demand_id"]))
                        if d_obj:
                            d_obj.payed_sum = (d_obj.payed_sum or 0.0) + alloc_amt
                            d_obj.remaining = max(0.0, (d_obj.sum or 0.0) - d_obj.payed_sum)
                            if d_obj.remaining <= 0.01:
                                d_obj.payment_status = "paid"
                                d_obj.payment_status_name = "To'langan"
                            else:
                                d_obj.payment_status = "partial"
                                d_obj.payment_status_name = "Qisman"
                
                cp_obj = await db.scalar(select(LocalCounterparty).where(LocalCounterparty.id == payment.counterparty_id))
                if cp_obj:
                    cp_obj.balance = (cp_obj.balance or 0.0) - total_payment_uzs
                await db.commit()
        except Exception as dbe:
            print(f"⚠️ Local DB to'lov yangilash xatosi (davom etiladi): {dbe}")

        # Keshlarni tozalash
        ms_client.invalidate_demands_cache()
        ms_client.invalidate_payments_cache()
        ms_client.invalidate_counterparties_cache()

        return {
            "success": True,
            "data": {
                "cash": payment.cash_amount,
                "card": payment.card_amount,
                "usd": payment.usd_amount,
                "usd_uzs": usd_sum_uzs,
                "total": total_payment_uzs,
                "linked_demands_count": len([item for item in to_link_pool if item.get("total_allocated", 0) > 0]),
                "linked_allocations": [
                    {"demand_id": item["demand_id"], "amount": item["total_allocated"]}
                    for item in to_link_pool if item.get("total_allocated", 0) > 0
                ]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Customer payment xatosi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ================= XARAJAT MODDALARI VA KASSA =================
class ExpenseItemCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""


class ExpenseCreateRequest(BaseModel):
    amount: float
    payment_type: str = "cash"  # 'cash' yoki 'card'
    expense_item_id: Optional[str] = None
    description: Optional[str] = ""
    account_id: Optional[str] = None


@router.get("/expense-items")
async def get_expense_items():
    """Barcha xarajat moddalari (Статьи расходов)"""
    try:
        items = await ms_client.get_expense_items()
        formatted = []
        for it in items:
            formatted.append({
                "id": it.get("id"),
                "name": it.get("name", ""),
                "description": it.get("description", ""),
            })
        return {"success": True, "data": formatted}
    except Exception as e:
        print(f"❌ Expense items xatosi: {e}")
        return {"success": True, "data": []}


@router.post("/expense-items")
async def create_expense_item(item: ExpenseItemCreateRequest):
    """Yangi xarajat moddasi yaratish"""
    try:
        res = await ms_client.create_expense_item(item.name.strip(), item.description or "")
        return {"success": True, "data": res}
    except Exception as e:
        print(f"❌ Create expense item xatosi: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expense")
async def create_expense(expense: ExpenseCreateRequest):
    """
    Yangi xarajat kiritish:
    - payment_type == 'cash' -> Kassa chiqim orderi (cashout)
    - payment_type == 'card' -> Bank chiqim to'lovi (paymentout)
    """
    try:
        if expense.amount <= 0:
            raise HTTPException(status_code=400, detail="Xarajat summasi 0 dan katta bo'lishi kerak")

        # Tashkilot
        org_resp = await ms_client._request("GET", "/entity/organization", params={"limit": 1})
        org = org_resp.get("rows", [])[0] if org_resp.get("rows") else None
        if not org:
            raise HTTPException(status_code=400, detail="Tashkilot topilmadi")

        org_meta = org.get("meta", {})
        moment_str = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

        expense_item_meta = None
        if expense.expense_item_id:
            expense_item_meta = {
                "href": f"{ms_client.base_url}/entity/expenseitem/{expense.expense_item_id}",
                "type": "expenseitem",
                "mediaType": "application/json",
            }
        else:
            expense_item_meta = {
                "href": f"{ms_client.base_url}/entity/expenseitem/metadata",
                "type": "expenseitem",
                "mediaType": "application/json",
            }

        purpose = expense.description or "Xarajat"

        if expense.payment_type == "cash":
            cashout_data = {
                "organization": {"meta": org_meta},
                "sum": int(expense.amount * 100),
                "moment": moment_str,
                "paymentPurpose": purpose,
                "expenseItem": {"meta": expense_item_meta},
            }
            res = await ms_client.create_cashout(cashout_data)
            print(f"💸 Naqd xarajat yaratildi: {expense.amount:,.0f} so'm ({purpose})")
        else:
            paymentout_data = {
                "organization": {"meta": org_meta},
                "sum": int(expense.amount * 100),
                "moment": moment_str,
                "paymentPurpose": purpose,
                "expenseItem": {"meta": expense_item_meta},
            }
            if expense.account_id and expense.account_id != "cash_default" and org.get("id"):
                account_href = f"{ms_client.base_url}/entity/organization/{org.get('id')}/accounts/{expense.account_id}"
                acc_meta_obj = {
                    "meta": {
                        "href": account_href,
                        "type": "account",
                        "mediaType": "application/json",
                    }
                }
                paymentout_data["account"] = acc_meta_obj
                paymentout_data["organizationAccount"] = acc_meta_obj
            res = await ms_client.create_paymentout(paymentout_data)
            print(f"[Expense created] Bank xarajati: {expense.amount:,.0f} so'm ({purpose})")

        # Keshni tozalash
        ms_client.invalidate_payments_cache()

        return {"success": True, "data": res, "message": "Xarajat muvaffaqiyatli saqlandi"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Xarajat yaratish xatosi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cashflow")
async def get_cashflow(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    type_filter: Optional[str] = Query("all"),  # 'all', 'inflow', 'outflow'
    expense_item_id: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),    # 'all', 'cash_default', 'dollar', yoki <account_id>
):
    """
    Barcha kassa va hisob-kitoblar aylanmasi (Kassalar & Hisob raqamlar bog'langan):
    - Kirimlar: Cashin (Naqd) + Paymentin (Karta/Bank/Dollar)
    - Chiqimlar: Cashout (Naqd xarajat) + Paymentout (Bank/Dollar xarajat)
    - Valyuta: USD kursi va har bir operatsiya hamda umumiy qoldiqning Dollar ekvivalenti
    - Hisoblar tahlili: Har bir kassa va bank hisob raqamining alohida balansi
    """
    try:
        # 1. Joriy Dollar kursini olish
        usd_rate = 12800.0
        try:
            raw_curr = await ms_client.get_currencies()
            for c in raw_curr:
                if c.get("isoCode") == "USD":
                    usd_rate = float(c.get("rate", 12800.0))
                    break
        except Exception as e:
            print(f"[Cashflow currency rate error] {e}")

        # 2. Parallel so'rovlar bilan barcha operatsiyalar va kesh xaritalarni olish
        cashins_task = ms_client._request("GET", "/entity/cashin", params={"limit": 1000, "expand": "agent,organization"})
        paymentins_task = ms_client._request("GET", "/entity/paymentin", params={"limit": 1000, "expand": "agent,organization,organizationAccount"})
        cashouts_task = ms_client.get_cashouts(limit=1000)
        paymentouts_task = ms_client.get_paymentouts(limit=1000)
        counterparties_task = ms_client.get_all_counterparties_cached()
        org_task = ms_client.get_organization()

        cashins_resp, paymentins_resp, cashouts_rows, paymentouts_rows, counterparties_cached, org_info = await asyncio.gather(
            cashins_task, paymentins_task, cashouts_task, paymentouts_task, counterparties_task, org_task
        )

        # Kontragentlar va Hisoblar xaritasi (MoySklad expand cheklovi sababli ID bo'yicha aniqlash)
        agent_map = {}
        for cp in (counterparties_cached or []):
            if isinstance(cp, dict) and cp.get("id") and cp.get("name"):
                agent_map[cp["id"]] = cp["name"]

        account_map = {}
        try:
            if org_info and org_info.get("id"):
                org_accounts = await ms_client.get_organization_accounts(org_info["id"])
                for a in (org_accounts or []):
                    if isinstance(a, dict) and a.get("id") and a.get("name"):
                        account_map[a["id"]] = a["name"]
        except Exception as e:
            print(f"[Cashflow org_accounts error] {e}")

        def get_agent_display_name(obj, fallback="Kirim"):
            if not obj or not isinstance(obj, dict):
                return fallback
            if obj.get("name"):
                return obj["name"]
            aid = obj.get("id")
            if not aid:
                href = obj.get("meta", {}).get("href", "")
                aid = href.split("/")[-1] if href else ""
            if aid and aid in agent_map:
                return agent_map[aid]
            return fallback

        def get_account_display_name(p_dict, default_name="Bank hisobi"):
            acc = p_dict.get("organizationAccount") or p_dict.get("account") or {}
            if isinstance(acc, dict):
                if acc.get("name"):
                    return acc["name"]
                aid = acc.get("id")
                if not aid:
                    href = acc.get("meta", {}).get("href", "")
                    aid = href.split("/")[-1] if href else ""
                if aid and aid in account_map:
                    return account_map[aid]
                if acc.get("accountNumber") or acc.get("accountnumber"):
                    return acc.get("accountNumber") or acc.get("accountnumber")
            return default_name

        all_tx = []

        # 1. Naqd kirimlar (Asosiy Naqd Kassa)
        for c in cashins_resp.get("rows", []):
            agent_name = get_agent_display_name(c.get("agent"), fallback="Kassa kirim")
            amt = c.get("sum", 0) / 100.0
            usd_val = round(amt / usd_rate, 2) if usd_rate > 0 else 0.0

            all_tx.append({
                "id": c.get("id"),
                "doc_type": "cashin",
                "direction": "in",
                "type_name": "💵 Naqd kirim",
                "doc_number": c.get("name", "—"),
                "moment": c.get("moment", ""),
                "amount": amt,
                "usd_amount": usd_val,
                "account_id": "cash_default",
                "account_name": "💵 Asosiy Naqd Kassa",
                "account_type": "cash",
                "target_name": agent_name,
                "expense_item": "Mijoz to'lovi",
                "purpose": c.get("paymentPurpose", "") or "Kassa kirim",
            })

        # 2. Bank / Hisob kirimlari
        for p in paymentins_resp.get("rows", []):
            agent_name = get_agent_display_name(p.get("agent"), fallback="Bank kirim")
            acc_name = get_account_display_name(p, default_name="Bank hisobi")
            is_dollar = "dollar" in acc_name.lower()
            acc = p.get("organizationAccount") or p.get("account") or {}
            acc_id = acc.get("id") or (acc.get("meta", {}).get("href", "").split("/")[-1] if isinstance(acc, dict) and acc.get("meta") else "")
            acc_num = acc.get("accountNumber") or acc.get("accountnumber", "") if isinstance(acc, dict) else ""

            amt = p.get("sum", 0) / 100.0
            usd_val = round(amt / usd_rate, 2) if usd_rate > 0 else 0.0
            acc_type = "dollar" if is_dollar else "bank"

            all_tx.append({
                "id": p.get("id"),
                "doc_type": "paymentin",
                "direction": "in",
                "type_name": "💵 Dollar kirim" if is_dollar else "💳 Bank kirim",
                "doc_number": p.get("name", "—"),
                "moment": p.get("moment", ""),
                "amount": amt,
                "usd_amount": usd_val,
                "account_id": acc_id or "bank_other",
                "account_name": f"{'💵' if is_dollar else '🏦'} {acc_name}",
                "account_number": acc_num,
                "account_type": acc_type,
                "target_name": agent_name,
                "expense_item": "Bank/karta to'lovi",
                "purpose": p.get("paymentPurpose", "") or "Hisobga kirim",
            })

        # 3. Naqd xarajatlar / chiqimlar
        for co in cashouts_rows:
            exp = co.get("expenseItem", {})
            exp_name = exp.get("name", "Xarajat") if isinstance(exp, dict) else "Xarajat"
            exp_id = exp.get("id", "") if isinstance(exp, dict) else ""
            agent_name = get_agent_display_name(co.get("agent"), fallback="")
            target = exp_name if not agent_name else f"{exp_name} ({agent_name})"
            amt = co.get("sum", 0) / 100.0
            usd_val = round(amt / usd_rate, 2) if usd_rate > 0 else 0.0

            all_tx.append({
                "id": co.get("id"),
                "doc_type": "cashout",
                "direction": "out",
                "type_name": "💸 Naqd xarajat",
                "doc_number": co.get("name", "—"),
                "moment": co.get("moment", ""),
                "amount": amt,
                "usd_amount": usd_val,
                "account_id": "cash_default",
                "account_name": "💵 Asosiy Naqd Kassa",
                "account_type": "cash",
                "target_name": target,
                "expense_item": exp_name,
                "expense_item_id": exp_id,
                "purpose": co.get("paymentPurpose", "") or "Kassa chiqim",
            })

        # 4. Bank xarajatlari / chiqimlari
        for po in paymentouts_rows:
            exp = po.get("expenseItem", {})
            exp_name = exp.get("name", "Bank xarajati") if isinstance(exp, dict) else "Bank xarajati"
            exp_id = exp.get("id", "") if isinstance(exp, dict) else ""
            agent_name = get_agent_display_name(po.get("agent"), fallback="")
            target = exp_name if not agent_name else f"{exp_name} ({agent_name})"
            acc_name = get_account_display_name(po, default_name="Bank hisobi")
            is_dollar = "dollar" in acc_name.lower()
            acc = po.get("organizationAccount") or po.get("account") or {}
            acc_id = acc.get("id") or (acc.get("meta", {}).get("href", "").split("/")[-1] if isinstance(acc, dict) and acc.get("meta") else "")
            acc_num = acc.get("accountNumber") or acc.get("accountnumber", "") if isinstance(acc, dict) else ""

            amt = po.get("sum", 0) / 100.0
            usd_val = round(amt / usd_rate, 2) if usd_rate > 0 else 0.0
            acc_type = "dollar" if is_dollar else "bank"

            all_tx.append({
                "id": po.get("id"),
                "doc_type": "paymentout",
                "direction": "out",
                "type_name": "💸 Dollar chiqim" if is_dollar else "🏛️ Bank xarajat",
                "doc_number": po.get("name", "—"),
                "moment": po.get("moment", ""),
                "amount": amt,
                "usd_amount": usd_val,
                "account_id": acc_id or "bank_other",
                "account_name": f"{'💵' if is_dollar else '🏦'} {acc_name}",
                "account_number": acc_num,
                "account_type": acc_type,
                "target_name": target,
                "expense_item": exp_name,
                "expense_item_id": exp_id,
                "purpose": po.get("paymentPurpose", "") or "Bank chiqim",
            })

        # Sanaga qarab saralash (eng yangisi tepada)
        all_tx.sort(key=lambda x: x["moment"], reverse=True)

        # 3. Filtrlash
        filtered_tx = all_tx

        # Sana filtrlash
        if date_from:
            start_bound = f"{date_from} 00:00:00"
            filtered_tx = [t for t in filtered_tx if t["moment"] >= start_bound]
        if date_to:
            end_bound = f"{date_to} 23:59:59"
            filtered_tx = [t for t in filtered_tx if t["moment"] <= end_bound]

        # Tur filtrlash
        if type_filter == "inflow":
            filtered_tx = [t for t in filtered_tx if t["direction"] == "in"]
        elif type_filter == "outflow":
            filtered_tx = [t for t in filtered_tx if t["direction"] == "out"]

        # Xarajat moddasi filtrlash
        if expense_item_id:
            filtered_tx = [t for t in filtered_tx if t.get("expense_item_id") == expense_item_id]

        # Hisob raqam bo'yicha filtrlash
        if account_id and account_id != "all":
            if account_id == "cash_default":
                filtered_tx = [t for t in filtered_tx if t.get("account_id") == "cash_default"]
            elif account_id == "dollar":
                filtered_tx = [t for t in filtered_tx if t.get("account_type") == "dollar"]
            else:
                filtered_tx = [t for t in filtered_tx if t.get("account_id") == account_id]

        # Jami hisob-kitoblar (filtrlangan)
        total_inflow = sum(t["amount"] for t in filtered_tx if t["direction"] == "in")
        total_outflow = sum(t["amount"] for t in filtered_tx if t["direction"] == "out")
        net_balance = total_inflow - total_outflow

        # Dual-currency ajratish (So'm va Dollar alohida)
        inflow_uzs = sum(t["amount"] for t in filtered_tx if t["direction"] == "in" and t.get("account_type") != "dollar")
        inflow_usd = sum(t.get("usd_amount", 0.0) for t in filtered_tx if t["direction"] == "in" and (t.get("account_type") == "dollar" or t.get("usd_amount", 0) > 0))

        outflow_uzs = sum(t["amount"] for t in filtered_tx if t["direction"] == "out" and t.get("account_type") != "dollar")
        outflow_usd = sum(t.get("usd_amount", 0.0) for t in filtered_tx if t["direction"] == "out" and (t.get("account_type") == "dollar" or t.get("usd_amount", 0) > 0))

        net_uzs = inflow_uzs - outflow_uzs
        net_usd = inflow_usd - outflow_usd

        # Naqd va Bank qoldiqlari (filtrlangan)
        cash_in = sum(t["amount"] for t in filtered_tx if t["doc_type"] == "cashin")
        cash_out = sum(t["amount"] for t in filtered_tx if t["doc_type"] == "cashout")
        card_in = sum(t["amount"] for t in filtered_tx if t["doc_type"] == "paymentin")
        card_out = sum(t["amount"] for t in filtered_tx if t["doc_type"] == "paymentout")

        # 4. Hisoblar bo'yicha to'liq balanslar (Account Balances breakdown)
        # Barcha mavjud hisoblarni MoySklad'dan olish
        org_accs = []
        try:
            org = await ms_client.get_organization()
            if org.get("id"):
                org_accs = await ms_client.get_organization_accounts(org.get("id"))
        except Exception as e:
            print(f"[Accounts fetch in cashflow error] {e}")

        from routers.settings import load_settings
        settings_data = load_settings()
        corrections = settings_data.get("corrections", {})
        ref_rate = settings_data.get("reference_usd_rate", 12800.0)

        account_balances = []

        # 1. Asosiy naqd kassa
        c_in = sum(t["amount"] for t in all_tx if t["account_id"] == "cash_default" and t["direction"] == "in")
        c_out = sum(t["amount"] for t in all_tx if t["account_id"] == "cash_default" and t["direction"] == "out")
        c_bal_raw = c_in - c_out
        c_corr = corrections.get("cash_default")
        c_bal = float(c_corr["adjusted_balance"]) if (c_corr and "adjusted_balance" in c_corr) else c_bal_raw

        account_balances.append({
            "id": "cash_default",
            "name": "💵 Asosiy Naqd Kassa (UZS)",
            "raw_name": "Asosiy Naqd Kassa",
            "accountnumber": "KASSA-UZS",
            "type": "cash",
            "currency": "UZS",
            "is_dollar": False,
            "inflow": c_in,
            "outflow": c_out,
            "balance": c_bal,
            "raw_balance": c_bal_raw,
            "has_correction": bool(c_corr and "adjusted_balance" in c_corr),
            "correction": c_corr,
        })

        total_uzs_balance = c_bal
        total_usd_balance = 0.0

        # 2. Har bir bank va valyuta hisob raqami
        for a in org_accs:
            a_id = a.get("id")
            a_name = a.get("name") or a.get("accountnumber") or "Bank hisobi"
            a_num = a.get("accountnumber", "")
            is_dol = "dollar" in (a_name + " " + a_num).lower()

            a_in = sum(t["amount"] for t in all_tx if t.get("account_id") == a_id and t["direction"] == "in")
            a_out = sum(t["amount"] for t in all_tx if t.get("account_id") == a_id and t["direction"] == "out")
            a_bal_raw = a_in - a_out

            a_corr = corrections.get(a_id)
            if a_corr and "adjusted_balance" in a_corr:
                final_bal = float(a_corr["adjusted_balance"])
                has_corr = True
            else:
                final_bal = a_bal_raw
                has_corr = False

            if is_dol:
                total_usd_balance += final_bal
            else:
                total_uzs_balance += final_bal

            account_balances.append({
                "id": a_id,
                "name": f"{'💵' if is_dol else '🏦'} {a_name}",
                "raw_name": a_name,
                "accountnumber": a_num,
                "type": "dollar" if is_dol else "bank",
                "currency": "USD" if is_dol else "UZS",
                "is_dollar": is_dol,
                "is_default": a.get("isDefault", False),
                "inflow": a_in,
                "outflow": a_out,
                "balance": final_bal,
                "raw_balance": a_bal_raw,
                "has_correction": has_corr,
                "correction": a_corr,
            })

        consolidated_uzs = total_uzs_balance + (total_usd_balance * ref_rate)

        return {
            "success": True,
            "data": {
                "summary": {
                    "total_inflow": total_inflow,
                    "total_outflow": total_outflow,
                    "net_balance": net_balance,
                    "inflow_uzs": inflow_uzs,
                    "inflow_usd": inflow_usd,
                    "outflow_uzs": outflow_uzs,
                    "outflow_usd": outflow_usd,
                    "net_uzs": net_uzs,
                    "net_usd": net_usd,
                    "total_uzs_balance": total_uzs_balance,
                    "total_usd_balance": total_usd_balance,
                    "reference_usd_rate": ref_rate,
                    "consolidated_uzs_equivalent": consolidated_uzs,
                    "cash_balance": cash_in - cash_out,
                    "card_balance": card_in - card_out,
                    "count": len(filtered_tx),
                    "account_balances": account_balances,
                },
                "transactions": filtered_tx,
            }
        }
    except Exception as e:
        print(f"[Cashflow error] {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class PaymentUpdateRequest(BaseModel):
    amount: Optional[float] = None
    purpose: Optional[str] = None
    moment: Optional[str] = None
    linked_demand_id: Optional[str] = None
    unlink_demands: Optional[bool] = False
    usd_amount: Optional[float] = None
    usd_rate: Optional[float] = None


@router.get("/{doc_type}/{payment_id}")
async def get_payment_detail(doc_type: str, payment_id: str):
    """To'lov hujjati tafsilotlari"""
    valid_types = ["cashin", "paymentin", "cashout", "paymentout"]
    if doc_type not in valid_types:
        raise HTTPException(status_code=400, detail="Noto'g'ri to'lov turi")
    try:
        doc = await ms_client._request("GET", f"/entity/{doc_type}/{payment_id}", params={"expand": "agent,organization,operations,organizationAccount"})
        return {"success": True, "data": doc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{doc_type}/{payment_id}")
async def update_payment(doc_type: str, payment_id: str, req: PaymentUpdateRequest):
    """To'lov hujjatini tahrirlash (summa, izoh, sana, sotuvga bog'lash)"""
    valid_types = ["cashin", "paymentin", "cashout", "paymentout"]
    if doc_type not in valid_types:
        raise HTTPException(status_code=400, detail="Noto'g'ri to'lov turi")

    try:
        update_data = {}
        if req.purpose is not None:
            update_data["paymentPurpose"] = req.purpose

        if req.moment:
            m_str = req.moment.replace("T", " ")
            if len(m_str) == 16:
                m_str += ":00"
            update_data["moment"] = m_str

        # Summa va kurs
        if req.usd_amount is not None and req.usd_amount > 0:
            rate = req.usd_rate if (req.usd_rate and req.usd_rate > 0) else 12800.0
            update_data["sum"] = int(req.usd_amount * 100)
            usd_curr_meta = await ms_client.get_usd_currency_meta()
            if usd_curr_meta:
                update_data["rate"] = {
                    "currency": {"meta": usd_curr_meta},
                    "value": float(rate)
                }
        elif req.amount is not None:
            update_data["sum"] = int(req.amount * 100)

        # Sotuvga bog'lash / uzish
        if req.unlink_demands:
            update_data["operations"] = []
        elif req.linked_demand_id:
            demand = await ms_client.get_demand(req.linked_demand_id)
            if demand and demand.get("meta"):
                op_sum = int((req.amount or 0) * 100) if req.amount else None
                if not op_sum and "sum" in update_data:
                    op_sum = update_data["sum"]
                op_obj = {
                    "meta": demand["meta"]
                }
                if op_sum:
                    op_obj["linkedSum"] = op_sum
                update_data["operations"] = [op_obj]

        res = await ms_client._request("PUT", f"/entity/{doc_type}/{payment_id}", json_data=update_data)

        # Mahalliy DB keshini yangilash
        try:
            from database import AsyncSessionLocal
            from models_db import LocalPayment
            async with AsyncSessionLocal() as db:
                lp = await db.get(LocalPayment, payment_id)
                if lp:
                    if "sum" in update_data:
                        lp.sum = update_data["sum"] / 100.0
                    if "moment" in update_data:
                        lp.moment = update_data["moment"]
                    if "paymentPurpose" in update_data:
                        lp.purpose = update_data["paymentPurpose"]
                    if req.linked_demand_id:
                        lp.demand_id = req.linked_demand_id
                    elif req.unlink_demands:
                        lp.demand_id = ""
                    await db.commit()
        except Exception:
            pass

        ms_client.invalidate_payments_cache()
        return {"success": True, "message": "To'lov muvaffaqiyatli yangilandi", "data": res}
    except Exception as e:
        print(f"❌ Payment update xatosi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{doc_type}/{payment_id}")
async def delete_payment(doc_type: str, payment_id: str):
    """To'lov hujjatini o'chirish"""
    valid_types = ["cashin", "paymentin", "cashout", "paymentout"]
    if doc_type not in valid_types:
        raise HTTPException(status_code=400, detail="Noto'g'ri to'lov turi")

    try:
        await ms_client._request("DELETE", f"/entity/{doc_type}/{payment_id}")

        # Mahalliy DB dan o'chirish
        try:
            from database import AsyncSessionLocal
            from models_db import LocalPayment
            async with AsyncSessionLocal() as db:
                lp = await db.get(LocalPayment, payment_id)
                if lp:
                    await db.delete(lp)
                    await db.commit()
        except Exception:
            pass

        ms_client.invalidate_payments_cache()
        return {"success": True, "message": "To'lov muvaffaqiyatli o'chirildi"}
    except Exception as e:
        print(f"❌ Payment delete xatosi: {e}")
        raise HTTPException(status_code=500, detail=str(e))