"""
Telegram Digital Store Bot - Main Entrypoint
Async, Clean Architecture powered by Aiogram 3 & Paytm Auto-Verification Engine
"""

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database.db import db
from handlers import all_routers
from handlers.checkout import deliver_order_items
from middlewares.user_middleware import UserMiddleware
from payments.paytm_verifier import setup_auto_verifier
from utils.helpers import format_currency

# Setup UTF-8 console output for Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("store_bot")


async def on_order_auto_verified(order: dict, transaction: dict, bot: Bot):
    """Callback when background verifier detects order payment"""
    order_id = order["id"]
    user_id = order["user_id"]
    txn_id = transaction.get("bizOrderId") or transaction.get("orderId") or "AUTO"

    logger.info(f"🎉 Triggering auto delivery for Order #{order['order_code']} (Txn: {txn_id})")
    await db.mark_transaction_used_async(
        txn_id=txn_id,
        order_id=order_id,
        amount=float(order["final_amount"]),
    )
    await deliver_order_items(bot, order, user_id)


async def on_deposit_auto_verified(deposit: dict, transaction: dict, bot: Bot):
    """Callback when background verifier detects wallet deposit"""
    user_id = deposit["user_id"]
    amount = float(deposit["amount"])
    txn_id = transaction.get("bizOrderId") or transaction.get("orderId") or "AUTO"

    logger.info(f"🎉 Auto-verified wallet deposit of ₹{amount} for user {user_id}")
    try:
        user = await db.get_user(user_id)
        current_bal = float(user.get("balance", 0.0)) if user else 0.0
        await bot.send_message(
            user_id,
            f"🎉 <b>Wallet Deposit Successful!</b>\n\n"
            f"💰 <b>Amount Credited:</b> {format_currency(amount)}\n"
            f"💼 <b>New Balance:</b> <code>{format_currency(current_bal)}</code>\n\n"
            f"<i>You can now purchase products with 1-click instant delivery!</i>",
        )
    except Exception as e:
        logger.error(f"Error sending deposit notification to user {user_id}: {e}")


async def handle_health_check(request):
    return web.Response(text="🤖 Telegram Store Bot is running healthy!", status=200)


async def start_web_server():
    """Start lightweight HTTP server for Render/Cloud Web Service health checks if PORT is set"""
    import os
    port_str = os.getenv("PORT")
    if not port_str:
        return None
    try:
        from aiohttp import web
        port = int(port_str)
        app = web.Application()
        app.router.add_get("/", handle_health_check)
        app.router.add_get("/health", handle_health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"🌐 Cloud Web Service active on port {port} (Render ready)")
        return runner
    except Exception as e:
        logger.warning(f"Could not start health check web server on port {port_str}: {e}")
        return None


async def main():
    """Main startup sequence"""
    print("=" * 55)
    print("🚀 Starting Telegram Digital Store Bot...")
    print("=" * 55)

    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN is not configured! Please add your bot token in .env file.")
        print("\n👉 Please open .env file and set your BOT_TOKEN from @BotFather\n")
        return

    # Start optional Cloud Health Server (Render compatibility)
    web_runner = await start_web_server()

    # Initialize Bot & Dispatcher
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Initialize Database
    await db.init()

    # Register Middlewares
    dp.update.outer_middleware(UserMiddleware())

    # Register all Routers
    for router in all_routers:
        dp.include_router(router)

    # Setup Paytm Auto Verifier Background Poller
    verifier = setup_auto_verifier(db)

    async def _order_cb(order, txn):
        await on_order_auto_verified(order, txn, bot)

    async def _deposit_cb(dep, txn):
        await on_deposit_auto_verified(dep, txn, bot)

    verifier.on_order_verified = _order_cb
    verifier.on_deposit_verified = _deposit_cb

    if config.PAYTM_SESSION and config.PAYTM_XSRF_TOKEN:
        await verifier.start(interval=config.AUTO_VERIFY_INTERVAL)
        logger.info(f"✅ Paytm Auto-Verifier active (Interval: {config.AUTO_VERIFY_INTERVAL}s)")
    else:
        logger.warning("⚠️ Paytm session cookies not set in .env. Running in QR & Manual UTR verification mode.")

    bot_user = await bot.get_me()
    print(f"✅ Bot connected successfully as @{bot_user.username} (ID: {bot_user.id})")
    print(f"👑 Admin IDs: {list(config.ADMIN_IDS)}")
    print(f"💳 Merchant UPI ID: {config.PAYTM_UPI_ID}")
    print("=" * 55)

    try:
        # Delete webhook if any and start long polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Shutting down bot...")
        if web_runner:
            await web_runner.cleanup()
        await verifier.stop()
        await db.close()
        await bot.session.close()
        logger.info("Bot shutdown completed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
