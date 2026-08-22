"""
MongoDB Async Database Manager (Motor + MongoDB Atlas)
Provides full ACID compatibility, atomic concurrency locks, and schema parity with high-performance querying.
"""

import asyncio
import logging
import random
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
import certifi
from motor.motor_asyncio import AsyncIOMotorClient

import config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self._client: Optional[AsyncIOMotorClient] = None
        self._db = None
        self._lock = asyncio.Lock()

    async def init(self):
        """Initialize MongoDB Atlas Connection & Indexes"""
        uri = config.MONGO_URI
        if not uri:
            raise ValueError("MONGO_URI is not set in environment or config!")

        self._client = AsyncIOMotorClient(uri, tlsCAFile=certifi.where())
        self._db = self._client["storebot"]

        # Ping MongoDB server
        await self._client.admin.command("ping")
        logger.info("Connected to MongoDB Atlas successfully!")

        # Create necessary unique & lookup indexes
        await self._db.users.create_index("user_id", unique=True)
        await self._db.categories.create_index("id", unique=True)
        await self._db.products.create_index("id", unique=True)
        await self._db.products.create_index("category_id")
        await self._db.stock_items.create_index("id", unique=True)
        await self._db.stock_items.create_index([("product_id", 1), ("is_used", 1)])
        await self._db.orders.create_index("id", unique=True)
        await self._db.orders.create_index("order_code", unique=True)
        await self._db.orders.create_index("transaction_ref")
        await self._db.orders.create_index("user_id")
        await self._db.orders.create_index("status")
        await self._db.wallet_transactions.create_index("id", unique=True)
        await self._db.wallet_transactions.create_index("transaction_ref")
        await self._db.wallet_transactions.create_index("user_id")
        await self._db.wallet_transactions.create_index("status")
        await self._db.used_transactions.create_index("txn_id", unique=True)
        await self._db.coupons.create_index("id", unique=True)
        await self._db.coupons.create_index("code", unique=True)
        await self._db.settings.create_index("key", unique=True)
        await self._db.verified_devices.create_index("device_hash", unique=True)
        await self._db.verified_devices.create_index("user_id", unique=True)
        await self._db.verification_sessions.create_index("bot_hash", unique=True)
        await self._db.referral_rewards.create_index("id", unique=True)
        await self._db.referral_redemptions.create_index("id", unique=True)
        await self._db.referral_redemptions.create_index("user_id")

        # Ensure default category exists
        default_cat = await self._db.categories.find_one({"id": 1})
        if not default_cat:
            await self._db.categories.insert_one({
                "id": 1,
                "name": "General",
                "description": "Default category",
                "order_index": 0,
                "is_active": 1,
            })

    async def close(self):
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None

    async def _get_next_sequence(self, name: str) -> int:
        """Atomic integer counter for auto-increment ID generation"""
        res = await self._db.counters.find_one_and_update(
            {"_id": name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True,
        )
        return int(res["seq"])

    @staticmethod
    def _clean_doc(doc: Optional[dict]) -> Optional[dict]:
        """Remove internal MongoDB _id from returned dicts for transparency"""
        if doc is None:
            return None
        d = dict(doc)
        d.pop("_id", None)
        return d

    # ==========================================
    # USER OPERATIONS
    # ==========================================

    async def get_or_create_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        referrer_id: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], bool]:
        """Fetch user or create new profile with optional referral tracking"""
        user = await self._db.users.find_one({"user_id": user_id})
        if user:
            # Update username / name if changed
            updates = {}
            if username and user.get("username") != username:
                updates["username"] = username
            if full_name and user.get("full_name") != full_name:
                updates["full_name"] = full_name
            if updates:
                await self._db.users.update_one({"user_id": user_id}, {"$set": updates})
                user.update(updates)
            return self._clean_doc(user), False

        # Validate referrer (cannot refer oneself)
        valid_referrer = None
        if referrer_id and referrer_id != user_id:
            ref_user = await self._db.users.find_one({"user_id": referrer_id})
            if ref_user:
                valid_referrer = referrer_id

        new_user = {
            "user_id": user_id,
            "username": username or "",
            "full_name": full_name or "",
            "balance": 0.0,
            "total_spent": 0.0,
            "referrer_id": valid_referrer,
            "referral_earnings": 0.0,
            "is_banned": 0,
            "created_at": datetime.now().isoformat(),
        }
        await self._db.users.insert_one(new_user)
        return self._clean_doc(new_user), True

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch single user document"""
        user = await self._db.users.find_one({"user_id": user_id})
        return self._clean_doc(user)

    async def update_user_balance(self, user_id: int, delta: float) -> bool:
        """Atomically adjust user balance (+ for deposit/reward, - for purchase)"""
        async with self._lock:
            if delta < 0:
                # Check sufficient funds
                user = await self._db.users.find_one({"user_id": user_id})
                if not user or user.get("balance", 0.0) + delta < -0.001:
                    return False
            res = await self._db.users.update_one(
                {"user_id": user_id},
                {"$inc": {"balance": delta}},
            )
            return res.modified_count > 0

    async def add_user_total_spent(self, user_id: int, amount: float):
        """Increment user lifetime spent amount"""
        await self._db.users.update_one(
            {"user_id": user_id},
            {"$inc": {"total_spent": amount}},
        )

    async def toggle_user_ban(self, user_id: int) -> bool:
        """Toggle banned status for user"""
        user = await self._db.users.find_one({"user_id": user_id})
        if not user:
            return False
        new_val = 0 if user.get("is_banned") else 1
        await self._db.users.update_one({"user_id": user_id}, {"$set": {"is_banned": new_val}})
        return bool(new_val)

    async def get_total_users_count(self) -> int:
        """Total registered user count"""
        return await self._db.users.count_documents({})

    async def get_all_users(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent users for admin"""
        cursor = self._db.users.find().sort("created_at", -1).limit(limit)
        return [self._clean_doc(doc) async for doc in cursor]

    async def get_all_user_ids(self) -> List[int]:
        """Fetch all non-banned user IDs for full broadcast"""
        cursor = self._db.users.find({"is_banned": 0}, {"user_id": 1})
        return [doc["user_id"] async for doc in cursor]

    async def search_users(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search users by ID, username, or name"""
        q = query.strip()
        conditions = []
        if q.isdigit():
            conditions.append({"user_id": int(q)})
        conditions.append({"username": {"$regex": q, "$options": "i"}})
        conditions.append({"full_name": {"$regex": q, "$options": "i"}})

        cursor = self._db.users.find({"$or": conditions}).limit(limit)
        return [self._clean_doc(doc) async for doc in cursor]

    # ==========================================
    # CATEGORIES
    # ==========================================

    async def get_categories(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Fetch categories"""
        query = {"is_active": 1} if active_only else {}
        cursor = self._db.categories.find(query).sort("order_index", 1)
        cats = [self._clean_doc(doc) async for doc in cursor]
        for c in cats:
            c["product_count"] = await self._db.products.count_documents(
                {"category_id": c["id"], "is_active": 1} if active_only else {"category_id": c["id"]}
            )
        return cats

    async def get_category(self, category_id: int) -> Optional[Dict[str, Any]]:
        """Fetch category by ID"""
        cat = await self._db.categories.find_one({"id": category_id})
        return self._clean_doc(cat)

    async def add_category(self, name: str, description: str = "", order_index: int = 0) -> int:
        """Create category"""
        cid = await self._get_next_sequence("category_id")
        doc = {
            "id": cid,
            "name": name.strip(),
            "description": description.strip(),
            "order_index": order_index,
            "is_active": 1,
        }
        await self._db.categories.insert_one(doc)
        return cid

    async def update_category(self, category_id: int, name: str, description: str = ""):
        """Update category"""
        await self._db.categories.update_one(
            {"id": category_id},
            {"$set": {"name": name.strip(), "description": description.strip()}},
        )

    async def delete_category(self, category_id: int):
        """Delete category and associated products"""
        await self._db.categories.delete_one({"id": category_id})
        prods = await self._db.products.find({"category_id": category_id}).to_list(1000)
        prod_ids = [p["id"] for p in prods]
        if prod_ids:
            await self._db.products.delete_many({"category_id": category_id})
            await self._db.stock_items.delete_many({"product_id": {"$in": prod_ids}})

    # ==========================================
    # PRODUCTS
    # ==========================================

    async def get_products_by_category(self, category_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all products in category with live stock counts"""
        query = {"category_id": category_id}
        if active_only:
            query["is_active"] = 1
        cursor = self._db.products.find(query).sort("id", 1)
        prods = [self._clean_doc(doc) async for doc in cursor]
        for p in prods:
            p["stock_count"] = await self._db.stock_items.count_documents(
                {"product_id": p["id"], "is_used": 0}
            )
        return prods

    async def get_all_products(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all products with stock counts"""
        query = {"is_active": 1} if active_only else {}
        cursor = self._db.products.find(query).sort("id", 1)
        prods = [self._clean_doc(doc) async for doc in cursor]
        for p in prods:
            p["stock_count"] = await self._db.stock_items.count_documents(
                {"product_id": p["id"], "is_used": 0}
            )
        return prods

    async def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get single product with stock count"""
        p = await self._db.products.find_one({"id": product_id})
        if not p:
            return None
        doc = self._clean_doc(p)
        doc["stock_count"] = await self._db.stock_items.count_documents(
            {"product_id": product_id, "is_used": 0}
        )
        cat = await self._db.categories.find_one({"id": doc.get("category_id", 1)})
        doc["category_name"] = cat["name"] if cat else "General"
        return doc

    async def add_product(
        self,
        name: str,
        price: float,
        description: str = "",
        category_id: int = 1,
        delivery_type: str = "line_stock",
        image_file_id: Optional[str] = None,
        file_id: Optional[str] = None,
        static_content: Optional[str] = None,
    ) -> int:
        """Create new product"""
        pid = await self._get_next_sequence("product_id")
        doc = {
            "id": pid,
            "category_id": category_id,
            "name": name.strip(),
            "description": description.strip(),
            "price": float(price),
            "delivery_type": delivery_type,
            "image_file_id": image_file_id,
            "file_id": file_id,
            "static_content": static_content,
            "is_active": 1,
            "created_at": datetime.now().isoformat(),
        }
        await self._db.products.insert_one(doc)
        return pid

    async def update_product(self, product_id: int, **kwargs):
        """Update fields of product"""
        if kwargs:
            await self._db.products.update_one({"id": product_id}, {"$set": kwargs})

    async def delete_product(self, product_id: int):
        """Delete product and its stock"""
        await self._db.products.delete_one({"id": product_id})
        await self._db.stock_items.delete_many({"product_id": product_id})

    async def adjust_product_price(self, product_id: int, delta: float) -> float:
        """Increase or decrease product price (min ₹1.0)"""
        product = await self.get_product(product_id)
        if not product:
            return 0.0
        new_price = max(1.0, float(product.get("price", 10.0)) + delta)
        await self._db.products.update_one({"id": product_id}, {"$set": {"price": new_price}})
        return new_price

    async def toggle_product_status(self, product_id: int) -> bool:
        """Toggle is_active status"""
        product = await self.get_product(product_id)
        if not product:
            return False
        new_val = 0 if product.get("is_active", 1) else 1
        await self._db.products.update_one({"id": product_id}, {"$set": {"is_active": new_val}})
        return bool(new_val)

    # ==========================================
    # STOCK ITEMS (DIGITAL GOODS / KEYS / FILES / ACCOUNTS)
    # ==========================================

    async def add_stock_item(
        self, product_id: int, content: str, file_id: Optional[str] = None, file_name: Optional[str] = None
    ) -> int:
        """Add single stock item (key/account/link or file)"""
        sid = await self._get_next_sequence("stock_id")
        doc = {
            "id": sid,
            "product_id": product_id,
            "content": content.strip(),
            "file_id": file_id,
            "file_name": file_name,
            "is_used": 0,
            "order_id": None,
            "added_at": datetime.now().isoformat(),
            "used_at": None,
        }
        await self._db.stock_items.insert_one(doc)
        return sid

    async def add_stock_file(self, product_id: int, file_id: str, file_name: Optional[str] = None) -> int:
        """Add single file as stock item"""
        return await self.add_stock_item(
            product_id=product_id,
            content=file_name or "Stock File",
            file_id=file_id,
            file_name=file_name or "stock_file.txt",
        )

    async def add_bulk_stock(self, product_id: int, content_list: List[str]) -> int:
        """Add multiple text line stock items at once"""
        clean_lines = [c.strip() for c in content_list if c.strip()]
        if not clean_lines:
            return 0
        docs = []
        for line in clean_lines:
            sid = await self._get_next_sequence("stock_id")
            docs.append({
                "id": sid,
                "product_id": product_id,
                "content": line,
                "file_id": None,
                "file_name": None,
                "is_used": 0,
                "order_id": None,
                "added_at": datetime.now().isoformat(),
                "used_at": None,
            })
        await self._db.stock_items.insert_many(docs)
        return len(docs)

    async def get_stock_count(self, product_id: int) -> int:
        """Get available unsent stock items count"""
        return await self._db.stock_items.count_documents({"product_id": product_id, "is_used": 0})

    async def claim_stock_items(self, product_id: int, quantity: int, order_id: int) -> List[Dict[str, Any]]:
        """
        Atomically mark stock items as used for an order and return item dict list.
        """
        async with self._lock:
            cursor = self._db.stock_items.find(
                {"product_id": product_id, "is_used": 0}
            ).sort("id", 1).limit(quantity)
            rows = [self._clean_doc(doc) async for doc in cursor]

            if len(rows) < quantity:
                return []

            claimed_ids = [r["id"] for r in rows]
            now_str = datetime.now().isoformat()
            await self._db.stock_items.update_many(
                {"id": {"$in": claimed_ids}},
                {"$set": {"is_used": 1, "order_id": order_id, "used_at": now_str}},
            )
            return rows

    async def get_available_stock_items(self, product_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get unused stock items list for admin viewing"""
        cursor = self._db.stock_items.find(
            {"product_id": product_id, "is_used": 0}
        ).sort("id", 1).limit(limit)
        return [self._clean_doc(doc) async for doc in cursor]

    async def delete_stock_item(self, stock_id: int):
        """Delete unused stock item"""
        await self._db.stock_items.delete_one({"id": stock_id})

    async def clear_unused_stock(self, product_id: int) -> int:
        """Clear all unused stock items for product"""
        res = await self._db.stock_items.delete_many({"product_id": product_id, "is_used": 0})
        return res.deleted_count

    async def get_unallocated_stock_raw(self, product_id: int) -> List[str]:
        """Fetch all unused stock lines for file export"""
        cursor = self._db.stock_items.find(
            {"product_id": product_id, "is_used": 0}
        ).sort("id", 1)
        return [doc.get("content", "") async for doc in cursor]

    async def get_sold_stock_history(self, product_id: int, limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch recent sold stock items with order details"""
        cursor = self._db.stock_items.find(
            {"product_id": product_id, "is_used": 1}
        ).sort("used_at", -1).limit(limit)
        sold_items = [self._clean_doc(doc) async for doc in cursor]
        for itm in sold_items:
            if itm.get("order_id"):
                ord_doc = await self._db.orders.find_one({"id": itm["order_id"]})
                if ord_doc:
                    itm["order_code"] = ord_doc.get("order_code", "N/A")
                    itm["user_id"] = ord_doc.get("user_id")
        return sold_items

    # ==========================================
    # ORDERS
    # ==========================================

    async def create_order(
        self,
        user_id: int,
        product_id: int,
        product_name: str,
        quantity: int,
        unit_price: float,
        final_amount: float,
        payment_method: str,
        discount_amount: float = 0.0,
        transaction_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create new pending order"""
        oid = await self._get_next_sequence("order_id")
        order_code = f"ORD-{random.randint(10000, 99999)}"
        now_str = datetime.now().isoformat()

        doc = {
            "id": oid,
            "order_code": order_code,
            "user_id": user_id,
            "product_id": product_id,
            "product_name": product_name,
            "quantity": quantity,
            "unit_price": float(unit_price),
            "discount_amount": float(discount_amount),
            "final_amount": float(final_amount),
            "payment_method": payment_method,
            "status": "pending",
            "transaction_ref": transaction_ref,
            "utr_number": None,
            "delivered_content": None,
            "created_at": now_str,
        }
        await self._db.orders.insert_one(doc)
        return self._clean_doc(doc)

    async def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Fetch single order by integer ID"""
        doc = await self._db.orders.find_one({"id": order_id})
        return self._clean_doc(doc)

    async def get_order_by_code(self, order_code: str) -> Optional[Dict[str, Any]]:
        """Fetch single order by code e.g. ORD-12345"""
        doc = await self._db.orders.find_one({"order_code": order_code.strip().upper()})
        return self._clean_doc(doc)

    async def get_order_by_ref(self, transaction_ref: str) -> Optional[Dict[str, Any]]:
        """Fetch order by transaction ref"""
        doc = await self._db.orders.find_one({"transaction_ref": transaction_ref.strip()})
        return self._clean_doc(doc)

    async def update_order_status(self, order_id: int, status: str, delivered_content: Optional[str] = None):
        """Update status of order"""
        updates = {"status": status}
        if delivered_content is not None:
            updates["delivered_content"] = delivered_content
        await self._db.orders.update_one({"id": order_id}, {"$set": updates})

    async def update_order_utr(self, order_id: int, utr_number: str):
        """Update submitted UTR for order"""
        await self._db.orders.update_one({"id": order_id}, {"$set": {"utr_number": utr_number.strip()}})

    async def update_order_discount(self, order_id: int, discount_amount: float, final_amount: float):
        """Update order discount and final payable total"""
        await self._db.orders.update_one(
            {"id": order_id},
            {"$set": {"discount_amount": float(discount_amount), "final_amount": float(final_amount)}},
        )

    async def get_pending_auto_verify_orders_async(self) -> List[Dict[str, Any]]:
        """Fetch pending orders created in last 24 hours that have a transaction ref"""
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        cursor = self._db.orders.find({
            "status": "pending",
            "transaction_ref": {"$ne": None},
            "created_at": {"$gte": cutoff},
        })
        return [self._clean_doc(doc) async for doc in cursor]

    async def get_user_orders(self, user_id: int, limit: int = 15) -> List[Dict[str, Any]]:
        """Fetch user past orders"""
        cursor = self._db.orders.find({"user_id": user_id}).sort("id", -1).limit(limit)
        return [self._clean_doc(doc) async for doc in cursor]

    async def get_all_orders(self, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all orders for admin"""
        query = {"status": status} if status else {}
        cursor = self._db.orders.find(query).sort("id", -1).limit(limit)
        return [self._clean_doc(doc) async for doc in cursor]

    # ==========================================
    # WALLET TRANSACTIONS & TOP-UPS
    # ==========================================

    async def create_wallet_transaction(
        self,
        user_id: int,
        amount: float,
        txn_type: str,
        description: str = "",
        transaction_ref: Optional[str] = None,
        status: str = "pending",
    ) -> Dict[str, Any]:
        """Create new wallet deposit or deduction transaction"""
        tid = await self._get_next_sequence("wallet_txn_id")
        doc = {
            "id": tid,
            "user_id": user_id,
            "amount": float(amount),
            "type": txn_type,
            "status": status,
            "transaction_ref": transaction_ref,
            "utr_number": None,
            "description": description,
            "created_at": datetime.now().isoformat(),
        }
        await self._db.wallet_transactions.insert_one(doc)
        return self._clean_doc(doc)

    async def get_wallet_transaction(self, txn_id: int) -> Optional[Dict[str, Any]]:
        """Get wallet transaction by ID"""
        doc = await self._db.wallet_transactions.find_one({"id": txn_id})
        return self._clean_doc(doc)

    async def get_wallet_transaction_by_ref(self, transaction_ref: str) -> Optional[Dict[str, Any]]:
        """Get wallet transaction by reference"""
        doc = await self._db.wallet_transactions.find_one({"transaction_ref": transaction_ref.strip()})
        return self._clean_doc(doc)

    async def get_pending_wallet_deposits(self) -> List[Dict[str, Any]]:
        """Fetch pending wallet top-up transactions created in last 24h"""
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        cursor = self._db.wallet_transactions.find({
            "status": "pending",
            "type": "deposit",
            "transaction_ref": {"$ne": None},
            "created_at": {"$gte": cutoff},
        })
        return [self._clean_doc(doc) async for doc in cursor]

    async def complete_wallet_deposit(
        self,
        txn_id: int,
        utr_number: Optional[str] = None,
        paytm_txn_id: Optional[str] = None,
    ) -> bool:
        """Atomically credit user balance and complete deposit (Anti-Double Spend Safe)"""
        async with self._lock:
            doc = await self._db.wallet_transactions.find_one({"id": txn_id})
            if not doc or doc.get("status") == "completed":
                return False

            user_id = doc["user_id"]
            amount = float(doc["amount"])

            # Credit user balance
            await self._db.users.update_one(
                {"user_id": user_id},
                {"$inc": {"balance": amount}},
            )

            # Mark wallet txn completed
            await self._db.wallet_transactions.update_one(
                {"id": txn_id},
                {"$set": {"status": "completed", "utr_number": utr_number}},
            )

            # Record used Paytm transaction
            if paytm_txn_id:
                await self.mark_transaction_used_async(
                    txn_id=paytm_txn_id,
                    wallet_txn_id=txn_id,
                    amount=amount,
                )
            return True

    async def get_user_wallet_history(self, user_id: int, limit: int = 15) -> List[Dict[str, Any]]:
        """Get past wallet ledger for user"""
        cursor = self._db.wallet_transactions.find({"user_id": user_id}).sort("id", -1).limit(limit)
        return [self._clean_doc(doc) async for doc in cursor]

    # ==========================================
    # USED TRANSACTIONS (ANTI DOUBLE-SPEND)
    # ==========================================

    async def is_transaction_used_async(self, txn_id: str) -> bool:
        """Check if Paytm transaction ID has already been credited"""
        if not txn_id:
            return False
        doc = await self._db.used_transactions.find_one({"txn_id": str(txn_id).strip()})
        return doc is not None

    def is_transaction_used(self, txn_id: str) -> bool:
        """Sync helper for legacy checks"""
        return False

    async def mark_transaction_used_async(
        self, txn_id: str, order_id: Optional[int] = None, wallet_txn_id: Optional[int] = None, amount: float = 0.0
    ):
        """Mark Paytm transaction ID as permanently redeemed"""
        async with self._lock:
            await self._db.used_transactions.update_one(
                {"txn_id": str(txn_id).strip()},
                {
                    "$set": {
                        "txn_id": str(txn_id).strip(),
                        "order_id": order_id,
                        "wallet_txn_id": wallet_txn_id,
                        "amount": amount,
                        "used_at": datetime.now().isoformat(),
                    }
                },
                upsert=True,
            )

    # ==========================================
    # COUPONS / PROMO CODES
    # ==========================================

    async def get_coupon(self, code: str) -> Optional[Dict[str, Any]]:
        """Find active promo code"""
        doc = await self._db.coupons.find_one({"code": code.strip().upper(), "is_active": 1})
        return self._clean_doc(doc)

    async def create_coupon(
        self,
        code: str,
        discount_type: str,
        discount_value: float,
        min_purchase: float = 0.0,
        max_uses: int = 0,
        expires_at: Optional[str] = None,
    ) -> int:
        """Create new discount coupon"""
        cid = await self._get_next_sequence("coupon_id")
        doc = {
            "id": cid,
            "code": code.strip().upper(),
            "discount_type": discount_type,
            "discount_value": float(discount_value),
            "min_purchase": float(min_purchase),
            "max_uses": int(max_uses),
            "used_count": 0,
            "is_active": 1,
            "expires_at": expires_at,
            "created_at": datetime.now().isoformat(),
        }
        await self._db.coupons.insert_one(doc)
        return cid

    async def use_coupon(self, coupon_id: int, user_id: int, order_id: int):
        """Record coupon usage"""
        await self._db.coupons.update_one({"id": coupon_id}, {"$inc": {"used_count": 1}})
        await self._db.coupon_usages.insert_one({
            "coupon_id": coupon_id,
            "user_id": user_id,
            "order_id": order_id,
            "used_at": datetime.now().isoformat(),
        })

    async def get_all_coupons(self) -> List[Dict[str, Any]]:
        """Get all coupons for admin"""
        cursor = self._db.coupons.find().sort("id", -1)
        return [self._clean_doc(doc) async for doc in cursor]

    async def delete_coupon(self, coupon_id: int):
        """Delete coupon"""
        await self._db.coupons.delete_one({"id": coupon_id})

    # ==========================================
    # ANALYTICS & DASHBOARD STATS
    # ==========================================

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """Fetch real-time store statistics"""
        total_users = await self._db.users.count_documents({})
        total_orders = await self._db.orders.count_documents({"status": {"$in": ["paid", "delivered"]}})
        pending_orders = await self._db.orders.count_documents({"status": "pending"})
        active_products = await self._db.products.count_documents({"is_active": 1})

        # Calculate revenue
        rev_pipeline = [
            {"$match": {"status": {"$in": ["paid", "delivered"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$final_amount"}}},
        ]
        rev_res = await self._db.orders.aggregate(rev_pipeline).to_list(1)
        total_revenue = rev_res[0]["total"] if rev_res else 0.0

        # Out of stock count
        all_prods = await self.get_all_products(active_only=True)
        out_of_stock = sum(
            1 for p in all_prods
            if p.get("delivery_type") in ("line_stock", "file_stock", "stock") and p.get("stock_count", 0) == 0
        )

        return {
            "total_users": total_users,
            "total_orders": total_orders,
            "total_revenue": float(total_revenue),
            "pending_orders": pending_orders,
            "active_products": active_products,
            "out_of_stock_products": out_of_stock,
        }

    async def get_advanced_analytics(self) -> Dict[str, Any]:
        """Get detailed breakdown of today, yesterday, and top selling products"""
        today_str = date.today().isoformat()
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        month_prefix = date.today().strftime("%Y-%m")

        # Today
        today_pipe = [
            {"$match": {"status": {"$in": ["paid", "delivered"]}, "created_at": {"$regex": f"^{today_str}"}}},
            {"$group": {"_id": None, "orders": {"$sum": 1}, "revenue": {"$sum": "$final_amount"}}},
        ]
        t_res = await self._db.orders.aggregate(today_pipe).to_list(1)
        today_orders = t_res[0]["orders"] if t_res else 0
        today_revenue = t_res[0]["revenue"] if t_res else 0.0

        # Yesterday
        y_pipe = [
            {"$match": {"status": {"$in": ["paid", "delivered"]}, "created_at": {"$regex": f"^{yesterday_str}"}}},
            {"$group": {"_id": None, "orders": {"$sum": 1}, "revenue": {"$sum": "$final_amount"}}},
        ]
        y_res = await self._db.orders.aggregate(y_pipe).to_list(1)
        yesterday_orders = y_res[0]["orders"] if y_res else 0
        yesterday_revenue = y_res[0]["revenue"] if y_res else 0.0

        # This Month
        m_pipe = [
            {"$match": {"status": {"$in": ["paid", "delivered"]}, "created_at": {"$regex": f"^{month_prefix}"}}},
            {"$group": {"_id": None, "orders": {"$sum": 1}, "revenue": {"$sum": "$final_amount"}}},
        ]
        m_res = await self._db.orders.aggregate(m_pipe).to_list(1)
        month_orders = m_res[0]["orders"] if m_res else 0
        month_revenue = m_res[0]["revenue"] if m_res else 0.0

        # Top 5 Best Selling Products
        top_pipe = [
            {"$match": {"status": {"$in": ["paid", "delivered"]}}},
            {"$group": {"_id": "$product_name", "units_sold": {"$sum": 1}, "total_revenue": {"$sum": "$final_amount"}}},
            {"$sort": {"units_sold": -1}},
            {"$limit": 5},
        ]
        top_res = await self._db.orders.aggregate(top_pipe).to_list(5)
        top_products = [{"product_name": r["_id"], "units_sold": r["units_sold"], "total_revenue": r["total_revenue"]} for r in top_res]

        stats = await self.get_dashboard_stats()
        stats.update({
            "today_orders": today_orders,
            "today_revenue": float(today_revenue),
            "yesterday_orders": yesterday_orders,
            "yesterday_revenue": float(yesterday_revenue),
            "month_orders": month_orders,
            "month_revenue": float(month_revenue),
            "top_products": top_products,
        })
        return stats

    # ==========================================
    # SETTINGS
    # ==========================================

    async def get_setting(self, key: str, default: str = "") -> str:
        """Get setting by key"""
        doc = await self._db.settings.find_one({"key": key})
        return doc["value"] if doc else default

    async def set_setting(self, key: str, value: str):
        """Set setting by key"""
        await self._db.settings.update_one(
            {"key": key},
            {"$set": {"key": key, "value": value}},
            upsert=True,
        )


    # ==========================================
    # DEVICE VERIFICATION & ANTI-FRAUD REFERRALS
    # ==========================================

    async def get_referral_settings(self) -> Dict[str, Any]:
        """Fetch referral program settings"""
        return {
            "join_enabled": (await self.get_setting("ref_join_enabled", "1")) == "1",
            "join_amount": float(await self.get_setting("ref_join_amount", "5.0")),
            "purchase_enabled": (await self.get_setting("ref_purch_enabled", "1")) == "1",
            "purchase_percent": float(await self.get_setting("ref_purch_percent", "5.0")),
            "channel": await self.get_setting("ref_channel", config.CHANNEL_USERNAME),
        }

    async def is_user_device_verified(self, user_id: int) -> bool:
        """Check if user has passed single device/IP verification"""
        user = await self.get_user(user_id)
        return bool(user and user.get("is_device_verified", 0) == 1)

    async def create_verification_session(self, user_id: int, bot_hash: str):
        """Create or update temporary verification hash session"""
        await self._db.verification_sessions.update_one(
            {"bot_hash": bot_hash},
            {"$set": {"user_id": user_id, "bot_hash": bot_hash, "created_at": datetime.now().isoformat()}},
            upsert=True,
        )

    async def get_verification_session(self, bot_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve verification session by bot_hash"""
        doc = await self._db.verification_sessions.find_one({"bot_hash": bot_hash})
        return self._clean_doc(doc)

    async def verify_user_device(
        self, user_id: int, device_hash: str, ip_address: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Verify user device. Strictly enforces 1 Device / 1 IP = 1 Account.
        Returns (success: bool, status_code: str)
        """
        async with self._lock:
            # Check if this user is already verified
            user = await self._db.users.find_one({"user_id": user_id})
            if user and user.get("is_device_verified") == 1:
                return True, "already_verified"

            clean_hash = str(device_hash).strip()
            # Check if device_hash is already linked to another user
            existing_device = await self._db.verified_devices.find_one({"device_hash": clean_hash})
            if existing_device and existing_device["user_id"] != user_id:
                return False, "duplicate_device"

            # Check if IP is already verified
            if ip_address:
                clean_ip = str(ip_address).strip()
                existing_ip = await self._db.verified_devices.find_one({"ip_address": clean_ip})
                if existing_ip and existing_ip["user_id"] != user_id:
                    return False, "duplicate_ip"

            # Register verified device
            now_str = datetime.now().isoformat()
            await self._db.verified_devices.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "device_hash": clean_hash,
                        "ip_address": ip_address,
                        "verified_at": now_str,
                    }
                },
                upsert=True,
            )

            # Update user record
            await self._db.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_device_verified": 1,
                        "device_hash": clean_hash,
                        "ip_address": ip_address,
                        "device_verified_at": now_str,
                    }
                },
            )
            return True, "success"

    async def get_user_referral_stats(self, user_id: int) -> Dict[str, Any]:
        """Fetch user referral counts and points"""
        total_referrals = await self._db.users.count_documents({"referrer_id": user_id})
        verified_referrals = await self._db.users.count_documents(
            {"referrer_id": user_id, "is_device_verified": 1}
        )
        user = await self.get_user(user_id) or {}
        points = int(user.get("referral_points", 0))
        is_verified = bool(user.get("is_device_verified", 0) == 1)

        return {
            "total_referrals": total_referrals,
            "verified_referrals": verified_referrals,
            "points": points,
            "is_device_verified": is_verified,
        }

    async def process_referral_rewards_on_verification(self, user_id: int) -> Dict[str, Any]:
        """
        Awards 1 Referral Point to referrer when invited friend verifies device.
        Points are exclusively used to redeem items in the Referral Reward Shop.
        """
        async with self._lock:
            user = await self._db.users.find_one({"user_id": user_id})
            if not user:
                return {"success": False, "reason": "user_not_found"}

            if user.get("referral_reward_processed") == 1:
                return {"success": False, "reason": "already_processed"}

            referrer_id = user.get("referrer_id")
            points_awarded = 0
            if referrer_id:
                points_awarded = 1
                # Increment referrer points by 1
                await self._db.users.update_one(
                    {"user_id": referrer_id},
                    {"$inc": {"referral_points": 1}},
                )

            # Mark reward as processed
            await self._db.users.update_one(
                {"user_id": user_id},
                {"$set": {"referral_reward_processed": 1}},
            )

            ref_user = await self.get_user(referrer_id) if referrer_id else None
            new_points = int(ref_user.get("referral_points", 0)) if ref_user else 0

            return {
                "success": True,
                "referrer_id": referrer_id,
                "points_awarded": points_awarded,
                "new_points_balance": new_points,
            }

    # ==========================================
    # REFERRAL REWARDS SHOP (REDEEM POINTS)
    # ==========================================

    async def get_all_referral_rewards(self, only_active: bool = True) -> List[Dict[str, Any]]:
        """List all rewards available for points redemption"""
        query = {"is_active": 1} if only_active else {}
        cursor = self._db.referral_rewards.find(query).sort("points_cost", 1)
        return [self._clean_doc(d) async for d in cursor]

    async def get_referral_reward(self, reward_id: int) -> Optional[Dict[str, Any]]:
        """Get single referral reward item"""
        doc = await self._db.referral_rewards.find_one({"id": reward_id})
        return self._clean_doc(doc)

    async def create_referral_reward(
        self,
        name: str,
        description: str,
        points_cost: int,
        delivery_type: str = "text",
        content: str = "",
        file_id: Optional[str] = None,
    ) -> int:
        """Create new redeemable reward item"""
        reward_id = await self._get_next_sequence("referral_reward_id")
        reward_doc = {
            "id": reward_id,
            "name": name.strip(),
            "description": description.strip(),
            "points_cost": int(points_cost),
            "delivery_type": delivery_type,
            "content": content.strip() if content else "",
            "file_id": file_id,
            "is_active": 1,
            "redeemed_count": 0,
            "created_at": datetime.now().isoformat(),
        }
        await self._db.referral_rewards.insert_one(reward_doc)
        return reward_id

    async def delete_referral_reward(self, reward_id: int) -> bool:
        """Delete a referral reward"""
        res = await self._db.referral_rewards.delete_one({"id": reward_id})
        return res.deleted_count > 0

    async def toggle_referral_reward(self, reward_id: int) -> bool:
        """Toggle active status of reward"""
        reward = await self._db.referral_rewards.find_one({"id": reward_id})
        if not reward:
            return False
        new_status = 0 if reward.get("is_active", 1) == 1 else 1
        await self._db.referral_rewards.update_one({"id": reward_id}, {"$set": {"is_active": new_status}})
        return bool(new_status == 1)

    async def redeem_referral_reward(
        self, user_id: int, reward_id: int
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Redeem a reward using referral points.
        Atomically checks balance, deducts points, and logs redemption.
        """
        async with self._lock:
            reward = await self._db.referral_rewards.find_one({"id": reward_id, "is_active": 1})
            if not reward:
                return False, "reward_not_found", None

            points_cost = int(reward.get("points_cost", 1))
            user = await self._db.users.find_one({"user_id": user_id})
            if not user:
                return False, "user_not_found", None

            user_points = int(user.get("referral_points", 0))
            if user_points < points_cost:
                return False, "not_enough_points", None

            # Deduct points from user
            await self._db.users.update_one(
                {"user_id": user_id},
                {"$inc": {"referral_points": -points_cost}},
            )

            # Increment reward redemption count
            await self._db.referral_rewards.update_one(
                {"id": reward_id},
                {"$inc": {"redeemed_count": 1}},
            )

            # Record redemption
            redemption_id = await self._get_next_sequence("referral_redemption_id")
            redemption_doc = {
                "id": redemption_id,
                "user_id": user_id,
                "reward_id": reward_id,
                "reward_name": reward["name"],
                "points_spent": points_cost,
                "delivery_type": reward.get("delivery_type", "text"),
                "delivered_content": reward.get("content", ""),
                "file_id": reward.get("file_id"),
                "redeemed_at": datetime.now().isoformat(),
            }
            await self._db.referral_redemptions.insert_one(redemption_doc)
            return True, "success", self._clean_doc(redemption_doc)

    async def get_user_redemptions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get past claimed items for a user"""
        cursor = self._db.referral_redemptions.find({"user_id": user_id}).sort("id", -1)
        return [self._clean_doc(d) async for d in cursor]

    async def get_all_redemptions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all redemptions for admin panel"""
        cursor = self._db.referral_redemptions.find().sort("id", -1).limit(limit)
        return [self._clean_doc(d) async for d in cursor]

    async def export_backup_json(self) -> str:
        """Export all collections as structured JSON string"""
        import json
        data = {
            "exported_at": datetime.now().isoformat(),
            "users": [self._clean_doc(d) async for d in self._db.users.find()],
            "categories": [self._clean_doc(d) async for d in self._db.categories.find()],
            "products": [self._clean_doc(d) async for d in self._db.products.find()],
            "stock_items": [self._clean_doc(d) async for d in self._db.stock_items.find()],
            "orders": [self._clean_doc(d) async for d in self._db.orders.find()],
            "wallet_transactions": [self._clean_doc(d) async for d in self._db.wallet_transactions.find()],
            "used_transactions": [self._clean_doc(d) async for d in self._db.used_transactions.find()],
            "coupons": [self._clean_doc(d) async for d in self._db.coupons.find()],
            "verified_devices": [self._clean_doc(d) async for d in self._db.verified_devices.find()],
            "referral_rewards": [self._clean_doc(d) async for d in self._db.referral_rewards.find()],
            "referral_redemptions": [self._clean_doc(d) async for d in self._db.referral_redemptions.find()],
            "settings": [self._clean_doc(d) async for d in self._db.settings.find()],
        }
        return json.dumps(data, indent=2, default=str)


# Global database instance
db = Database()

