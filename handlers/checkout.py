"""
Checkout, Order Creation, and Payment Processing Handlers
"""

from io import BytesIO
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from aiogram.fsm.context import FSMContext

from database.db import db
from keyboards.user_kb import (
    quantity_selector_kb,
    checkout_payment_kb,
    payment_qr_kb,
    main_menu_kb,
    back_to_menu_kb,
)
from payments.paytm_qr import generate_payment_qr, generate_unique_transaction_ref
from payments.paytm_verifier import paytm_api
from utils.states import UserCheckoutStates, UserPromoStates
from utils.helpers import format_currency, escape_html, format_timestamp
import config

router = Router(name="checkout_router")


async def deliver_order_items(bot: Bot, order: dict, user_id: int) -> bool:
    """Deliver digital goods, individual unique files, or keys to the customer upon payment completion"""
    order_id = order["id"]
    product_id = order["product_id"]
    quantity = order.get("quantity", 1)
    product = await db.get_product(product_id)

    delivery_type = product.get("delivery_type", "line_stock") if product else "line_stock"
    # Map legacy delivery types
    if delivery_type == "stock":
        delivery_type = "line_stock"
    elif delivery_type == "file":
        delivery_type = "static_file"
    elif delivery_type == "manual":
        delivery_type = "static_text"

    delivered_text = ""
    files_to_send = []  # List of tuples: (file_id, file_name)

    if delivery_type == "file_stock":
        # Claim unique files for this customer
        items = await db.claim_stock_items(product_id, quantity, order_id)
        if items:
            file_names = []
            for itm in items:
                fid = itm.get("file_id")
                fname = itm.get("file_name") or "stock_file.txt"
                if fid:
                    files_to_send.append((fid, fname))
                    file_names.append(f"📁 <code>{escape_html(fname)}</code>")
                else:
                    file_names.append(f"🔑 <code>{escape_html(itm.get('content', ''))}</code>")
            delivered_text = "📁 <b>Your unique stock file(s) have been attached below:</b>\n" + "\n".join(file_names)
        else:
            delivered_text = "⚠️ <i>Stock was temporarily depleted. Store admin will fulfill your order shortly.</i>"

    elif delivery_type == "line_stock":
        # Claim available line items from DB
        items = await db.claim_stock_items(product_id, quantity, order_id)
        if items:
            delivered_text = "\n".join(
                f"🔑 <code>{escape_html(itm.get('content') if isinstance(itm, dict) else itm)}</code>"
                for itm in items
            )
        else:
            delivered_text = "⚠️ <i>Stock was temporarily depleted. Store admin will fulfill your order shortly.</i>"

    elif delivery_type == "static_file":
        if product and product.get("file_id"):
            files_to_send.append((product["file_id"], product.get("name", "download.txt")))
        delivered_text = "📁 <i>Your digital file has been attached below.</i>"

    elif delivery_type == "static_text":
        static_txt = (
            (product.get("static_content") or product.get("description") or "Access granted.")
            if product
            else "Access granted."
        )
        delivered_text = f"🎁 <b>Access Details / Code:</b>\n<code>{escape_html(static_txt)}</code>"

    # Update DB status
    await db.update_order_status(
        order_id=order_id,
        status="delivered",
        delivered_content=delivered_text,
    )

    # Add to total spent
    await db.add_user_total_spent(user_id, float(order.get("final_amount", 0)))

    # Send receipt & delivery message to buyer
    delivery_msg = f"""
🎉 <b>Payment Confirmed! Order Delivered!</b> 🎉

━━━━━━━━━━━━━━━━━━━━━
📦 <b>Product:</b> {escape_html(order['product_name'])}
🔢 <b>Quantity:</b> {quantity}
💰 <b>Amount Paid:</b> <code>{format_currency(order['final_amount'])}</code>
🧾 <b>Order ID:</b> <code>#{order['order_code']}</code>
━━━━━━━━━━━━━━━━━━━━━

🎁 <b>Your Delivered Content / Item(s):</b>
{delivered_text}

━━━━━━━━━━━━━━━━━━━━━
<i>Thank you for shopping with {escape_html(config.PAYTM_MERCHANT_NAME)}! You can view past orders anytime in <b>My Orders</b>.</i>
"""
    try:
        await bot.send_message(user_id, delivery_msg, reply_markup=main_menu_kb())

        # Send all attached documents/files
        for fid, fname in files_to_send:
            try:
                await bot.send_document(user_id, document=fid, caption=f"📁 {escape_html(fname)}")
            except Exception:
                pass

    except Exception:
        pass

    # Process referral purchase cashback
    try:
        buyer = await db.get_user(user_id)
        referrer_id = buyer.get("referrer_id") if buyer else None
        if referrer_id and buyer.get("is_device_verified") == 1:
            ref_settings = await db.get_referral_settings()
            if ref_settings.get("purchase_enabled"):
                purch_pct = ref_settings.get("purchase_percent", 5.0)
                final_amt = float(order.get("final_amount", 0))
                cashback = (purch_pct / 100.0) * final_amt
                if cashback >= 0.01:
                    await db.update_user_balance(referrer_id, cashback)
                    await db._db.users.update_one({"user_id": referrer_id}, {"$inc": {"referral_earnings": cashback}})
                    await db.create_wallet_transaction(
                        user_id=referrer_id,
                        amount=cashback,
                        txn_type="referral_cashback",
                        description=f"🎁 {purch_pct}% Cashback from friend's order #{order['order_code']}",
                        status="completed",
                    )
                    await bot.send_message(
                        referrer_id,
                        f"🎁 <b>Referral Cashback Received!</b>\n\n"
                        f"💰 <b>Cashback Earned:</b> <code>+{format_currency(cashback)}</code> ({purch_pct}%)\n"
                        f"🧾 <b>From Friend's Order:</b> #{order['order_code']}\n\n"
                        f"<i>Credited directly to your wallet!</i>",
                    )
    except Exception as e:
        logger.error(f"Error processing referral purchase cashback: {e}")

    # Notify Admins
    for admin_id in config.ADMIN_IDS:
        try:
            admin_notify = f"""
🔔 <b>New Order Paid & Delivered!</b>

🧾 <b>Order:</b> #{order['order_code']}
👤 <b>Customer ID:</b> <code>{user_id}</code>
📦 <b>Item:</b> {escape_html(order['product_name'])} (Qty: {quantity})
💵 <b>Paid:</b> {format_currency(order['final_amount'])} via {order.get('payment_method', 'N/A').upper()}
"""
            await bot.send_message(admin_id, admin_notify)
        except Exception:
            pass

    return True


