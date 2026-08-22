"""
User registration and ban check middleware
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update

from database.db import db
import config


class UserMiddleware(BaseMiddleware):
    """Automatically registers users and blocks banned users"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        telegram_user = data.get("event_from_user")
        text_content = ""

        if not telegram_user:
            if isinstance(event, Message):
                telegram_user = event.from_user
                text_content = event.text or ""
            elif isinstance(event, CallbackQuery):
                telegram_user = event.from_user
            elif isinstance(event, Update):
                if event.message:
                    telegram_user = event.message.from_user
                    text_content = event.message.text or ""
                elif event.callback_query:
                    telegram_user = event.callback_query.from_user
        else:
            if isinstance(event, Message):
                text_content = event.text or ""
            elif isinstance(event, Update) and event.message:
                text_content = event.message.text or ""

        if telegram_user:
            user_id = telegram_user.id
            username = f"@{telegram_user.username}" if telegram_user.username else None
            full_name = telegram_user.full_name or "Anonymous"

            # Check if start command had a referral code
            referrer_id = None
            if text_content and text_content.startswith("/start ref_"):
                parts = text_content.split()
                if len(parts) > 1 and parts[1].startswith("ref_"):
                    try:
                        ref_code = parts[1].replace("ref_", "")
                        if ref_code.isdigit():
                            referrer_id = int(ref_code)
                    except Exception:
                        pass

            # Fetch or create user in DB
            user, is_new = await db.get_or_create_user(
                user_id=user_id,
                username=username,
                full_name=full_name,
                referrer_id=referrer_id,
            )

            # Check ban status
            if user and user.get("is_banned"):
                if isinstance(event, Message):
                    await event.answer("🚫 <b>Access Restricted:</b> Your account has been suspended by the store administrator.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Your account is suspended.", show_alert=True)
                elif isinstance(event, Update):
                    if event.message:
                        await event.message.answer("🚫 <b>Access Restricted:</b> Your account has been suspended.")
                    elif event.callback_query:
                        await event.callback_query.answer("🚫 Your account is suspended.", show_alert=True)
                return

            # Inject into handler data
            data["user"] = user
            data["is_new"] = is_new
            data["referrer_id"] = referrer_id
            data["is_admin"] = config.is_admin(user_id)

        return await handler(event, data)
