"""
Admin Broadcast Announcement Handlers
"""

import asyncio
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import db
from keyboards.admin_kb import admin_main_kb
from middlewares.admin_middleware import AdminMiddleware
from utils.states import AdminBroadcastStates

router = Router(name="admin_broadcast_router")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.callback_query(F.data == "adm_broadcast")
async def cb_start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Prompt admin for broadcast message"""
    await state.set_state(AdminBroadcastStates.waiting_for_broadcast_content)
    text = """
📢 <b>Broadcast Announcement</b>

<i>Send the text, photo, or formatted message you want to broadcast to ALL registered store users:</i>
"""
    await callback.message.reply(text)
    await callback.answer()


@router.message(AdminBroadcastStates.waiting_for_broadcast_content)
async def process_broadcast_content(message: Message, state: FSMContext):
    """Confirm broadcast before sending"""
    await state.update_data(
        text=message.html_text if message.text else message.caption,
        photo_id=message.photo[-1].file_id if message.photo else None,
    )
    await state.set_state(AdminBroadcastStates.waiting_for_confirmation)

    users_count = await db.get_total_users_count()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"✅ Confirm & Send to {users_count} Users", callback_data="adm_send_broadcast"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="adm_cancel_broadcast"),
            ]
        ]
    )
    await message.reply(
        f"📢 <b>Broadcast Confirmation:</b>\n\n"
        f"This announcement will be delivered to <b>{users_count}</b> registered users.\n\n"
        f"<i>Are you ready to send?</i>",
        reply_markup=kb,
    )


@router.callback_query(AdminBroadcastStates.waiting_for_confirmation, F.data == "adm_send_broadcast")
async def cb_execute_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Send broadcast to all users"""
    data = await state.get_data()
    await state.clear()

    text = data.get("text")
    photo_id = data.get("photo_id")

    user_ids = await db.get_all_user_ids()
    total = len(user_ids)
    sent = 0
    failed = 0

    status_msg = await callback.message.reply(f"🚀 <b>Broadcasting in progress...</b> (0/{total})")

    for idx, uid in enumerate(user_ids, 1):
        try:
            if photo_id:
                await bot.send_photo(uid, photo=photo_id, caption=text)
            else:
                await bot.send_message(uid, text=text)
            sent += 1
        except Exception:
            failed += 1

        if idx % 25 == 0 or idx == total:
            try:
                await status_msg.edit_text(f"🚀 <b>Broadcasting in progress...</b> ({idx}/{total})\n✅ Sent: {sent} | ❌ Failed: {failed}")
            except Exception:
                pass
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"🎉 <b>Broadcast Completed!</b>\n\n"
        f"👥 Total Target: {total}\n"
        f"✅ Delivered: {sent}\n"
        f"❌ Failed / Blocked: {failed}",
        reply_markup=admin_main_kb(),
    )


@router.callback_query(AdminBroadcastStates.waiting_for_confirmation, F.data == "adm_cancel_broadcast")
async def cb_cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ <b>Broadcast Cancelled.</b>", reply_markup=admin_main_kb())
    await callback.answer()