@router.callback_query(F.data.startswith("buy_"))
async def cb_start_purchase(callback: CallbackQuery):
    """Start purchase flow and show quantity selection if stock > 1"""
    prod_id = int(callback.data.split("_")[1])
    product = await db.get_product(prod_id)

    if not product:
        await callback.answer("Product not found!", show_alert=True)
        return

    stock = product.get("stock_count", 0)
    cat_id = product.get("category_id", 0)

    if product.get("delivery_type") == "stock" and stock <= 0:
        await callback.answer("Sorry, this item is currently out of stock!", show_alert=True)
        return

    max_stock = stock if product.get("delivery_type") == "stock" else 10

    if max_stock > 1:
        text = f"""
🛒 <b>Select Quantity</b>

📦 <b>Item:</b> {escape_html(product['name'])}
💵 <b>Unit Price:</b> {format_currency(product['price'])}
🟢 <b>Available Stock:</b> {stock if product.get('delivery_type') == 'stock' else 'Unlimited'}

<i>Use the buttons below to choose how many units you wish to purchase:</i>
"""
        await callback.message.edit_text(
            text,
            reply_markup=quantity_selector_kb(
                product_id=prod_id,
                category_id=cat_id,
                quantity=1,
                max_stock=max_stock,
                unit_price=product["price"],
            ),
        )
        await callback.answer()
    else:
        # Proceed directly to checkout with qty 1
        await render_checkout_screen(callback, prod_id, 1)


