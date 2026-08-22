"""
Paytm Auto-Verifier Engine
Integrates Paytm Dashboard API for real-time automatic transaction verification
Matches by transaction_ref (QR), direct UTR search, and time-amount correlation
"""

import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable

import config
from database.db import Database

logger = logging.getLogger(__name__)


class PaytmDashboardAPI:
    """Client for Paytm Dashboard API to fetch and search transactions"""

    BASE_URL = "https://dashboard.paytm.com/api"

    def __init__(self):
        self.session_cookie: Optional[str] = None
        self.xsrf_token: Optional[str] = None
        self.ump_session: Optional[str] = None
        self.abck_cookie: Optional[str] = None
        self.ak_bmsc_cookie: Optional[str] = None
        self.bm_sz_cookie: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookies_valid = True

    def configure_from_config(self):
        """Load session credentials from config"""
        self.session_cookie = config.PAYTM_SESSION
        self.xsrf_token = config.PAYTM_XSRF_TOKEN
        self.ump_session = config.PAYTM_UMP_SESSION or config.PAYTM_SESSION
        self.abck_cookie = config.PAYTM_ABCK
        self.ak_bmsc_cookie = config.PAYTM_AK_BMSC
        self.bm_sz_cookie = config.PAYTM_BM_SZ
        self._cookies_valid = bool(self.session_cookie and self.xsrf_token)
        if self._cookies_valid:
            logger.info("PaytmDashboardAPI configured successfully from config")

    def configure(
        self,
        session: str,
        xsrf_token: str,
        ump_session: Optional[str] = None,
        abck: Optional[str] = None,
        ak_bmsc: Optional[str] = None,
        bm_sz: Optional[str] = None,
    ):
        """Set cookies dynamically"""
        self.session_cookie = session
        self.xsrf_token = xsrf_token
        self.ump_session = ump_session or session
        self.abck_cookie = abck
        self.ak_bmsc_cookie = ak_bmsc
        self.bm_sz_cookie = bm_sz
        self._cookies_valid = bool(session and xsrf_token)

    def is_configured(self) -> bool:
        return bool(self.session_cookie and self.xsrf_token)

    def _build_cookies(self) -> str:
        cookies = []
        if self.session_cookie:
            cookies.append(f"SESSION={self.session_cookie}")
        if self.xsrf_token:
            cookies.append(f"XSRF-TOKEN={self.xsrf_token}")
        if self.ump_session:
            cookies.append(f"UMP_SESSION={self.ump_session}")
        if self.bm_sz_cookie:
            cookies.append(f"bm_sz={self.bm_sz_cookie}")
        if self.ak_bmsc_cookie:
            cookies.append(f"ak_bmsc={self.ak_bmsc_cookie}")
        if self.abck_cookie:
            cookies.append(f"_abck={self.abck_cookie}")
        return "; ".join(cookies)

    def _build_headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "origin": "https://dashboard.paytm.com",
            "referer": "https://dashboard.paytm.com/next/transactions",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
            "x-xsrf-token": self.xsrf_token or "",
            "x-ump-version": "bpay-v2.26.2-12941-g34c41904c9",
            "cookie": self._build_cookies(),
        }

    def _handle_response_cookies(self, response: aiohttp.ClientResponse):
        """Auto-capture updated cookies from Paytm server and sync to config and .env"""
        try:
            cookies = response.cookies
            updated = {}
            if "SESSION" in cookies and cookies["SESSION"].value:
                self.session_cookie = cookies["SESSION"].value
                updated["PAYTM_SESSION"] = self.session_cookie
            if "XSRF-TOKEN" in cookies and cookies["XSRF-TOKEN"].value:
                self.xsrf_token = cookies["XSRF-TOKEN"].value
                updated["PAYTM_XSRF_TOKEN"] = self.xsrf_token
            if "UMP_SESSION" in cookies and cookies["UMP_SESSION"].value:
                self.ump_session = cookies["UMP_SESSION"].value
                updated["PAYTM_UMP_SESSION"] = self.ump_session
            if "_abck" in cookies and cookies["_abck"].value:
                self.abck_cookie = cookies["_abck"].value
                updated["PAYTM_ABCK"] = self.abck_cookie
            if "ak_bmsc" in cookies and cookies["ak_bmsc"].value:
                self.ak_bmsc_cookie = cookies["ak_bmsc"].value
                updated["PAYTM_AK_BMSC"] = self.ak_bmsc_cookie
            if "bm_sz" in cookies and cookies["bm_sz"].value:
                self.bm_sz_cookie = cookies["bm_sz"].value
                updated["PAYTM_BM_SZ"] = self.bm_sz_cookie

            if updated:
                from paytm_login import update_env_file
                update_env_file(updated)
                logger.debug(f"Auto-refreshed Paytm cookies: {list(updated.keys())}")
        except Exception as e:
            logger.debug(f"Error updating cookies from response: {e}")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def check_cookie_health(self) -> Dict[str, Any]:
        """Check if Paytm API cookies are valid and refresh session keepalive"""
        if not self.is_configured():
            return {"valid": False, "status": 0, "message": "Paytm cookies not configured"}

        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)

        payload = {
            "bizTypeList": ["ACQUIRING"],
            "pageSize": 1,
            "pageNum": 1,
            "orderCreatedStartTime": start_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "orderCreatedEndTime": end_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "isSort": True,
        }

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.BASE_URL}/v3/order/list",
                headers=self._build_headers(),
                json=payload,
                ssl=False,
            ) as response:
                self._handle_response_cookies(response)
                if response.status == 200:
                    self._cookies_valid = True
                    return {"valid": True, "status": 200, "message": "Cookies are ACTIVE & valid"}
                elif response.status == 401:
                    self._cookies_valid = False
                    return {"valid": False, "status": 401, "message": "Session EXPIRED (Need new SESSION cookie)"}
                elif response.status == 403:
                    self._cookies_valid = False
                    return {"valid": False, "status": 403, "message": "Access FORBIDDEN (Akamai / _abck expired)"}
                else:
                    return {"valid": False, "status": response.status, "message": f"API Error HTTP {response.status}"}
        except Exception as e:
            return {"valid": False, "status": 0, "message": f"Connection error: {str(e)}"}

    async def search_by_utr(self, utr: str) -> Dict[str, Any]:
        """Search Paytm transactions by UTR/Bank Reference Number"""
        if not self.is_configured():
            return {"error": "API not configured", "orders": []}

        now = datetime.now()
        start_time = now - timedelta(days=2)
        payload = {
            "bizTypeList": ["ACQUIRING", "CASHBACK", "SPLIT_PAYMENT"],
            "pageSize": 20,
            "pageNum": 1,
            "orderCreatedStartTime": start_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "orderCreatedEndTime": now.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "bankReferenceNo": utr.strip(),
            "isSort": True,
        }

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.BASE_URL}/v3/order/list",
                headers=self._build_headers(),
                json=payload,
                ssl=False,
            ) as response:
                self._handle_response_cookies(response)
                if response.status == 200:
                    data = await response.json()
                    orders = data.get("orderList", [])
                    return {"orders": orders}
                return {"error": f"API status {response.status}", "orders": []}
        except Exception as e:
            return {"error": str(e), "orders": []}

    async def search_by_transaction_ref(
        self, transaction_ref: str, amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """Search transaction by QR embedded transaction_ref"""
        if not self.is_configured():
            return {"found": False, "error": "API not configured"}

        payload = {
            "bizTypeList": ["ACQUIRING", "CASHBACK", "SPLIT_PAYMENT"],
            "pageSize": 20,
            "pageNum": 1,
            "merchantTransId": transaction_ref.strip(),
            "isSort": True,
        }

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.BASE_URL}/v3/order/list",
                headers=self._build_headers(),
                json=payload,
                ssl=False,
            ) as response:
                self._handle_response_cookies(response)
                if response.status == 200:
                    data = await response.json()
                    orders = data.get("orderList", [])

                    tr_upper = transaction_ref.strip().upper()
                    for txn in orders:
                        merchant_trans_id = (txn.get("merchantTransId") or "").upper()
                        comment = ((txn.get("additionalInfo") or {}).get("comment") or "").upper()

                        if tr_upper == merchant_trans_id or tr_upper in comment:
                            # Verify amount if passed
                            if amount is not None:
                                pay_amount = txn.get("payMoneyAmount", {})
                                if isinstance(pay_amount, dict):
                                    txn_amount = float(pay_amount.get("value", 0) or 0) / 100.0
                                else:
                                    txn_amount = float(txn.get("txnAmount", 0) or 0)
                                if abs(txn_amount - amount) > 0.01:
                                    continue

                            return {"found": True, "transaction": txn}

                    return {"found": False, "error": "Transaction not found"}
                return {"found": False, "error": f"API error {response.status}"}
        except Exception as e:
            return {"found": False, "error": str(e)}


