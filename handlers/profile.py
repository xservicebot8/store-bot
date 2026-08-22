"""
User Profile Handlers
"""

from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import db
from utils.helpers import format_currency, escape_html, format_timestamp

router = Router(name="profile_router")


@router.callback_query(F.data == "user_profile")
async def cb_user_profile(callback: CallbackQuery, bot: Bot, user: dict = None):
    """Show clean profile stats and balance"""
    user_id = callback.from_user.id
    current_user = await db.get_user(user_id) or user or {}

    balance = float(current_user.get("balance", 0.0))
    total_spent = float(current_user.get("total_spent", 0.0))
    name = escape_html(current_user.get("full_name", "Customer"))
    reg_date = format_timestamp(current_user.get("created_at"))

    from utils.helpers import EMOJI_USER, EMOJI_BACK
    text = f"""
<tg-emoji emoji-id="{EMOJI_USER}">👤</tg-emoji> <b>My Account Profile</b>

━━━━━━━━━━━━━━━━━━━━━
🆔 <b>User ID:</b> <code>{user_id}</code>
<tg-emoji emoji-id="{EMOJI_USER}">👤</tg-emoji> <b>Name:</b> {name}
📅 <b>Member Since:</b> {reg_date}
💰 <b>Wallet Balance:</b> <code>{format_currency(balance)}</code>
🛍️ <b>Total Purchases:</b> <code>{format_currency(total_spent)}</code>
━━━━━━━━━━━━━━━━━━━━━
"""

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💼 My Wallet", callback_data="user_wallet", style="success"),
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu_home", style="primary", icon_custom_emoji_id=EMOJI_BACK),
            ],
        ]
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()
