"""
Start Command and Main Menu Navigation Handlers
"""

from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from keyboards.user_kb import main_menu_kb
from database.db import db
from utils.helpers import format_currency, escape_html
import config

router = Router(name="start_router")


def get_welcome_text(user: dict, is_admin: bool = False) -> str:
    """Build stylish, compact welcome message with premium custom emojis"""
    from utils.helpers import EMOJI_BULLET, EMOJI_USER, EMOJI_STAR
    name = escape_html(user.get("full_name", "Valued Customer"))
    balance = format_currency(user.get("balance", 0.0))
    role_badge = f'<tg-emoji emoji-id="{EMOJI_STAR}">👑</tg-emoji> <b>Admin</b>' if is_admin else f'<tg-emoji emoji-id="{EMOJI_USER}">👤</tg-emoji> <b>Customer</b>'

    return (
        f'<tg-emoji emoji-id="{EMOJI_BULLET}">✨</tg-emoji> <b>Welcome to {escape_html(config.PAYTM_MERCHANT_NAME)}!</b>\n\n'
        f"👋 Hello, <b>{name}</b> ({role_badge})\n"
        f"💰 <b>Wallet Balance:</b> <code>{balance}</code>\n\n"
        f"👇 <i>Choose an option below:</i>"
    )


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    bot: Bot,
    user: Optional[dict] = None,
    is_admin: Optional[bool] = None,
    is_new: bool = False,
    referrer_id: Optional[int] = None,
    state: Optional[FSMContext] = None,
):
    """Handle /start command with referral code support and instant device verification prompt"""
    if state:
        await state.clear()
    user_id = message.from_user.id

    # Check for referral parameter in command if not provided by middleware
    if referrer_id is None:
        args = message.text.split(maxsplit=1) if message.text else []
        if len(args) > 1:
            param = args[1].strip()
            if param.startswith("ref_"):
                ref_str = param.replace("ref_", "")
                if ref_str.isdigit() and int(ref_str) != user_id:
                    referrer_id = int(ref_str)

    if user is None:
        username = f"@{message.from_user.username}" if message.from_user.username else None
        full_name = message.from_user.full_name or "Valued Customer"
        user, is_new = await db.get_or_create_user(user_id, username, full_name, referrer_id=referrer_id)

    if is_admin is None:
        is_admin = config.is_admin(user_id)

    # 1. Send Main Welcome Message
    text = get_welcome_text(user, is_admin)
    await message.answer(text, reply_markup=main_menu_kb(is_admin=is_admin))

    # 2. If user joined via referral and is not yet verified, send Device Verification Prompt
    is_verified = await db.is_user_device_verified(user_id)
    has_referrer = bool(referrer_id or user.get("referrer_id"))

    if has_referrer and not is_verified:
        try:
            from handlers.referral import get_device_verification_screen
            ver_text, ver_kb = await get_device_verification_screen(bot, user_id, is_referred=True)
            await message.answer(ver_text, reply_markup=ver_kb)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error sending referral verification prompt: {e}")


@router.callback_query(F.data == "menu_home")
async def cb_main_menu(
    callback: CallbackQuery,
    user: Optional[dict] = None,
    is_admin: Optional[bool] = None,
    state: Optional[FSMContext] = None,
):
    """Return to main menu from any sub-menu"""
    if state:
        await state.clear()
    user_id = callback.from_user.id
    if user is None:
        user = await db.get_user(user_id) or {"full_name": callback.from_user.full_name, "balance": 0.0}

    if is_admin is None:
        is_admin = config.is_admin(user_id)

    text = get_welcome_text(user, is_admin)
    try:
        await callback.message.edit_text(text, reply_markup=main_menu_kb(is_admin=is_admin))
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=main_menu_kb(is_admin=is_admin))
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    """Handle dummy/informational buttons"""
    await callback.answer()