paytm_api = PaytmDashboardAPI()


class PaytmAutoVerifier:
    """Background polling, keep-alive heartbeat, and verification coordinator"""

    def __init__(self, api: PaytmDashboardAPI, database: Database):
        self.api = api
        self.db = database
        self.is_running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._keepalive_task: Optional[asyncio.Task] = None
        self.on_order_verified: Optional[Callable] = None
        self.on_deposit_verified: Optional[Callable] = None

    async def start(self, interval: int = 15):
        """Start auto-verification polling and keep-alive tasks"""
        if self.is_running:
            return
        self.is_running = True
        self._poll_task = asyncio.create_task(self._run_loop(interval))
        self._keepalive_task = asyncio.create_task(self._run_keepalive_loop(interval=300))
        logger.info(f"PaytmAutoVerifier started with interval {interval}s and Keep-Alive Heartbeat (300s / 5min)")

    async def stop(self):
        """Stop background workers"""
        self.is_running = False
        for task in (self._poll_task, self._keepalive_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("PaytmAutoVerifier stopped")

    async def _run_keepalive_loop(self, interval: int = 300):
        """Periodic heartbeat (every 5-10 minutes) to keep Paytm session alive"""
        while self.is_running:
            try:
                await asyncio.sleep(interval)
                if self.api.is_configured():
                    health = await self.api.check_cookie_health()
                    if health.get("valid"):
                        logger.debug("💓 Paytm Session Heartbeat: Active & Refreshed")
                    else:
                        logger.warning(f"⚠️ Paytm Session Heartbeat Alert: {health.get('message')}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Keep-alive heartbeat error: {e}")

    async def _run_loop(self, interval: int):
        while self.is_running:
            try:
                if self.api.is_configured():
                    await self.check_pending_orders()
                    await self.check_pending_deposits()
            except Exception as e:
                logger.error(f"Error in Paytm verification loop: {e}", exc_info=True)
            await asyncio.sleep(interval)

    async def check_pending_orders(self):
        """Check all pending orders waiting for auto-verify or UTR verification"""
        orders = await self.db.get_pending_auto_verify_orders_async()
        if not orders:
            return

        for order in orders:
            order_id = order["id"]
            tr_ref = order.get("transaction_ref")
            utr = order.get("utr_number")
            amount = float(order.get("final_amount", 0))

            matched_txn = None

            # Strategy 1: Check by QR transaction reference
            if tr_ref:
                res = await self.api.search_by_transaction_ref(tr_ref, amount=amount)
                if res.get("found"):
                    matched_txn = res.get("transaction")

            # Strategy 2: Check by UTR if submitted
            if not matched_txn and utr and len(utr) >= 6:
                res = await self.api.search_by_utr(utr)
                for txn in res.get("orders", []):
                    txn_status = txn.get("orderStatus", "").upper()
                    if txn_status in ("SUCCESS", "COMPLETED", "TXN_SUCCESS"):
                        pay_amount = txn.get("payMoneyAmount", {})
                        if isinstance(pay_amount, dict):
                            txn_amount = float(pay_amount.get("value", 0) or 0) / 100.0
                        else:
                            txn_amount = float(txn.get("txnAmount", 0) or 0)

                        if abs(txn_amount - amount) <= 0.01:
                            matched_txn = txn
                            break

            if matched_txn:
                txn_id = matched_txn.get("bizOrderId") or matched_txn.get("orderId") or "UNKNOWN"
                # Check if transaction already used
                if await self.db.is_transaction_used_async(txn_id):
                    logger.warning(f"Paytm txn {txn_id} already used. Skipping order {order_id}.")
                    continue

                logger.info(f"✅ Verified Order #{order['order_code']} via Paytm Txn: {txn_id}")
                if self.on_order_verified:
                    try:
                        await self.on_order_verified(order, matched_txn)
                    except Exception as e:
                        logger.error(f"Error executing on_order_verified callback: {e}")

    async def check_pending_deposits(self):
        """Check pending wallet deposit requests"""
        deposits = await self.db.get_pending_wallet_deposits()
        if not deposits:
            return

        for dep in deposits:
            dep_id = dep["id"]
            tr_ref = dep.get("transaction_ref")
            amount = float(dep.get("amount", 0))

            if not tr_ref:
                continue

            res = await self.api.search_by_transaction_ref(tr_ref, amount=amount)
            if res.get("found"):
                matched_txn = res.get("transaction")
                txn_id = matched_txn.get("bizOrderId") or matched_txn.get("orderId") or "UNKNOWN"

                if await self.db.is_transaction_used_async(txn_id):
                    continue

                # Credit user balance & mark deposit complete
                success = await self.db.complete_wallet_deposit(
                    txn_id=dep_id,
                    utr_number=tr_ref,
                    paytm_txn_id=txn_id,
                )

                if success and self.on_deposit_verified:
                    try:
                        await self.on_deposit_verified(dep, matched_txn)
                    except Exception as e:
                        logger.error(f"Error executing on_deposit_verified callback: {e}")


def setup_auto_verifier(database: Database) -> PaytmAutoVerifier:
    paytm_api.configure_from_config()
    return PaytmAutoVerifier(paytm_api, database)
