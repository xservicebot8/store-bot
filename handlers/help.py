"""
Support and FAQs Handler
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from utils.helpers import escape_html
import config

router = Router(name="help_router")


@router.callback_query(F.data == "user_support")
async def cb_user_support(callback: CallbackQuery):
    """Show customer support contact and store channel"""
    clean_support = config.SUPPORT_USERNAME.replace("@", "")
    clean_channel = config.CHANNEL_USERNAME.replace("@", "")

    text = f"""
📞 <b>Customer Support & Help Desk</b>

━━━━━━━━━━━━━━━━━━━━━
💬 Need assistance with an order, custom request, or payment?
Our support team is available to help you!

🛡️ <b>Official Support Handle:</b> {escape_html(config.SUPPORT_USERNAME)}
📢 <b>Updates & Proofs Channel:</b> {escape_html(config.CHANNEL_USERNAME)}
━━━━━━━━━━━━━━━━━━━━━

<i>Please make sure to have your Order ID ready when contacting support.</i>
"""

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 Contact Support", url=f"https://t.me/{clean_support}"),
                InlineKeyboardButton(text="📢 Join Channel", url=f"https://t.me/{clean_channel}"),
            ],
            [
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu_home"),
            ],
        ]
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()
