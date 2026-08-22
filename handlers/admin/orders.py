"""
Admin Order Management and Manual Action Handlers
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import db
from keyboards.admin_kb import admin_orders_filter_kb, admin_order_actions_kb, admin_main_kb
from middlewares.admin_middleware import AdminMiddleware
from handlers.checkout import deliver_order_items
from utils.helpers import format_currency, escape_html, format_timestamp

router = Router(name="admin_orders_router")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.callback_query(F.data == "adm_orders_menu")
async def cb_admin_orders_menu(callback: CallbackQuery):
    """Show orders list menu"""
    await render_orders_list(callback, status=None, filter_name="all")


@router.callback_query(F.data == "adm_orders_pending")
async def cb_orders_pending(callback: CallbackQuery):
    await render_orders_list(callback, status="pending", filter_name="pending")


@router.callback_query(F.data == "adm_orders_paid")
async def cb_orders_paid(callback: CallbackQuery):
    await render_orders_list(callback, status="delivered", filter_name="paid")


@router.callback_query(F.data == "adm_orders_all")
async def cb_orders_all(callback: CallbackQuery):
    await render_orders_list(callback, status=None, filter_name="all")


async def render_orders_list(callback: CallbackQuery, status: str = None, filter_name: str = "all"):
    """Render list of orders with filter controls"""
    orders = await db.get_all_orders(limit=25, status=status)

    builder = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏳ Pending", callback_data="adm_orders_pending"),
                InlineKeyboardButton(text="✅ Delivered", callback_data="adm_orders_paid"),
                InlineKeyboardButton(text="📦 All", callback_data="adm_orders_all"),
            ]
        ]
    )

    if not orders:
        text = f"📋 <b>Orders ({filter_name.upper()}):</b>\n\n<i>No orders found matching this filter.</i>"
    else:
        text = f"📋 <b>Orders ({filter_name.upper()}):</b>\n\n<i>Click an order to view details & take actions:</i>"
        custom_rows = []
        for o in orders:
            icon = "⏳" if o["status"] == "pending" else "✅"
            custom_rows.append([
                InlineKeyboardButton(
                    text=f"{icon} #{o['order_code']} • {o['product_name']} ({format_currency(o['final_amount'])})",
                    callback_data=f"adm_view_order_{o['id']}",
                )
            ])
        custom_rows.append([InlineKeyboardButton(text="🔙 Admin Dashboard", callback_data="admin_dashboard")])
        builder = InlineKeyboardMarkup(inline_keyboard=builder.inline_keyboard + custom_rows)

    await callback.message.edit_text(text, reply_markup=builder)
    await callback.answer()


@router.callback_query(F.data.startswith("adm_view_order_"))
async def cb_admin_view_order(callback: CallbackQuery):
    """View details of a specific order in admin panel"""
    order_id = int(callback.data.split("_")[3])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return

    text = f"""
🧾 <b>Order Details:</b> <code>#{order['order_code']}</code>

━━━━━━━━━━━━━━━━━━━━━
👤 <b>Customer ID:</b> <code>{order['user_id']}</code>
📦 <b>Item:</b> {escape_html(order['product_name'])}
🔢 <b>Quantity:</b> {order['quantity']}
💵 <b>Total:</b> <code>{format_currency(order['final_amount'])}</code>
📊 <b>Status:</b> <b>{order['status'].upper()}</b>
🏷️ <b>Txn Ref:</b> <code>{order.get('transaction_ref', 'N/A')}</code>
🔢 <b>Submitted UTR:</b> <code>{order.get('utr_number', 'None')}</code>
📅 <b>Date:</b> {format_timestamp(order['created_at'])}
━━━━━━━━━━━━━━━━━━━━━
"""
    await callback.message.edit_text(text, reply_markup=admin_order_actions_kb(order))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_approve_order_"))
async def cb_force_approve_order(callback: CallbackQuery, bot: Bot):
    """Force approve and deliver order items"""
    order_id = int(callback.data.split("_")[3])
    order = await db.get_order(order_id)

    if not order or order["status"] != "pending":
        await callback.answer("Order cannot be approved.", show_alert=True)
        return

    await deliver_order_items(bot, order, order["user_id"])
    await callback.answer("✅ Order approved & items delivered to customer!", show_alert=True)
    await cb_admin_view_order(callback)


@router.callback_query(F.data.startswith("adm_cancel_order_"))
async def cb_admin_cancel_order(callback: CallbackQuery):
    """Cancel order"""
    order_id = int(callback.data.split("_")[3])
    await db.update_order_status(order_id, "cancelled")
    await callback.answer("Order marked cancelled.", show_alert=True)
    await cb_admin_view_order(callback)


@router.callback_query(F.data.startswith("adm_refund_order_"))
async def cb_refund_order(callback: CallbackQuery, bot: Bot):
    """Refund order amount back to user's wallet"""
    order_id = int(callback.data.split("_")[3])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return

    amount = float(order["final_amount"])
    user_id = order["user_id"]

    await db.update_user_balance(user_id, amount)
    await db.create_wallet_transaction(
        user_id=user_id,
        amount=amount,
        txn_type="refund",
        description=f"Refund for Order #{order['order_code']}",
        status="completed",
    )
    await db.update_order_status(order_id, "cancelled")

    try:
        await bot.send_message(
            user_id,
            f"↩️ <b>Order Refunded!</b>\n\n"
            f"Amount: <b>{format_currency(amount)}</b> for Order #{order['order_code']} has been credited back to your wallet.",
        )
    except Exception:
        pass

    await callback.answer("Order refunded to user wallet!", show_alert=True)
    await cb_admin_view_order(callback)
