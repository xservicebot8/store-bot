"""
Migration script: SQLite (data/store.db) to MongoDB Atlas
"""
import asyncio
import aiosqlite
import certifi
from motor.motor_asyncio import AsyncIOMotorClient

SQLITE_PATH = "data/store.db"
MONGO_URI = "mongodb+srv://khanshahbaz1563:khanshahbaz1563@cluster0.0fyxndt.mongodb.net/storebot?retryWrites=true&w=majority&appName=Cluster0"

async def migrate():
    print("Starting Migration from SQLite to MongoDB Atlas...")
    
    # Connect to MongoDB
    mongo_client = AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
    db = mongo_client["storebot"]
    
    # Test MongoDB connection
    await mongo_client.admin.command('ping')
    print("Connected to MongoDB Atlas successfully!")

    # Setup indexes
    await db.users.create_index("user_id", unique=True)
    await db.categories.create_index("id", unique=True)
    await db.products.create_index("id", unique=True)
    await db.stock_items.create_index("id", unique=True)
    await db.orders.create_index("id", unique=True)
    await db.orders.create_index("order_code", unique=True)
    await db.wallet_transactions.create_index("id", unique=True)
    await db.used_transactions.create_index("txn_id", unique=True)
    await db.coupons.create_index("id", unique=True)
    await db.coupons.create_index("code", unique=True)
    await db.settings.create_index("key", unique=True)

    # Open SQLite
    async with aiosqlite.connect(SQLITE_PATH) as sdb:
        sdb.row_factory = aiosqlite.Row

        # 1. Users
        async with sdb.execute("SELECT * FROM users") as cur:
            users = [dict(r) for r in await cur.fetchall()]
            if users:
                for u in users:
                    await db.users.update_one({"user_id": u["user_id"]}, {"$set": u}, upsert=True)
                print(f"Migrated {len(users)} users.")

        # 2. Categories
        async with sdb.execute("SELECT * FROM categories") as cur:
            categories = [dict(r) for r in await cur.fetchall()]
            if categories:
                for c in categories:
                    await db.categories.update_one({"id": c["id"]}, {"$set": c}, upsert=True)
                print(f"Migrated {len(categories)} categories.")

        # 3. Products
        async with sdb.execute("SELECT * FROM products") as cur:
            products = [dict(r) for r in await cur.fetchall()]
            if products:
                for p in products:
                    await db.products.update_one({"id": p["id"]}, {"$set": p}, upsert=True)
                print(f"Migrated {len(products)} products.")

        # 4. Stock Items
        async with sdb.execute("SELECT * FROM stock_items") as cur:
            stocks = [dict(r) for r in await cur.fetchall()]
            if stocks:
                for s in stocks:
                    await db.stock_items.update_one({"id": s["id"]}, {"$set": s}, upsert=True)
                print(f"Migrated {len(stocks)} stock items.")

        # 5. Orders
        async with sdb.execute("SELECT * FROM orders") as cur:
            orders = [dict(r) for r in await cur.fetchall()]
            if orders:
                for o in orders:
                    await db.orders.update_one({"id": o["id"]}, {"$set": o}, upsert=True)
                print(f"Migrated {len(orders)} orders.")

        # 6. Wallet Transactions
        async with sdb.execute("SELECT * FROM wallet_transactions") as cur:
            txns = [dict(r) for r in await cur.fetchall()]
            if txns:
                for t in txns:
                    await db.wallet_transactions.update_one({"id": t["id"]}, {"$set": t}, upsert=True)
                print(f"Migrated {len(txns)} wallet transactions.")

        # 7. Used Transactions
        async with sdb.execute("SELECT * FROM used_transactions") as cur:
            used_txns = [dict(r) for r in await cur.fetchall()]
            if used_txns:
                for ut in used_txns:
                    await db.used_transactions.update_one({"txn_id": ut["txn_id"]}, {"$set": ut}, upsert=True)
                print(f"Migrated {len(used_txns)} used transactions.")

        # 8. Coupons
        async with sdb.execute("SELECT * FROM coupons") as cur:
            coupons = [dict(r) for r in await cur.fetchall()]
            if coupons:
                for cp in coupons:
                    await db.coupons.update_one({"id": cp["id"]}, {"$set": cp}, upsert=True)
                print(f"Migrated {len(coupons)} coupons.")

        # Update Counters for auto-increment
        counters = [
            ("category_id", max([c["id"] for c in categories], default=1)),
            ("product_id", max([p["id"] for p in products], default=0)),
            ("stock_id", max([s["id"] for s in stocks], default=0)),
            ("order_id", max([o["id"] for o in orders], default=0)),
            ("wallet_txn_id", max([t["id"] for t in txns], default=0)),
            ("coupon_id", max([c["id"] for c in coupons], default=0)),
        ]
        for cname, cval in counters:
            await db.counters.update_one({"_id": cname}, {"$set": {"seq": cval}}, upsert=True)
        print("Updated sequence counters.")

    print("ALL DATA MIGRATED TO MONGODB ATLAS SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(migrate())
