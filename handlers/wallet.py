"""
Wallet, Balance Top-up, and Transaction History Handlers
"""

from typing import Optional, Dict, Any, List
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from aiogram.fsm.context import FSMContext

from database.db import db
from keyboards.user_kb import (
    wallet_menu_kb,
    deposit_amount_presets_kb,
    deposit_qr_kb,
    main_menu_kb,
    back_to_menu_kb,
)
from payments.paytm_qr import generate_payment_qr, generate_unique_transaction_ref
from payments.paytm_verifier import paytm_api
from utils.states import UserDepositStates
from utils.helpers import format_currency, escape_html, format_timestamp
import config

router = Router(name="wallet_router")


@router.callback_query(F.data == "user_wallet")
async def cb_view_wallet(callback: CallbackQuery, user: Optional[dict] = None):
    """Show wallet balance and quick topup options"""
    user_id = callback.from_user.id
    current_user = await db.get_user(user_id) or user or {}

    balance = float(current_user.get("balance", 0.0))
    total_spent = float(current_user.get("total_spent", 0.0))
    ref_earnings = float(current_user.get("referral_earnings", 0.0))

    from utils.helpers import EMOJI_GIFT
    text = f"""
💼 <b>My Digital Wallet</b>

💰 <b>Current Balance:</b> <code>{format_currency(balance)}</code>
🛍️ <b>Total Spent:</b> <code>{format_currency(total_spent)}</code>
<tg-emoji emoji-id="{EMOJI_GIFT}">🎁</tg-emoji> <b>Referral Earnings:</b> <code>{format_currency(ref_earnings)}</code>

━━━━━━━━━━━━━━━━━━━━━
⚡ <i>Top-up your balance anytime for instant 1-click purchases on all store products!</i>
"""
    try:
        await callback.message.edit_text(text, reply_markup=wallet_menu_kb())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=wallet_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "wallet_deposit")
async def cb_deposit_presets(callback: CallbackQuery):
    """Display quick deposit preset amounts"""
    text = f"""
➕ <b>Add Balance / Top-up Wallet</b>

💳 <b>Payment Method:</b> UPI QR (Paytm, PhonePe, GPay, BHIM)
⚡ <b>Instant Verification:</b> 100% Automated
📌 <b>Minimum Deposit:</b> {format_currency(config.MIN_DEPOSIT)}

<i>Select a deposit amount below or enter a custom amount:</i>
"""
    await callback.message.edit_text(text, reply_markup=deposit_amount_presets_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("deposit_amt_"))
async def cb_preset_deposit_selected(callback: CallbackQuery):
    """Handle preset amount button"""
    amount = float(callback.data.split("_")[2])
    await generate_deposit_qr_screen(callback, amount)


@router.callback_query(F.data == "deposit_custom")
async def cb_custom_deposit_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt user for custom deposit amount"""
    await state.set_state(UserDepositStates.waiting_for_amount)
    await callback.message.reply(
        f"✏️ <b>Enter Deposit Amount (INR):</b>\n\n"
        f"<i>Minimum deposit amount is <b>{format_currency(config.MIN_DEPOSIT)}</b>. Example: <code>150</code></i>"
    )
    await callback.answer()


@router.message(UserDepositStates.waiting_for_amount)
async def process_custom_deposit_input(message: Message, state: FSMContext):
    """Process custom deposit input"""
    raw_text = message.text.strip()
    try:
        amount = float(raw_text)
        if amount < config.MIN_DEPOSIT:
            await message.reply(f"❌ Minimum deposit amount is {format_currency(config.MIN_DEPOSIT)}. Please enter a higher amount:")
            return
        if amount > 50000:
            await message.reply("❌ Maximum single deposit limit is ₹50,000. Please enter a lower amount:")
            return
    except ValueError:
        await message.reply("❌ Invalid number. Please enter a valid amount (e.g. 100):")
        return

    await state.clear()
    await generate_deposit_qr_from_message(message, amount)


async def generate_deposit_qr_screen(callback: CallbackQuery, amount: float):
    """Create deposit record and show QR code"""
    user_id = callback.from_user.id
    trxn_ref = generate_unique_transaction_ref(prefix="DEP")

    # Create pending wallet transaction
    dep_id = await db.create_wallet_transaction(
        user_id=user_id,
        amount=amount,
        txn_type="deposit",
        description=f"Wallet Top-up (+{format_currency(amount)})",
        transaction_ref=trxn_ref,
        status="pending",
    )

    qr_buffer, upi_url, _ = generate_payment_qr(
        upi_id=config.PAYTM_UPI_ID,
        merchant_name=config.PAYTM_MERCHANT_NAME,
        order_id=f"DEP{dep_id}",
        amount=amount,
        transaction_ref=trxn_ref,
    )

    caption = f"""
