"""
Order History and Delivered Item Viewer Handlers
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.db import db
from keyboards.user_kb import orders_list_kb, back_to_menu_kb
from utils.helpers import format_currency, escape_html, format_timestamp

router = Router(name="orders_router")


@router.callback_query(F.data == "user_orders")
async def cb_user_orders_list(callback: CallbackQuery):
    """List recent orders placed by user"""
    user_id = callback.from_user.id
    orders = await db.get_user_orders(user_id, limit=15)

    if not orders:
        text = """
📦 <b>My Orders</b>

<i>You haven't placed any orders yet. Explore our store to make your first purchase!</i>
"""
        await callback.message.edit_text(text, reply_markup=back_to_menu_kb())
        await callback.answer()
        return

    text = """
📦 <b>My Order History</b>

<i>Select an order below to view receipt and delivered keys/files:</i>
"""
    await callback.message.edit_text(text, reply_markup=orders_list_kb(orders))
    await callback.answer()


@router.callback_query(F.data.startswith("view_order_"))
async def cb_view_single_order(callback: CallbackQuery):
    """View details and delivered keys for a specific order"""
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return

    status_badge = {
        "delivered": "✅ Delivered",
        "paid": "🟢 Paid (Processing)",
        "pending": "⏳ Pending Payment",
        "cancelled": "❌ Cancelled",
        "failed": "⚠️ Failed",
    }.get(order["status"], order["status"].capitalize())

    delivered_content_section = ""
    if order.get("delivered_content"):
        delivered_content_section = f"""
━━━━━━━━━━━━━━━━━━━━━
🎁 <b>Delivered Item(s):</b>
{order['delivered_content']}
"""

    text = f"""
🧾 <b>Order Details</b> • <code>#{order['order_code']}</code>

━━━━━━━━━━━━━━━━━━━━━
📦 <b>Product:</b> {escape_html(order['product_name'])}
🔢 <b>Quantity:</b> {order['quantity']}
💵 <b>Unit Price:</b> {format_currency(order['unit_price'])}
💰 <b>Total Amount:</b> <code>{format_currency(order['final_amount'])}</code>
📊 <b>Status:</b> <b>{status_badge}</b>
💳 <b>Payment Method:</b> {order.get('payment_method', 'N/A').upper()}
📅 <b>Order Date:</b> {format_timestamp(order['created_at'])}
{delivered_content_section}
━━━━━━━━━━━━━━━━━━━━━
"""
    await callback.message.edit_text(text, reply_markup=back_to_menu_kb())
    await callback.answer()
