import sys
import io
import httpx
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from config import get_settings

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        try:
            text = " ".join(str(a) for a in args)
            clean_text = text.encode("ascii", "replace").decode("ascii")
            sys.stdout.write(clean_text + "\n")
        except Exception:
            pass

settings = get_settings()


class RateLimiter:
    """Sekundiga maksimal N ta so'rovni cheklash"""

    def __init__(self, rate: float = 10.0):
        self.rate = rate
        self.interval = 1.0 / rate
        self.last_request = 0.0
        self._lock = None
        self._loop = None

    async def acquire(self):
        try:
            cur_loop = asyncio.get_running_loop()
        except RuntimeError:
            cur_loop = None

        if self._lock is None or self._loop is not cur_loop:
            self._lock = asyncio.Lock()
            self._loop = cur_loop

        async with self._lock:
            now = time.monotonic()
            wait_time = self.last_request + self.interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                self.last_request = time.monotonic()
            else:
                self.last_request = now


class MoySkladClient:
    """MoySklad REST API klienti (Connection Pooling bilan)"""

    def __init__(self):
        self.base_url = settings.moysklad_api_url
        self.headers = {
            "Authorization": f"Bearer {settings.moysklad_token}",
            "Content-Type": "application/json",
        }
        # HIMOYA: Rate limiter va Semaphore (MoySklad API yangi cheklovlari)
        self.rate_limiter = RateLimiter(rate=3.5)  # Max 11 reqs per 3 sec (1 dekabrdan)
        self._semaphore = None
        self._sem_loop = None

        self._client = None
        self._client_loop = None

        # Statistika
        self.total_requests = 0
        self.rate_limit_hits = 0
        self._actual_cache_lock = None
        self._cache_lock_loop = None
        
        # Keshlash
        self._currencies_cache = {"data": None, "timestamp": 0}
        self.CURRENCIES_CACHE_TTL = 3600  # 1 soat

    def update_token(self, new_token: str):
        """Yangi MoySklad API tokenni o'rnatish va ulanishlarni yangilash"""
        self.headers["Authorization"] = f"Bearer {new_token}"
        if self._client and not self._client.is_closed:
            self._client.headers["Authorization"] = f"Bearer {new_token}"
        else:
            self._client = None
        print(f"[MoySkladClient] API token muvaffaqiyatli yangilandi: {new_token[:8]}...")

    def get_http_client(self):
        try:
            cur_loop = asyncio.get_running_loop()
        except RuntimeError:
            cur_loop = None

        if self._client is None or self._client.is_closed or self._client_loop is not cur_loop:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=5.0),
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30.0,
                ),
                headers=self.headers,
            )
            self._client_loop = cur_loop
        return self._client

    def get_semaphore(self):
        try:
            cur_loop = asyncio.get_running_loop()
        except RuntimeError:
            cur_loop = None

        if self._semaphore is None or self._sem_loop is not cur_loop:
            self._semaphore = asyncio.Semaphore(3)  # Bir vaqtda eng ko'pi 3 ta so'rov
            self._sem_loop = cur_loop
        return self._semaphore

    @property
    def _cache_lock(self):
        try:
            cur_loop = asyncio.get_running_loop()
        except RuntimeError:
            cur_loop = None

        if getattr(self, "_actual_cache_lock", None) is None or getattr(self, "_cache_lock_loop", None) is not cur_loop:
            self._actual_cache_lock = asyncio.Lock()
            self._cache_lock_loop = cur_loop
        return self._actual_cache_lock

    async def close(self):
        """Ilovani yopishda chaqiriladi"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Umumiy HTTP so'rov (pooling + rate limit + retry)"""
        url = f"{self.base_url}{endpoint}"
        client = self.get_http_client()
        sem = self.get_semaphore()

        async with sem:
            for attempt in range(max_retries):
                await self.rate_limiter.acquire()
                self.total_requests += 1

                try:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json_data,
                    )

                    # 429 Rate Limit bo'lsa — kutib qayta urinish
                    if response.status_code == 429:
                        self.rate_limit_hits += 1
                        wait_time = 2 ** attempt
                        safe_print(f"⚠️ 429 Rate Limit! {wait_time}s kutmoqda... ({attempt+1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue

                    if response.status_code >= 400:
                        err_detail = ""
                        try:
                            err_json = response.json()
                            if "errors" in err_json:
                                err_msgs = [e.get("error", "") for e in err_json.get("errors", []) if e.get("error")]
                                err_detail = " | ".join(err_msgs)
                        except Exception:
                            pass
                        if not err_detail:
                            err_detail = response.text or f"HTTP {response.status_code}"
                        
                        safe_print(f"❌ MoySklad Xatolik [{response.status_code}] {method} {url}: {err_detail}")
                        raise Exception(f"MoySklad API xatosi ({response.status_code}): {err_detail}")

                    return response.json()

                except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                    if attempt < max_retries - 1:
                        safe_print(f"⚠️ Ulanish xatosi, qayta urinilmoqda... ({attempt+1}/{max_retries})")
                        await asyncio.sleep(1)
                        continue
                    raise

        raise Exception(f"Maksimal urinishlar oshib ketdi: {endpoint}")

    def get_stats(self) -> Dict:
        return {
            "total_requests": self.total_requests,
            "rate_limit_hits": self.rate_limit_hits,
        }

    # ================= VALYUTALAR =================
    async def get_currencies(self) -> list:
        """Barcha valyutalarni keshdan olish"""
        import time
        now = time.time()
        if self._currencies_cache["data"] is not None and (now - self._currencies_cache["timestamp"]) <= self.CURRENCIES_CACHE_TTL:
            return self._currencies_cache["data"]
            
        async with self._cache_lock:
            now = time.time()
            if self._currencies_cache["data"] is None or (now - self._currencies_cache["timestamp"]) > self.CURRENCIES_CACHE_TTL:
                try:
                    resp = await self._request("GET", "/entity/currency")
                    self._currencies_cache["data"] = resp.get("rows", [])
                    self._currencies_cache["timestamp"] = now
                except Exception as e:
                    print(f"⚠️ Currencies xatosi: {e}")
                    return []
        return self._currencies_cache["data"]

    async def get_usd_currency_meta(self) -> Optional[Dict]:
        """USD valyutasining metadata sini topish"""
        currencies = await self.get_currencies()
        for c in currencies:
            iso = (c.get("isoCode") or "").upper()
            code = str(c.get("code") or "")
            name = (c.get("name") or "").lower()
            full_name = (c.get("fullName") or "").lower()
            if iso == "USD" or code == "840" or "usd" in name or "dollar" in name or "$" in name or "dollar" in full_name:
                return c.get("meta")
        return {
            "href": f"{self.base_url}/entity/currency/45062adb-ab4a-11f1-0a80-0bf500815be8",
            "metadataHref": f"{self.base_url}/entity/currency/metadata",
            "type": "currency",
            "mediaType": "application/json"
        }

    # ================= OTGRUZKA (DEMAND) =================
    async def get_demands(
        self,
        limit: int = 50,
        offset: int = 0,
        moment_from: Optional[str] = None,
        moment_to: Optional[str] = None,
        counterparty_id: Optional[str] = None,
    ) -> Dict:
        """Otgruzkalar ro'yxati"""
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "expand": "agent,organization,state"
        }
        filters = []
        if moment_from:
            filters.append(f"moment>={moment_from}")
        if moment_to:
            filters.append(f"moment<={moment_to}")
        if counterparty_id:
            filters.append(f"agent.id={counterparty_id}")
        if filters:
            params["filter"] = ";".join(filters)
        return await self._request("GET", "/entity/demand", params=params)

    async def get_demand(self, demand_id: str) -> Dict:
        """Bitta otgruzka (kengaytirilgan: agent, state, owner)"""
        return await self._request(
            "GET", 
            f"/entity/demand/{demand_id}", 
            params={"expand": "agent,state,owner"}
        )

    async def create_demand(self, data: Dict) -> Dict:
        """Yangi otgruzka yaratish"""
        return await self._request("POST", "/entity/demand", json_data=data)

    async def update_demand(self, demand_id: str, data: Dict) -> Dict:
        """Otgruzkani yangilash (skidka, status va h.k.)"""
        url = f"{self.base_url}/entity/demand/{demand_id}"

        async with self.get_semaphore():
            await self.rate_limiter.acquire()
            self.total_requests += 1

            for attempt in range(3):
                response = await self._client.request(
                    "PUT", url,
                    headers=self.headers,
                    json=data,
                )

                if response.status_code == 429:
                    self.rate_limit_hits += 1
                    await asyncio.sleep(2 ** attempt)
                    continue

                print(f"   📤 MoySklad'ga yuborilgan data: {data}")
                response.raise_for_status()
                return response.json()

        raise Exception("update_demand: maksimal urinishlar oshdi")

    async def get_demand_positions(self, demand_id: str) -> Dict:
        """Otgruzka tovarlari"""
        return await self._request("GET", f"/entity/demand/{demand_id}/positions", params={"expand": "assortment"})

    async def update_demand_position(self, demand_id: str, position_id: str, data: Dict) -> Dict:
        """Bitta tovar narxi/miqdorini o'zgartirish"""
        return await self._request("PUT", f"/entity/demand/{demand_id}/positions/{position_id}", json_data=data)

    # ================= TOVAR QO'SHISH / O'CHIRISH =================
    async def add_demand_position(self, demand_id: str, data: Dict) -> Dict:
        """Otgruzkaga yangi tovar qo'shish (MoySklad array qaytaradi)"""
        url = f"{self.base_url}/entity/demand/{demand_id}/positions"

        async with self.get_semaphore():
            await self.rate_limiter.acquire()
            self.total_requests += 1

            response = await self._client.request(
                "POST", url,
                headers=self.headers,
                json=[data],  # ARRAY sifatida (batch mode)
            )

            response.raise_for_status()
            result = response.json()

            # MoySklad array qaytaradi, birinchi elementni olamiz
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return result if isinstance(result, dict) else {}

    async def update_demand_positions_batch(self, demand_id: str, positions_data: list) -> list:
        """Barcha tovar pozitsiyalarini BIR SO'ROVDA yangilash (batch update)"""
        url = f"{self.base_url}/entity/demand/{demand_id}/positions"

        async with self.get_semaphore():
            await self.rate_limiter.acquire()
            self.total_requests += 1

            response = await self._client.request(
                "POST", url,
                headers=self.headers,
                json=positions_data,
            )

            response.raise_for_status()
            result = response.json()

            if isinstance(result, list):
                print(f"   📦 Batch update: {len(result)} ta pozitsiya yangilandi")
                return result
            return []

    async def delete_demand_position(self, demand_id: str, position_id: str) -> bool:
        """Otgruzkadan tovar o'chirish"""
        url = f"{self.base_url}/entity/demand/{demand_id}/positions/{position_id}"

        async with self.get_semaphore():
            await self.rate_limiter.acquire()
            self.total_requests += 1

            response = await self._client.request(
                "DELETE", url,
                headers=self.headers,
            )

            if response.status_code in (200, 204):
                return True

            response.raise_for_status()
            return True

    # ================= TOVAR QIDIRISH =================
    async def search_assortment_enhanced(self, query: str) -> Dict:
        """Kengaytirilgan qidiruv: kod, nom, barcode (EAN13)"""
        all_results = {}
        query_stripped = query.strip()

        # 1. Barcode (EAN13) - faqat raqamlar
        if query_stripped.isdigit() and len(query_stripped) >= 4:
            try:
                resp = await self._request("GET", "/entity/assortment",
                                           params={"limit": 20, "filter": f"barcode={query_stripped}"})
                for item in resp.get("rows", []):
                    all_results[item.get("id")] = item
            except:
                pass

        # 2. Kod va nom bo'yicha
        if len(query_stripped) >= 2:
            try:
                resp = await self._request("GET", "/entity/assortment",
                                           params={"limit": 20, "filter": f"code~{query_stripped}"})
                for item in resp.get("rows", []):
                    all_results[item.get("id")] = item
            except:
                pass

            try:
                resp = await self._request("GET", "/entity/assortment",
                                           params={"limit": 20, "filter": f"name~{query_stripped}"})
                for item in resp.get("rows", []):
                    all_results[item.get("id")] = item
            except:
                pass

        # 3. Umumiy search (zaxira)
        if not all_results and len(query_stripped) >= 2:
            try:
                resp = await self._request("GET", "/entity/assortment",
                                           params={"limit": 20, "search": query_stripped})
                for item in resp.get("rows", []):
                    all_results[item.get("id")] = item
            except:
                pass

        return {"rows": list(all_results.values())}

    # ================= TOVARLAR =================
    async def get_all_assortments(self) -> List[Dict]:
        """Barcha tovarlarni to'liq tortib olish (Pagination bilan)"""
        all_rows = []
        offset = 0
        limit = 1000
        while True:
            try:
                resp = await self._request("GET", "/entity/assortment", params={"limit": limit, "offset": offset})
                rows = resp.get("rows", [])
                if not rows:
                    break
                all_rows.extend(rows)
                meta = resp.get("meta", {})
                size = meta.get("size", len(all_rows))
                if len(all_rows) >= size or len(rows) < limit:
                    break
                offset += limit
            except Exception as e:
                print(f"⚠️ get_all_assortments error at offset {offset}: {e}")
                break
        return all_rows

    async def get_assortment(self, search: Optional[str] = None) -> Dict:
        """Tovarlar ro'yxati"""
        params = {"limit": 100}
        if search:
            params["search"] = search
        return await self._request("GET", "/entity/assortment", params=params)

    # ================= TO'LOVLAR (YARATISH) =================
    async def create_cashin(self, data: Dict) -> Dict:
        """Naqd to'lov yaratish (Приходный ордер)"""
        return await self._request("POST", "/entity/cashin", json_data=data)

    async def create_paymentin(self, data: Dict) -> Dict:
        """Karta/bank to'lov yaratish (Входящий платеж)"""
        return await self._request("POST", "/entity/paymentin", json_data=data)

    # ================= SOTUV TO'LOVLARINI OLISH =================
    async def get_demand_payments(self, demand_id: str) -> Dict:
        """Sotuvga bog'langan to'lovlar (faqat rasmiy bog'langan: demand.payments + operations)"""
        demand_name = ""
        demand_payment_hrefs = set()
        try:
            demand = await self.get_demand(demand_id)
            demand_name = demand.get("name", "")
            for p_ref in demand.get("payments", []):
                if isinstance(p_ref, dict):
                    h = p_ref.get("meta", {}).get("href", "")
                    if h:
                        demand_payment_hrefs.add(h)
        except Exception:
            pass

        all_payments = await self.get_all_payments_cached()
        target_href = f"/entity/demand/{demand_id}"

        def is_linked_to_demand(payment: dict) -> bool:
            # 1. demand.payments ro'yxatida to'g'ridan-to'g'ri bormi?
            p_href = payment.get("meta", {}).get("href", "")
            if p_href and p_href in demand_payment_hrefs:
                return True

            # 2. operations ichida (Связанный документ)
            operations = payment.get("operations", [])
            if isinstance(operations, list):
                for op in operations:
                    if isinstance(op, dict):
                        op_href = op.get("meta", {}).get("href", "")
                        if target_href in op_href or (demand_id in op_href):
                            return True

            # 3. demand to'g'ridan-to'g'ri havolasi
            demand_ref = payment.get("demand") or {}
            if isinstance(demand_ref, dict):
                href = demand_ref.get("meta", {}).get("href", "")
                if target_href in href or (demand_id in href):
                    return True
            
            return False

        cashins = [c for c in all_payments["cashins"] if is_linked_to_demand(c)]
        paymentins = [p for p in all_payments["paymentins"] if is_linked_to_demand(p)]

        print(f"💳 Bog'langan to'lovlar (faqat rasmiy): {len(cashins)} naqd + {len(paymentins)} karta (Sotuv {demand_name})")
        return {"cashins": cashins, "paymentins": paymentins}

    async def get_demand_payments_all(self, counterparty_id: str) -> float:
        """Mijozning barcha to'lovlarini olish (naqd + karta), jami summa"""
        try:
            date_from = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d 00:00:00")
            date_to = datetime.now().strftime("%Y-%m-%d 23:59:59")

            total = 0.0
            target_href_part = f"/entity/counterparty/{counterparty_id}"

            # Naqd to'lovlar
            cashins = await self._request(
                "GET", "/entity/cashin",
                params={"limit": 1000, "momentFrom": date_from, "momentTo": date_to}
            )
            for c in cashins.get("rows", []):
                agent = c.get("agent", {})
                if target_href_part in agent.get("meta", {}).get("href", ""):
                    total += c.get("sum", 0) / 100.0

            # Karta to'lovlar
            paymentins = await self._request(
                "GET", "/entity/paymentin",
                params={"limit": 1000, "momentFrom": date_from, "momentTo": date_to}
            )
            for p in paymentins.get("rows", []):
                agent = p.get("agent", {})
                if target_href_part in agent.get("meta", {}).get("href", ""):
                    total += p.get("sum", 0) / 100.0

            return total
        except Exception as e:
            print(f"   ⚠️ To'lovlar yig'ish xatosi: {e}")
            return 0.0

    # ================= MIJOZ (KONTRAGENT) =================
    async def get_counterparty(self, cp_id: str) -> Dict:
        """Mijoz ma'lumotlari"""
        return await self._request("GET", f"/entity/counterparty/{cp_id}")

    async def search_counterparties(self, query: str) -> Dict:
        """Mijoz qidirish"""
        return await self._request("GET", "/entity/counterparty", params={"search": query, "limit": 20})

    async def update_counterparty(self, cp_id: str, data: Dict) -> Dict:
        """Mijoz ma'lumotlarini tahrirlash"""
        return await self._request("PUT", f"/entity/counterparty/{cp_id}", json_data=data)

    async def create_counterparty(self, data: Dict) -> Dict:
        """Yangi mijoz (kontragent) yaratish"""
        return await self._request("POST", "/entity/counterparty", json_data=data)

    async def get_all_counterparties(self, limit: int = 1000) -> Dict:
        """Barcha mijozlar ro'yxati"""
        return await self._request("GET", "/entity/counterparty", params={"limit": limit})

    # ================= MIJOZ BALANSI =================
    async def get_counterparty_balance_report(self, counterparty_id: str) -> float:
        """
        Mijoz balansi — MoySklad report/counterparty dan olinadi (eng aniq usul).
        Musbat = mijoz bizga qarzdor.
        """
        try:
            report = await self._request("GET", "/report/counterparty", params={"limit": 1000})
            for row in report.get("rows", []):
                cp_href = row.get("counterparty", {}).get("meta", {}).get("href", "")
                if counterparty_id in cp_href:
                    # MoySklad'da manfiy = mijoz bizdan qarzdor, shuning uchun minus bilan olamiz
                    balance_kopecks = row.get("balance", 0)
                    return -float(balance_kopecks) / 100.0
            return 0.0
        except Exception as e:
            safe_print(f"   ⚠️ Balans xatosi: {e}")
            return 0.0

    # ================= TASHKILOT =================
    _org_cache: Optional[Dict] = {"id": "default", "name": "MoySklad Korxonasi", "inn": ""}
    _org_cache_time: float = 0.0

    async def get_organization(self) -> Dict:
        """Asosiy tashkilot (yuridik shaxs) ma'lumotlari (kesh va fallback bilan)"""
        now = time.time()
        if MoySkladClient._org_cache_time > 0 and (now - MoySkladClient._org_cache_time) < 1800:
            return MoySkladClient._org_cache
        try:
            result = await asyncio.wait_for(
                self._request("GET", "/entity/organization", params={"limit": 1}),
                timeout=2.5
            )
            rows = result.get("rows", [])
            if rows:
                MoySkladClient._org_cache = rows[0]
                MoySkladClient._org_cache_time = now
                return rows[0]
        except Exception as e:
            safe_print(f"[get_organization warning] {e}")

        return MoySkladClient._org_cache or {"id": "default", "name": "MoySklad Korxonasi", "inn": ""}

    _org_accounts_cache = {}
    _org_accounts_cache_time = 0.0

    # ================= TASHKILOT HISOB RAQAMLARI =================
    async def get_organization_accounts(self, org_id: str) -> list:
        """Tashkilotning barcha bank hisob raqamlari (Tezkor kesh bilan)"""
        if not org_id or org_id == "default":
            return []
        import time
        now = time.time()
        if org_id in MoySkladClient._org_accounts_cache and (now - MoySkladClient._org_accounts_cache_time) < 600:
            return MoySkladClient._org_accounts_cache[org_id]

        try:
            # To'g'ridan-to'g'ri accounts sub-resursiga so'rov (yengil va tez)
            try:
                resp = await asyncio.wait_for(
                    self._request("GET", f"/entity/organization/{org_id}/accounts"),
                    timeout=3.0
                )
                accounts_list = resp.get("rows", []) if isinstance(resp, dict) else []
            except Exception:
                org = await asyncio.wait_for(
                    self._request("GET", f"/entity/organization/{org_id}", params={"expand": "accounts"}),
                    timeout=3.0
                )
                accounts_raw = org.get("accounts", {})
                accounts_list = accounts_raw.get("rows", []) if isinstance(accounts_raw, dict) else (accounts_raw if isinstance(accounts_raw, list) else [])

            result_accounts = []
            for acc in accounts_list:
                if not isinstance(acc, dict):
                    continue

                acc_id = acc.get("id") or acc.get("meta", {}).get("href", "").split("/")[-1]
                account_num = acc.get("accountNumber") or acc.get("accountnumber", "")

                acc_name = (
                    acc.get("name") or
                    account_num or
                    acc.get("description") or
                    "Hisob"
                )

                if acc_id:
                    result_accounts.append({
                        "id": acc_id,
                        "name": acc_name,
                        "accountnumber": account_num,
                        "bankName": acc.get("bankName") or acc.get("bankLocation", ""),
                        "isDefault": acc.get("isDefault", False),
                    })

            MoySkladClient._org_accounts_cache[org_id] = result_accounts
            MoySkladClient._org_accounts_cache_time = now
            return result_accounts
        except Exception as e:
            safe_print(f"[get_organization_accounts warning] {e}")
            return MoySkladClient._org_accounts_cache.get(org_id, [])

            # Default hisobni birinchi qo'yish
            result_accounts.sort(key=lambda x: not x.get("isDefault", False))
            return result_accounts

        except Exception as e:
            print(f"[Accounts error] {e}")
            import traceback
            traceback.print_exc()
            return []

    # ================= DASHBOARD UCHUN =================
    async def get_demands_with_positions(
        self,
        limit: int = 1000,
        moment_from: Optional[str] = None,
        moment_to: Optional[str] = None,
    ) -> Dict:
        """Otgruzkalar + positions bir so'rovda"""
        params: Dict[str, Any] = {"limit": limit, "expand": "agent,positions"}
        filters = []
        if moment_from:
            filters.append(f"moment>={moment_from}")
        if moment_to:
            filters.append(f"moment<={moment_to}")
        if filters:
            params["filter"] = ";".join(filters)
        return await self._request("GET", "/entity/demand", params=params)

    async def get_cashins(self, moment_from: str, moment_to: str) -> Dict:
        """Naqd to'lovlar (dashboard uchun)"""
        params = {"limit": 1000, "filter": f"moment>={moment_from};moment<={moment_to}"}
        return await self._request("GET", "/entity/cashin", params=params)

    async def get_payments_in(self, moment_from: str, moment_to: str) -> Dict:
        """Karta/bank to'lovlar (dashboard uchun)"""
        params = {"limit": 1000, "filter": f"moment>={moment_from};moment<={moment_to}"}
        return await self._request("GET", "/entity/paymentin", params=params)

    async def get_total_debt(self) -> float:
        """Umumiy qarzdorlik (barcha mijozlar balansi yig'indisi)"""
        result = await self._request("GET", "/entity/counterparty", params={"limit": 1000})
        rows = result.get("rows", [])
        total = 0.0
        for cp in rows:
            balance = cp.get("balance", 0)
            if balance > 0:
                total += balance / 100.0
        return total

    # ================= METADATA =================
    _metadata_cache: Optional[Dict] = None
    _metadata_cache_time: float = 0.0

    async def get_demand_metadata(self) -> Dict:
        """Otgruzka metadata — statuslar ro'yxati uchun (kesh va zaxira bilan)"""
        now = time.time()
        if MoySkladClient._metadata_cache and (now - MoySkladClient._metadata_cache_time) < 600:
            return MoySkladClient._metadata_cache
        try:
            res = await self._request("GET", "/entity/demand/metadata")
            if res and "states" in res:
                MoySkladClient._metadata_cache = res
                MoySkladClient._metadata_cache_time = now
                return res
        except Exception as e:
            safe_print(f"[get_demand_metadata warning] {e}")

        if MoySkladClient._metadata_cache:
            return MoySkladClient._metadata_cache

        # Standart statuslar (tarmoq uzilganda yoki sekin ishlaganda qotib qolmaslik uchun)
        return {
            "states": [
                {"id": "new", "name": "Новый", "color": 10855845},
                {"id": "agreed", "name": "Договорились", "color": 3899638},
                {"id": "assembled", "name": "Собран", "color": 16109323},
                {"id": "on_the_way", "name": "В пути", "color": 9133302},
                {"id": "in_store", "name": "В магазине", "color": 439764},
                {"id": "closed", "name": "Закрыт", "color": 1096065},
                {"id": "cancelled", "name": "Отменен", "color": 15680324},
            ],
            "attributes": []
        }

    # ================= CHOP ETISH =================
    async def print_demand(self, demand_id: str, template_id: str) -> bytes:
        """Nakladnoyni PDF sifatida olish"""
        url = f"{self.base_url}/entity/demand/{demand_id}/print"
        await self.rate_limiter.acquire()
        response = await self._client.post(
            url,
            json={"templateId": template_id},
        )
        response.raise_for_status()
        return response.content

    # ================= BARCHA BALANSLAR (MOYSKLAD NATIV HISOBOT) =================
    async def get_all_balances(self) -> Dict[str, float]:
        """
        Barcha mijozlar rasmiy balanslarini MoySklad nativ hisobotidan (/report/counterparty) olish.
        Bu 100% MoySklad bilan bir xil bo'lishini (akt-sverka, korrektirovkalar, tovar qaytarishlar va h.k.) ta'minlaydi.
        """
        import time
        start = time.time()
        balances = {}
        try:
            resp = await self._request("GET", "/report/counterparty", params={"limit": 1000})
            for r in resp.get("rows", []):
                cp = r.get("counterparty", {})
                cp_id = cp.get("id")
                if cp_id:
                    # MoySklad report balance: manfiy = mijoz qarzi, musbat = mijoz haqdorligi
                    # Bizning ilovada: musbat = mijoz qarzi, manfiy = mijoz haqdorligi
                    ms_bal = float(r.get("balance", 0)) / 100.0
                    balances[cp_id] = -ms_bal

            elapsed = time.time() - start
            safe_print(f"📊 Barcha balanslar (MoySklad Nativ): {len(balances)} ta mijoz, {elapsed:.1f}s")
            return balances
        except Exception as e:
            safe_print(f"⚠️ MoySklad hisobotidan balanslarni olishda xato: {e}")
            return {}


    # ================= BARCHA SOTUVLAR (KESHLANGAN) =================
    _demands_cache = {"data": None, "timestamp": 0}
    DEMANDS_CACHE_TTL = 60  # 60 soniya

    async def get_all_demands_cached(self) -> list:
        """
        Barcha sotuvlarni keshdan olish (60 soniya).
        Agent bilan birga kengaytirilgan.
        """
        import time
        now = time.time()
        
        if self._demands_cache["data"] is not None and (now - self._demands_cache["timestamp"]) <= self.DEMANDS_CACHE_TTL:
            return self._demands_cache["data"]

        async with self._cache_lock:
            # Double-check inside lock
            now = time.time()
            if self._demands_cache["data"] is None or (now - self._demands_cache["timestamp"]) > self.DEMANDS_CACHE_TTL:
                safe_print("Sotuvlar keshi yangilanmoqda...")
                resp = await self._request(
                    "GET", "/entity/demand",
                    params={"limit": 1000, "expand": "agent"}
                )
                self._demands_cache["data"] = resp.get("rows", [])
                self._demands_cache["timestamp"] = now
                safe_print(f"Kesh: {len(self._demands_cache['data'])} ta sotuv")
        
        return self._demands_cache["data"]

    # ================= BARCHA TO'LOVLAR (KESHLANGAN) =================
    _payments_cache = {"cashins": None, "paymentins": None, "timestamp": 0}
    PAYMENTS_CACHE_TTL = 300  # 5 daqiqa kesh (to'lov kiritilganda avtomatik invalidate bo'ladi)

    async def get_all_payments_cached(self) -> dict:
        """Barcha to'lovlar (keshlangan, 10 soniya)"""
        import time
        now = time.time()
        
        if self._payments_cache["cashins"] is not None and (now - self._payments_cache["timestamp"]) <= self.PAYMENTS_CACHE_TTL:
            return {
                "cashins": self._payments_cache["cashins"],
                "paymentins": self._payments_cache["paymentins"],
            }

        async with self._cache_lock:
            # Double-check inside lock
            now = time.time()
            if self._payments_cache["cashins"] is None or (now - self._payments_cache["timestamp"]) > self.PAYMENTS_CACHE_TTL:
                safe_print("To'lovlar keshi yangilanmoqda...")
                cashins_resp = await self._request(
                    "GET", "/entity/cashin",
                    params={"limit": 1000, "expand": "agent,demand,operations"}
                )
                paymentins_resp = await self._request(
                    "GET", "/entity/paymentin",
                    params={"limit": 1000, "expand": "agent,demand,operations"}
                )
                self._payments_cache["cashins"] = cashins_resp.get("rows", [])
                self._payments_cache["paymentins"] = paymentins_resp.get("rows", [])
                self._payments_cache["timestamp"] = now
                safe_print(f"To'lovlar keshi: {len(self._payments_cache['cashins'])} naqd + {len(self._payments_cache['paymentins'])} karta")
        
        return {
            "cashins": self._payments_cache["cashins"],
            "paymentins": self._payments_cache["paymentins"],
        }
    
    def invalidate_payments_cache(self):
        """To'lovlar keshini majburiy tozalash"""
        self._payments_cache["cashins"] = None
        self._payments_cache["paymentins"] = None
        self._payments_cache["timestamp"] = 0

    def invalidate_demands_cache(self):
        """Sotuvlar keshini majburiy tozalash"""
        self._demands_cache["data"] = None
        self._demands_cache["timestamp"] = 0

    # ================= BARCHA MIJOZLAR (KESHLANGAN) =================
    _counterparties_cache = {"data": None, "timestamp": 0}
    COUNTERPARTIES_CACHE_TTL = 120  # 120 soniya

    async def get_all_counterparties_cached(self) -> list:
        """Barcha mijozlarni keshdan tez olish (120 soniya)"""
        import time
        now = time.time()
        if self._counterparties_cache["data"] is not None and (now - self._counterparties_cache["timestamp"]) <= self.COUNTERPARTIES_CACHE_TTL:
            return self._counterparties_cache["data"]

        async with self._cache_lock:
            # Double-check inside lock
            now = time.time()
            if self._counterparties_cache["data"] is None or (now - self._counterparties_cache["timestamp"]) > self.COUNTERPARTIES_CACHE_TTL:
                safe_print("Mijozlar keshi yangilanmoqda...")
                resp = await self._request("GET", "/entity/counterparty", params={"limit": 1000})
                self._counterparties_cache["data"] = resp.get("rows", [])
                self._counterparties_cache["timestamp"] = now
                safe_print(f"Mijozlar keshi: {len(self._counterparties_cache['data'])} ta")
        return self._counterparties_cache["data"]

    def invalidate_counterparties_cache(self):
        """Mijozlar keshini tozalash"""
        self._counterparties_cache["data"] = None
        self._counterparties_cache["timestamp"] = 0

    # ================= XARAJATLAR VA KASSA AMALLARI =================
    async def get_expense_items(self) -> list:
        """Xarajat moddalari ro'yxati (Статьи расходов)"""
        try:
            resp = await self._request("GET", "/entity/expenseitem", params={"limit": 100})
            return resp.get("rows", [])
        except Exception as e:
            print(f"⚠️ Expense items xatosi: {e}")
            return []

    async def create_expense_item(self, name: str, description: str = "") -> Dict:
        """Yangi xarajat moddasi yaratish"""
        data = {"name": name}
        if description:
            data["description"] = description
        return await self._request("POST", "/entity/expenseitem", json_data=data)

    async def create_cashout(self, data: Dict) -> Dict:
        """Naqd pul chiqimi / xarajat (Расходный кассовый ордер)"""
        return await self._request("POST", "/entity/cashout", json_data=data)

    async def create_paymentout(self, data: Dict) -> Dict:
        """Bank orqali chiqim / xarajat (Исходящий платеж)"""
        return await self._request("POST", "/entity/paymentout", json_data=data)

    async def get_cashouts(self, limit: int = 1000) -> list:
        """Barcha naqd chiqimlar (tezkor so'rov)"""
        resp = await self._request("GET", "/entity/cashout", params={"limit": limit})
        return resp.get("rows", [])

    async def get_paymentouts(self, limit: int = 1000) -> list:
        """Barcha bank chiqimlari (tezkor so'rov)"""
        resp = await self._request("GET", "/entity/paymentout", params={"limit": limit})
        return resp.get("rows", [])

    async def get_counterparty_metadata(self) -> Dict:
        """Kontragent metadata (states + groups)"""
        try:
            return await self._request("GET", "/entity/counterparty/metadata")
        except Exception as e:
            print(f"[Counterparty metadata error] {e}")
            return {"states": [], "groups": []}

    # ================= VALYUTA (CURRENCY) =================
    async def get_currency(self, currency_id: str) -> Dict:
        """Bitta valyuta ma'lumotlari"""
        return await self._request("GET", f"/entity/currency/{currency_id}")

    async def update_currency_rate(self, currency_id: str, rate: float) -> Dict:
        """MoySklad valyuta kursini yangilash"""
        res = await self._request("PUT", f"/entity/currency/{currency_id}", json_data={"rate": rate})
        self._currencies_cache["data"] = None
        self._currencies_cache["timestamp"] = 0
        return res


# Global instansiya
ms_client = MoySkladClient()