@router.callback_query(F.data.startswith("qty_"))
async def cb_adjust_quantity(callback: CallbackQuery):
    """Handle +/- buttons in quantity selector"""
    parts = callback.data.split("_")
    prod_id = int(parts[1])
    new_qty = int(parts[2])

    product = await db.get_product(prod_id)
    if not product:
        await callback.answer("Product not found!", show_alert=True)
        return

    stock = product.get("stock_count", 0)
    max_stock = stock if product.get("delivery_type") == "stock" else 10
    cat_id = product.get("category_id", 0)

    try:
        await callback.message.edit_reply_markup(
            reply_markup=quantity_selector_kb(
                product_id=prod_id,
                category_id=cat_id,
                quantity=new_qty,
                max_stock=max_stock,
                unit_price=product["price"],
            )
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("checkout_"))
async def cb_proceed_checkout(callback: CallbackQuery):
    """Handle Proceed to Payment button"""
    parts = callback.data.split("_")
    prod_id = int(parts[1])
    quantity = int(parts[2])
    await render_checkout_screen(callback, prod_id, quantity)


async def render_checkout_screen(callback: CallbackQuery, product_id: int, quantity: int):
    """Create pending order and present payment choices"""
    user_id = callback.from_user.id
    product = await db.get_product(product_id)

    if not product:
        await callback.answer("Product not found!", show_alert=True)
        return

    unit_price = float(product["price"])
    total_amount = unit_price * quantity
    transaction_ref = generate_unique_transaction_ref()

    # Create pending order in database
    order = await db.create_order(
        user_id=user_id,
        product_id=product_id,
        product_name=product["name"],
        quantity=quantity,
        unit_price=unit_price,
        discount_amount=0.0,
        final_amount=total_amount,
        payment_method="upi_qr",
        transaction_ref=transaction_ref,
    )

    user = await db.get_user(user_id)
    user_balance = float(user.get("balance", 0.0)) if user else 0.0

    text = f"""
🧾 <b>Order Confirmation</b> • <code>#{order['order_code']}</code>

━━━━━━━━━━━━━━━━━━━━━
📦 <b>Item:</b> {escape_html(product['name'])}
🔢 <b>Quantity:</b> {quantity}
💵 <b>Unit Price:</b> {format_currency(unit_price)}
💰 <b>Total Payable:</b> <code>{format_currency(total_amount)}</code>
━━━━━━━━━━━━━━━━━━━━━
💼 <b>Your Wallet Balance:</b> {format_currency(user_balance)}

👇 <b>Select your payment method below:</b>
"""

    await callback.message.edit_text(
        text,
        reply_markup=checkout_payment_kb(
            order_id=order["id"],
            product_id=product_id,
            final_amount=total_amount,
            user_balance=user_balance,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_wallet_"))
async def cb_pay_with_wallet(callback: CallbackQuery, bot: Bot):
    """Pay using user wallet balance"""
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    user_id = callback.from_user.id

    if not order or order["status"] != "pending":
        await callback.answer("Order is no longer active!", show_alert=True)
        return

    amount = float(order["final_amount"])
    user = await db.get_user(user_id)
    balance = float(user.get("balance", 0.0)) if user else 0.0

    if balance < amount:
        await callback.answer("Insufficient wallet balance!", show_alert=True)
        return

    # Deduct balance atomically
    await db.update_user_balance(user_id, -amount)

    # Log wallet transaction
    await db.create_wallet_transaction(
        user_id=user_id,
        amount=amount,
        txn_type="purchase",
        description=f"Purchase of {order['product_name']} (#{order['order_code']})",
        status="completed",
    )

    # Deliver order
    await callback.message.delete()
    await deliver_order_items(bot, order, user_id)
    await callback.answer("Payment Successful! Delivering your items...", show_alert=True)


@router.callback_query(F.data.startswith("topup_and_pay_"))
async def cb_topup_and_pay(callback: CallbackQuery):
    """Notify user of shortage and offer direct UPI payment or wallet top-up"""
    order_id = int(callback.data.split("_")[3])
    order = await db.get_order(order_id)
    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    balance = float(user.get("balance", 0.0)) if user else 0.0
    needed = float(order["final_amount"]) - balance

    await callback.answer(
        f"Wallet balance is low ({format_currency(balance)}).\n"
        f"You need {format_currency(needed)} more. You can pay directly via UPI QR below!",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("pay_qr_"))
async def cb_pay_with_upi_qr(callback: CallbackQuery):
    """Generate dynamic UPI QR code and display payment screen"""
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)

    if not order or order["status"] != "pending":
        await callback.answer("Order is no longer active!", show_alert=True)
        return

    amount = float(order["final_amount"])
    trxn_ref = order.get("transaction_ref") or generate_unique_transaction_ref()

    qr_buffer, upi_url, _ = generate_payment_qr(
        upi_id=config.PAYTM_UPI_ID,
        merchant_name=config.PAYTM_MERCHANT_NAME,
        order_id=order["order_code"],
        amount=amount,
        transaction_ref=trxn_ref,
    )

    caption = f"""
⚡ <b>Scan & Pay via Any UPI App</b> ⚡

━━━━━━━━━━━━━━━━━━━━━
🧾 <b>Order:</b> <code>#{order['order_code']}</code>
💰 <b>Amount:</b> <code>{format_currency(amount)}</code>
🏷️ <b>Payment Note/Ref:</b> <code>{trxn_ref}</code>
💳 <b>Pay to UPI:</b> <code>{config.PAYTM_UPI_ID}</code>
━━━━━━━━━━━━━━━━━━━━━

📌 <b>Instructions:</b>
1. Scan the QR code using <b>Paytm, PhonePe, GPay, or BHIM</b>.
2. Pay the exact amount: <b>{format_currency(amount)}</b>.
3. <i>Payment is automatically verified within 10-20 seconds!</i>
4. If not verified automatically, click <b>Submit 12-Digit UTR</b> below.
"""

    photo_file = BufferedInputFile(qr_buffer.getvalue(), filename="upi_qr.png")

    try:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo_file,
            caption=caption,
            reply_markup=payment_qr_kb(order_id),
        )
    except Exception:
        await callback.message.answer_photo(
            photo=photo_file,
            caption=caption,
            reply_markup=payment_qr_kb(order_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("check_pay_"))
async def cb_check_payment_status(callback: CallbackQuery, bot: Bot):
    """Manual trigger to verify payment immediately"""
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    user_id = callback.from_user.id

    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return

    if order["status"] in ("paid", "delivered"):
        await callback.answer("✅ This order has already been verified and delivered!", show_alert=True)
        return

    amount = float(order["final_amount"])
    tr_ref = order.get("transaction_ref")
    utr = order.get("utr_number")

    matched_txn = None

    # Check via transaction ref
    if tr_ref:
        res = await paytm_api.search_by_transaction_ref(tr_ref, amount=amount)
        if res.get("found"):
            matched_txn = res.get("transaction")

    # Check via UTR
    if not matched_txn and utr:
        res = await paytm_api.search_by_utr(utr)
        for txn in res.get("orders", []):
            if txn.get("orderStatus", "").upper() in ("SUCCESS", "COMPLETED", "TXN_SUCCESS"):
                matched_txn = txn
                break

    if matched_txn:
        txn_id = matched_txn.get("bizOrderId") or matched_txn.get("orderId") or "UNKNOWN"
        if await db.is_transaction_used_async(txn_id):
            await callback.answer("⚠️ Transaction already redeemed for another order.", show_alert=True)
            return

        await db.mark_transaction_used_async(txn_id, order_id=order_id, amount=amount)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await deliver_order_items(bot, order, user_id)
        await callback.answer("✅ Payment Verified! Delivering now...", show_alert=True)
    else:
        await callback.answer(
            "⏳ Payment not detected yet. If you have completed payment, please click 'Submit UTR' or wait a few moments.",
            show_alert=True,
        )


@router.callback_query(F.data.startswith("submit_utr_"))
async def cb_submit_utr_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt user to type UTR number"""
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)

    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return

    await state.set_state(UserCheckoutStates.waiting_for_utr)
    await state.update_data(order_id=order_id)

    text = f"""
🔢 <b>Submit 12-Digit UPI Ref / UTR Number</b>

🧾 <b>Order:</b> <code>#{order['order_code']}</code>
💰 <b>Amount:</b> <code>{format_currency(order['final_amount'])}</code>

<i>Please enter the 12-digit UTR / Bank Reference Number from your payment app (e.g. <code>423189201923</code>):</i>
"""
    await callback.message.reply(text)
    await callback.answer()


@router.message(UserCheckoutStates.waiting_for_utr)
async def process_user_utr_submission(message: Message, state: FSMContext, bot: Bot):
    """Process submitted UTR number and verify immediately"""
    data = await state.get_data()
    order_id = data.get("order_id")
    utr = message.text.strip()

    if len(utr) < 6 or not utr.isalnum():
        await message.reply("❌ Invalid UTR format. Please enter a valid 12-digit UPI reference number:")
        return

    await state.clear()
    order = await db.get_order(order_id)

    if not order:
        await message.reply("Order not found.")
        return

    # Update order with submitted UTR
    await db.update_order_utr(order_id, utr)

    # Search Paytm API
    amount = float(order["final_amount"])
    res = await paytm_api.search_by_utr(utr)
    transactions = res.get("orders", [])

    matched = False
    for txn in transactions:
        status = txn.get("orderStatus", "").upper()
        if status in ("SUCCESS", "COMPLETED", "TXN_SUCCESS"):
            pay_amount = txn.get("payMoneyAmount", {})
            if isinstance(pay_amount, dict):
                txn_amount = float(pay_amount.get("value", 0) or 0) / 100.0
            else:
                txn_amount = float(txn.get("txnAmount", 0) or 0)

            if abs(txn_amount - amount) <= 0.01:
                txn_id = txn.get("bizOrderId") or txn.get("orderId") or "UNKNOWN"
                if not await db.is_transaction_used_async(txn_id):
                    await db.mark_transaction_used_async(txn_id, order_id=order_id, amount=amount)
                    await deliver_order_items(bot, order, message.from_user.id)
                    matched = True
                    break

    if not matched:
        await message.reply(
            f"⏳ <b>UTR Recorded:</b> <code>{escape_html(utr)}</code>\n\n"
            "<i>Your payment reference has been submitted. Our automated verifier is checking it. If needed, the admin will approve it manually shortly!</i>",
            reply_markup=main_menu_kb(),
        )
        # Notify Admin
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⚠️ <b>Manual UTR Submitted:</b>\n\n"
                    f"🧾 Order: #{order['order_code']}\n"
                    f"👤 User: <code>{message.from_user.id}</code>\n"
                    f"🔢 UTR: <code>{escape_html(utr)}</code>\n"
                    f"💰 Amount: {format_currency(amount)}",
                )
            except Exception:
                pass


@router.callback_query(F.data.startswith("cancel_order_"))
async def cb_cancel_order(callback: CallbackQuery):
    """Cancel pending order"""
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)

    if order and order["status"] == "pending":
        await db.update_order_status(order_id, "cancelled")
        await callback.answer("Order cancelled.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer("❌ <b>Order Cancelled.</b>", reply_markup=main_menu_kb())
    else:
        await callback.answer("Order cannot be cancelled.", show_alert=True)
