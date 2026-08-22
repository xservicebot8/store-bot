"""
Admin User Management and Balance Adjustment Handlers
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import db
from keyboards.admin_kb import admin_user_actions_kb, admin_main_kb
from middlewares.admin_middleware import AdminMiddleware
from utils.states import AdminUserStates
from utils.helpers import format_currency, escape_html, format_timestamp

router = Router(name="admin_users_router")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.callback_query(F.data == "adm_users_menu")
async def cb_admin_users_menu(callback: CallbackQuery, state: FSMContext):
    """Prompt admin to search for a user"""
    await state.set_state(AdminUserStates.waiting_for_user_query)
    text = """
👥 <b>User Management</b>

<i>Send a User ID, @username, or name to search customer records:</i>
"""
    await callback.message.edit_text(text)
    await callback.answer()


@router.message(AdminUserStates.waiting_for_user_query)
async def process_user_search(message: Message, state: FSMContext):
    """Search users in DB"""
    query = message.text.strip().replace("@", "")
    await state.clear()

    users = await db.search_users(query)
    if not users:
        await message.reply(f"❌ No users found matching '<code>{escape_html(query)}</code>'.", reply_markup=admin_main_kb())
        return

    user = users[0]
    await display_user_card(message, user)


async def display_user_card(message: Message, user: dict):
    """Display user details with admin actions"""
    user_id = user["user_id"]
    name = escape_html(user.get("full_name", "N/A"))
    username = escape_html(user.get("username", "N/A"))
    balance = float(user.get("balance", 0.0))
    spent = float(user.get("total_spent", 0.0))
    banned = "🚫 BANNED" if user.get("is_banned") else "🟢 ACTIVE"

    text = f"""
👤 <b>Customer Details</b>

━━━━━━━━━━━━━━━━━━━━━
🆔 <b>User ID:</b> <code>{user_id}</code>
👤 <b>Name:</b> {name}
💬 <b>Username:</b> {username}
💰 <b>Balance:</b> <code>{format_currency(balance)}</code>
🛍️ <b>Total Spent:</b> <code>{format_currency(spent)}</code>
📊 <b>Account Status:</b> <b>{banned}</b>
📅 <b>Joined:</b> {format_timestamp(user.get('created_at'))}
━━━━━━━━━━━━━━━━━━━━━
"""
    await message.reply(text, reply_markup=admin_user_actions_kb(user))


@router.callback_query(F.data.startswith("adm_usr_addbal_"))
async def cb_prompt_add_balance(callback: CallbackQuery, state: FSMContext):
    """Prompt for balance addition"""
    target_id = int(callback.data.split("_")[3])
    await state.set_state(AdminUserStates.waiting_for_balance_adjust)
    await state.update_data(target_id=target_id, action="add")
    await callback.message.reply(f"➕ <b>Enter Amount to ADD to User {target_id}'s balance (INR):</b>")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_usr_dedbal_"))
async def cb_prompt_deduct_balance(callback: CallbackQuery, state: FSMContext):
    """Prompt for balance deduction"""
    target_id = int(callback.data.split("_")[3])
    await state.set_state(AdminUserStates.waiting_for_balance_adjust)
    await state.update_data(target_id=target_id, action="deduct")
    await callback.message.reply(f"➖ <b>Enter Amount to DEDUCT from User {target_id}'s balance (INR):</b>")
    await callback.answer()


@router.message(AdminUserStates.waiting_for_balance_adjust)
async def process_balance_adjustment(message: Message, state: FSMContext, bot: Bot):
    """Execute balance adjustment"""
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply("❌ Invalid amount. Enter positive number:")
        return

    data = await state.get_data()
    target_id = data.get("target_id")
    action = data.get("action")
    await state.clear()

    delta = amount if action == "add" else -amount
    new_bal = await db.update_user_balance(target_id, delta)

    # Log transaction
    await db.create_wallet_transaction(
        user_id=target_id,
        amount=amount,
        txn_type="adjustment",
        description=f"Admin Balance {'Credit' if action == 'add' else 'Debit'}",
        status="completed",
    )

    action_text = "Added" if action == "add" else "Deducted"
    await message.reply(
        f"✅ <b>Successfully {action_text} {format_currency(amount)}!</b>\n\n"
        f"👤 User: <code>{target_id}</code>\n"
        f"💰 New Balance: <code>{format_currency(new_bal)}</code>",
        reply_markup=admin_main_kb(),
    )

    # Notify User
    try:
        if action == "add":
            await bot.send_message(
                target_id,
                f"🎉 <b>Wallet Balance Added!</b>\n\n"
                f"The store admin credited <b>{format_currency(amount)}</b> to your wallet.\n"
                f"💰 Current Balance: <b>{format_currency(new_bal)}</b>",
            )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_usr_toggleban_"))
async def cb_toggle_ban_user(callback: CallbackQuery):
    """Toggle ban status for user"""
    target_id = int(callback.data.split("_")[3])
    user = await db.get_user(target_id)
    if not user:
        await callback.answer("User not found!", show_alert=True)
        return

    new_status = not bool(user.get("is_banned", 0))
    await db.set_user_ban_status(target_id, new_status)

    action_msg = "User BANNED 🚫" if new_status else "User UNBANNED 🟢"
    await callback.answer(action_msg, show_alert=True)

    updated_user = await db.get_user(target_id)
    await callback.message.edit_reply_markup(reply_markup=admin_user_actions_kb(updated_user))


@router.callback_query(F.data.startswith("adm_usr_orders_"))
async def cb_view_user_orders(callback: CallbackQuery):
    """View all past orders for a specific user"""
    target_id = int(callback.data.split("_")[3])
    orders = await db.get_user_orders(target_id, limit=20)

    if not orders:
        text = f"📦 <b>Orders for User <code>{target_id}</code>:</b>\n\n<i>No orders found for this user.</i>"
    else:
        text = f"📦 <b>Orders for User <code>{target_id}</code>:</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
        for o in orders:
            icon = "✅" if o["status"] == "delivered" else "⏳"
            text += f"{icon} <b>#{o['order_code']}</b> • {escape_html(o['product_name'])} (Qty: {o['quantity']})\n"
            text += f"   Amount: {format_currency(o['final_amount'])} • Status: {o['status'].upper()}\n"
            text += f"   Date: {format_timestamp(o['created_at'])}\n\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Users", callback_data="adm_users_menu")],
            [InlineKeyboardButton(text="⚡ Admin Dashboard", callback_data="admin_dashboard")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()