➕ <b>Wallet Top-up QR Code</b> ➕

━━━━━━━━━━━━━━━━━━━━━
💰 <b>Deposit Amount:</b> <code>{format_currency(amount)}</code>
🏷️ <b>Reference Code:</b> <code>{trxn_ref}</code>
💳 <b>Pay to UPI:</b> <code>{config.PAYTM_UPI_ID}</code>
━━━━━━━━━━━━━━━━━━━━━

📌 <b>Instructions:</b>
1. Scan & pay via <b>Paytm, PhonePe, GPay, or any UPI app</b>.
2. Ensure you pay the exact amount: <b>{format_currency(amount)}</b>.
3. Balance will be credited automatically within 10-20 seconds!
"""

    photo = BufferedInputFile(qr_buffer.getvalue(), filename="deposit_qr.png")

    try:
        await callback.message.delete()
        await callback.message.answer_photo(photo, caption=caption, reply_markup=deposit_qr_kb(dep_id))
    except Exception:
        await callback.message.answer_photo(photo, caption=caption, reply_markup=deposit_qr_kb(dep_id))
    await callback.answer()


async def generate_deposit_qr_from_message(message: Message, amount: float):
    """Create deposit record and show QR code from message"""
    user_id = message.from_user.id
    trxn_ref = generate_unique_transaction_ref(prefix="DEP")

    dep_id = await db.create_wallet_transaction(
        user_id=user_id,
        amount=amount,
        txn_type="deposit",
        description=f"Wallet Top-up (+{format_currency(amount)})",
        transaction_ref=trxn_ref,
        status="pending",
    )

    qr_buffer, upi_url, _ = generate_payment_qr(
        upi_id=config.PAYTM_UPI_ID,
        merchant_name=config.PAYTM_MERCHANT_NAME,
        order_id=f"DEP{dep_id}",
        amount=amount,
        transaction_ref=trxn_ref,
    )

    caption = f"""
➕ <b>Wallet Top-up QR Code</b> ➕

━━━━━━━━━━━━━━━━━━━━━
💰 <b>Deposit Amount:</b> <code>{format_currency(amount)}</code>
🏷️ <b>Reference Code:</b> <code>{trxn_ref}</code>
💳 <b>Pay to UPI:</b> <code>{config.PAYTM_UPI_ID}</code>
━━━━━━━━━━━━━━━━━━━━━

