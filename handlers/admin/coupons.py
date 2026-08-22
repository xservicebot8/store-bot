"""
Admin Coupons & Promo Code Management Handlers
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import db
from keyboards.admin_kb import admin_coupons_kb, admin_main_kb
from middlewares.admin_middleware import AdminMiddleware
from utils.states import AdminCouponStates
from utils.helpers import format_currency, escape_html

router = Router(name="admin_coupons_router")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.callback_query(F.data == "adm_coupons_menu")
async def cb_admin_coupons(callback: CallbackQuery):
    """List all coupons"""
    coupons = await db.get_all_coupons()
    text = "🎟️ <b>Discount Coupons & Promo Codes:</b>"
    await callback.message.edit_text(text, reply_markup=admin_coupons_kb(coupons))
    await callback.answer()


@router.callback_query(F.data == "adm_add_coupon")
async def cb_create_coupon_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt for coupon code"""
    await state.set_state(AdminCouponStates.waiting_for_code)
    await callback.message.reply("🎟️ <b>Enter Coupon Code:</b>\n\n<i>Example: <code>SAVE20</code> or <code>WELCOME50</code></i>")
    await callback.answer()


@router.message(AdminCouponStates.waiting_for_code)
async def process_coupon_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    await state.update_data(code=code)
    await state.set_state(AdminCouponStates.waiting_for_type)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Percentage Discount (%)", callback_data="cptype_percent")],
            [InlineKeyboardButton(text="💵 Flat Discount (₹ INR)", callback_data="cptype_flat")],
        ]
    )
    await message.reply("📊 <b>Select Discount Type:</b>", reply_markup=kb)


@router.callback_query(AdminCouponStates.waiting_for_type, F.data.startswith("cptype_"))
async def process_coupon_type(callback: CallbackQuery, state: FSMContext):
    dtype = "percent" if "percent" in callback.data else "flat"
    await state.update_data(discount_type=dtype)
    await state.set_state(AdminCouponStates.waiting_for_value)

    prompt = "Enter percentage value (e.g. 20 for 20%):" if dtype == "percent" else "Enter flat discount in INR (e.g. 50):"
    await callback.message.reply(f"💰 <b>{prompt}</b>")
    await callback.answer()


@router.message(AdminCouponStates.waiting_for_value)
async def process_coupon_val(message: Message, state: FSMContext):
    try:
        val = float(message.text.strip())
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.reply("❌ Invalid value. Enter positive number:")
        return

    await state.update_data(discount_value=val)
    await state.set_state(AdminCouponStates.waiting_for_min_purchase)
    await message.reply("🛒 <b>Minimum Order Amount required (INR):</b>\n\n<i>Enter 0 for no minimum requirement.</i>")


@router.message(AdminCouponStates.waiting_for_min_purchase)
async def process_coupon_min(message: Message, state: FSMContext):
    try:
        min_p = float(message.text.strip())
    except ValueError:
        min_p = 0.0

    await state.update_data(min_purchase=min_p)
    await state.set_state(AdminCouponStates.waiting_for_max_uses)
    await message.reply("🔢 <b>Max Total Uses Allowed:</b>\n\n<i>Enter 0 for unlimited uses.</i>")


@router.message(AdminCouponStates.waiting_for_max_uses)
async def process_coupon_max(message: Message, state: FSMContext):
    try:
        max_u = int(message.text.strip())
    except ValueError:
        max_u = 0

    data = await state.get_data()
    await state.clear()

    await db.create_coupon(
        code=data["code"],
        discount_type=data["discount_type"],
        discount_value=data["discount_value"],
        min_purchase=data["min_purchase"],
        max_uses=max_u,
    )

    coupons = await db.get_all_coupons()
    await message.reply(
        f"✅ <b>Coupon '{data['code']}' Created Successfully!</b>",
        reply_markup=admin_coupons_kb(coupons),
    )


@router.callback_query(F.data.startswith("adm_view_coupon_"))
async def cb_view_coupon_detail(callback: CallbackQuery):
    """View and delete coupon"""
    c_id = int(callback.data.split("_")[3])
    # Fetch coupon from list
    coupons = await db.get_all_coupons()
    coupon = next((c for c in coupons if c["id"] == c_id), None)

    if not coupon:
        await callback.answer("Coupon not found!", show_alert=True)
        return

    val_str = f"{coupon['discount_value']}%" if coupon["discount_type"] == "percent" else format_currency(coupon["discount_value"])
    max_uses_str = "Unlimited" if coupon["max_uses"] == 0 else str(coupon["max_uses"])

    text = f"""
🎟️ <b>Coupon:</b> <code>{coupon['code']}</code>

━━━━━━━━━━━━━━━━━━━━━
💰 <b>Discount:</b> {val_str}
🛒 <b>Min Purchase:</b> {format_currency(coupon['min_purchase'])}
🔢 <b>Used:</b> {coupon['used_count']} / {max_uses_str}
━━━━━━━━━━━━━━━━━━━━━
"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Delete Coupon", callback_data=f"adm_del_coupon_{c_id}")],
            [InlineKeyboardButton(text="🔙 Back to Coupons", callback_data="adm_coupons_menu")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm_del_coupon_"))
async def cb_delete_coupon(callback: CallbackQuery):
    c_id = int(callback.data.split("_")[3])
    await db.delete_coupon(c_id)
    await callback.answer("Coupon deleted.", show_alert=True)
    coupons = await db.get_all_coupons()
    await callback.message.edit_text("🎟️ <b>Updated Coupons:</b>", reply_markup=admin_coupons_kb(coupons))
