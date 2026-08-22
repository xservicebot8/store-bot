"""
Coupons & Promo Code Handlers
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database.db import db
from keyboards.user_kb import checkout_payment_kb, main_menu_kb, back_to_menu_kb
from utils.states import UserPromoStates
from utils.helpers import format_currency, escape_html

router = Router(name="promo_router")


@router.callback_query(F.data == "user_apply_promo")
async def cb_enter_promo_standalone(callback: CallbackQuery, state: FSMContext):
    """Prompt user to enter general promo code"""
    await state.set_state(UserPromoStates.waiting_for_coupon_code)
    await callback.message.reply("🎟️ <b>Enter your Promo Code:</b>\n\n<i>Type your discount coupon code below:</i>")
    await callback.answer()


@router.callback_query(F.data.startswith("apply_coupon_"))
async def cb_enter_promo_for_order(callback: CallbackQuery, state: FSMContext):
    """Prompt user to enter coupon for a pending order"""
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)

    if not order or order["status"] != "pending":
        await callback.answer("Order is no longer active!", show_alert=True)
        return

    await state.set_state(UserPromoStates.waiting_for_coupon_code)
    await state.update_data(order_id=order_id)

    await callback.message.reply(
        f"🎟️ <b>Apply Coupon to Order #{order['order_code']}</b>\n\n"
        "<i>Please enter your coupon code:</i>"
    )
    await callback.answer()


@router.message(UserPromoStates.waiting_for_coupon_code)
async def process_coupon_submission(message: Message, state: FSMContext):
    """Validate and apply coupon code"""
    code = message.text.strip().upper()
    data = await state.get_data()
    order_id = data.get("order_id")
    user_id = message.from_user.id

    await state.clear()

    coupon = await db.get_coupon(code)
    if not coupon:
        await message.reply("❌ Invalid or expired coupon code.", reply_markup=main_menu_kb())
        return

    # Check max uses
    if coupon["max_uses"] > 0 and coupon["used_count"] >= coupon["max_uses"]:
        await message.reply("❌ This coupon has reached its maximum usage limit.", reply_markup=main_menu_kb())
        return

    # If applying to an order
    if order_id:
        order = await db.get_order(order_id)
        if not order or order["status"] != "pending":
            await message.reply("Order expired or completed.", reply_markup=main_menu_kb())
            return

        unit_total = float(order["unit_price"]) * int(order["quantity"])
        if coupon["min_purchase"] > 0 and unit_total < coupon["min_purchase"]:
            await message.reply(
                f"❌ Minimum purchase requirement for this coupon is {format_currency(coupon['min_purchase'])}.",
                reply_markup=main_menu_kb(),
            )
            return

        # Calculate discount
        if coupon["discount_type"] == "percent":
            discount = (unit_total * float(coupon["discount_value"])) / 100.0
        else:
            discount = float(coupon["discount_value"])

        discount = min(discount, unit_total)
        new_total = max(1.0, unit_total - discount)

        # Update order in DB
        await db.update_order_discount(order_id, discount, new_total)

        await db.use_coupon(coupon["id"], user_id, order_id)

        user = await db.get_user(user_id)
        user_balance = float(user.get("balance", 0.0)) if user else 0.0

        updated_text = f"""
🎉 <b>Coupon '{coupon['code']}' Applied Successfully!</b>

━━━━━━━━━━━━━━━━━━━━━
📦 <b>Item:</b> {escape_html(order['product_name'])}
🔢 <b>Quantity:</b> {order['quantity']}
💵 <b>Subtotal:</b> {format_currency(unit_total)}
🎟️ <b>Discount:</b> -{format_currency(discount)}
💰 <b>New Total:</b> <code>{format_currency(new_total)}</code>
━━━━━━━━━━━━━━━━━━━━━
💼 <b>Your Balance:</b> {format_currency(user_balance)}

👇 <b>Choose your payment method:</b>
"""
        await message.reply(
            updated_text,
            reply_markup=checkout_payment_kb(
                order_id=order_id,
                product_id=order["product_id"],
                final_amount=new_total,
                user_balance=user_balance,
            ),
        )
    else:
        # Standalone promo
        val_str = f"{coupon['discount_value']}%" if coupon["discount_type"] == "percent" else f"₹{coupon['discount_value']}"
        await message.reply(
            f"✅ <b>Coupon Verified:</b> <code>{coupon['code']}</code>\n"
            f"🎁 <b>Discount:</b> {val_str} off on orders!\n\n"
            "<i>You can use this coupon at checkout when purchasing any product!</i>",
            reply_markup=main_menu_kb(),
        )
