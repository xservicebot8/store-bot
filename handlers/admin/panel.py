"""
Admin Dashboard, Advanced Analytics, and Database Backup Handlers
"""

import os
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.filters import Command

from database.db import db
from keyboards.admin_kb import admin_main_kb
from middlewares.admin_middleware import AdminMiddleware
from utils.helpers import format_currency, escape_html
import config

router = Router(name="admin_panel_router")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Open admin panel via /admin command"""
    text = """
⚡ <b>Store Bot Administration Dashboard</b>

<i>Manage products, categories, stock, orders, payments, coupons, users, backups, and broadcasts from this control panel.</i>
"""
    await message.answer(text, reply_markup=admin_main_kb())


@router.callback_query(F.data == "admin_dashboard")
async def cb_admin_dashboard(callback: CallbackQuery):
    """Return to admin dashboard main menu"""
    text = """
⚡ <b>Store Bot Administration Dashboard</b>

<i>Manage products, categories, stock, orders, payments, coupons, users, backups, and broadcasts from this control panel.</i>
"""
    try:
        await callback.message.edit_text(text, reply_markup=admin_main_kb())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=admin_main_kb())
    await callback.answer()


@router.callback_query(F.data == "adm_stats")
async def cb_admin_stats(callback: CallbackQuery):
    """View advanced store sales statistics, revenue breakdowns, and bestsellers"""
    stats = await db.get_advanced_analytics()

    top_products_text = ""
    if stats.get("top_products"):
        top_products_text = "\n🏆 <b>Top Best-Selling Products:</b>\n"
        for idx, tp in enumerate(stats["top_products"], 1):
            top_products_text += f"{idx}. <b>{escape_html(tp['product_name'])}</b>: <code>{tp['units_sold']} sold</code> ({format_currency(tp['total_revenue'])})\n"

    text = f"""
📊 <b>Advanced Store Analytics & Revenue Report</b>

━━━━━━━━━━━━━━━━━━━━━
📅 <b>Today:</b> <code>{stats['today_orders']} orders</code> • <b>{format_currency(stats['today_revenue'])}</b>
📆 <b>Yesterday:</b> <code>{stats['yesterday_orders']} orders</code> • <b>{format_currency(stats['yesterday_revenue'])}</b>
🗓️ <b>This Month:</b> <code>{stats['month_orders']} orders</code> • <b>{format_currency(stats['month_revenue'])}</b>
━━━━━━━━━━━━━━━━━━━━━
💰 <b>All-Time Revenue:</b> <code>{format_currency(stats['total_revenue'])}</code>
📦 <b>Total Paid Orders:</b> <code>{stats['total_orders']}</code>
👥 <b>Total Customers:</b> <code>{stats['total_users']}</code>
⏳ <b>Pending Orders:</b> <code>{stats['pending_orders']}</code>
🛍️ <b>Active Products:</b> <code>{stats['active_products']}</code>
🔴 <b>Out-of-Stock Products:</b> <code>{stats['out_of_stock_products']}</code>
━━━━━━━━━━━━━━━━━━━━━
{top_products_text}
"""
    await callback.message.edit_text(text, reply_markup=admin_main_kb())
    await callback.answer()


@router.callback_query(F.data == "adm_backup_db")
async def cb_backup_database(callback: CallbackQuery, bot: Bot):
    """Send complete database backup (MongoDB JSON & SQLite if available) to admin"""
    from aiogram.types import BufferedInputFile

    try:
        json_backup_str = await db.export_backup_json()
        now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"MongoDB_Store_Backup_{now_str}.json"
        
        file_bytes = json_backup_str.encode("utf-8")
        file_size_kb = len(file_bytes) / 1024.0
        doc = BufferedInputFile(file_bytes, filename=backup_filename)

        await callback.message.answer_document(
            document=doc,
            caption=(
                f"💾 <b>Cloud Database Backup (MongoDB Atlas)</b>\n\n"
                f"📅 <b>Created:</b> {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
                f"📦 <b>File Size:</b> {file_size_kb:.2f} KB\n"
                f"🔒 <i>Includes all Users, Products, Stock Items, Orders, and Transactions.</i>"
            ),
        )
        await callback.answer("MongoDB backup generated and sent!", show_alert=True)
    except Exception as e:
        await callback.answer(f"Backup error: {e}", show_alert=True)

