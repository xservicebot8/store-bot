"""
Admin authorization filter and middleware
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

import config


class AdminMiddleware(BaseMiddleware):
    """Restricts access to admin-only handlers"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        telegram_user = None
        if isinstance(event, Message):
            telegram_user = event.from_user
        elif isinstance(event, CallbackQuery):
            telegram_user = event.from_user

        if not telegram_user or not config.is_admin(telegram_user.id):
            if isinstance(event, Message):
                await event.answer("⛔ <b>Access Denied:</b> You are not authorized to access the admin panel.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Access Denied! Admins only.", show_alert=True)
            return

        return await handler(event, data)