📌 <b>Instructions:</b>
1. Scan & pay via <b>Paytm, PhonePe, GPay, or any UPI app</b>.
2. Pay the exact amount: <b>{format_currency(amount)}</b>.
3. Balance will be credited automatically within 10-20 seconds!
"""

    photo = BufferedInputFile(qr_buffer.getvalue(), filename="deposit_qr.png")
    await message.answer_photo(photo, caption=caption, reply_markup=deposit_qr_kb(dep_id))


@router.callback_query(F.data.startswith("check_dep_"))
async def cb_check_deposit_status(callback: CallbackQuery, bot: Bot):
    """Manual check for deposit status"""
    dep_id = int(callback.data.split("_")[2])
    txn = await db.get_wallet_transaction(dep_id)

    if not txn:
        await callback.answer("Deposit record not found!", show_alert=True)
        return

    if txn["status"] == "completed":
        await callback.answer("✅ Deposit already credited!", show_alert=True)
        return

    tr_ref = txn.get("transaction_ref")
    amount = float(txn["amount"])

    res = await paytm_api.search_by_transaction_ref(tr_ref, amount=amount)
    if res.get("found"):
        matched = res.get("transaction")
        txn_id = matched.get("bizOrderId") or matched.get("orderId") or "UNKNOWN"

        if not await db.is_transaction_used_async(txn_id):
            await db.complete_wallet_deposit(dep_id, utr_number=tr_ref, paytm_txn_id=txn_id)
            await callback.answer("🎉 Deposit Verified! Balance credited.", show_alert=True)
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(
                f"✅ <b>Wallet Credited!</b>\n\n"
                f"Amount: <b>{format_currency(amount)}</b> has been successfully added to your wallet.",
                reply_markup=main_menu_kb(),
            )
            return

    await callback.answer("⏳ Payment not detected yet. Please ensure payment is done or submit UTR.", show_alert=True)


@router.callback_query(F.data.startswith("submit_dep_utr_"))
async def cb_deposit_utr_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt for deposit UTR"""
    dep_id = int(callback.data.split("_")[3])
    await state.set_state(UserDepositStates.waiting_for_deposit_utr)
    await state.update_data(dep_id=dep_id)

    await callback.message.reply("🔢 <b>Enter the 12-digit UTR / UPI Ref Number for this deposit:</b>")
    await callback.answer()


@router.message(UserDepositStates.waiting_for_deposit_utr)
async def process_deposit_utr(message: Message, state: FSMContext, bot: Bot):
    """Process deposit UTR"""
    data = await state.get_data()
    dep_id = data.get("dep_id")
    utr = message.text.strip()

    if len(utr) < 6:
        await message.reply("❌ Invalid UTR. Please enter valid UPI reference number:")
        return

    await state.clear()
    txn = await db.get_wallet_transaction(dep_id)
    if not txn:
        await message.reply("Deposit record not found.")
        return

    amount = float(txn["amount"])
    res = await paytm_api.search_by_utr(utr)
    transactions = res.get("orders", [])

    matched = False
    for t in transactions:
        if t.get("orderStatus", "").upper() in ("SUCCESS", "COMPLETED", "TXN_SUCCESS"):
            pay_amount = t.get("payMoneyAmount", {})
            if isinstance(pay_amount, dict):
                txn_amount = float(pay_amount.get("value", 0) or 0) / 100.0
            else:
                txn_amount = float(t.get("txnAmount", 0) or 0)

            if abs(txn_amount - amount) <= 0.01:
                paytm_id = t.get("bizOrderId") or t.get("orderId") or "UNKNOWN"
                if not await db.is_transaction_used_async(paytm_id):
                    await db.complete_wallet_deposit(dep_id, utr_number=utr, paytm_txn_id=paytm_id)
                    matched = True
                    await message.reply(
                        f"🎉 <b>Deposit Verified!</b>\n\n"
                        f"Amount of <b>{format_currency(amount)}</b> has been added to your wallet balance!",
                        reply_markup=main_menu_kb(),
                    )
                    break

    if not matched:
        await message.reply(
            f"⏳ <b>Deposit UTR Recorded:</b> <code>{escape_html(utr)}</code>\n\n"
            "<i>Our system is verifying your payment. Your balance will update automatically shortly!</i>",
            reply_markup=main_menu_kb(),
        )


@router.callback_query(F.data == "wallet_history")
async def cb_wallet_history(callback: CallbackQuery):
    """View past wallet transactions"""
    user_id = callback.from_user.id
    history = await db.get_user_wallet_history(user_id, limit=10)

    if not history:
        text = """
📜 <b>Wallet Transaction History</b>

<i>No past wallet transactions found.</i>
"""
    else:
        text = "📜 <b>Recent Wallet Transactions</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
        for h in history:
            sign = "+" if h["type"] in ("deposit", "referral", "refund") else "-"
            status_icon = "✅" if h["status"] == "completed" else "⏳"
            text += f"{status_icon} <b>{h['type'].upper()}:</b> {sign}{format_currency(h['amount'])}\n"
            text += f"   <i>{escape_html(h['description'])}</i> • {format_timestamp(h['created_at'])}\n\n"

    await callback.message.edit_text(text, reply_markup=back_to_menu_kb())
    await callback.answer()
