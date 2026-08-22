"""
Admin Settings, Paytm API Health, and Configuration Handlers
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from keyboards.admin_kb import admin_settings_kb, admin_main_kb
from middlewares.admin_middleware import AdminMiddleware
from payments.paytm_verifier import paytm_api
from paytm_login import update_env_file
from utils.states import AdminSettingsStates, AdminReferralRewardStates
from utils.helpers import escape_html, format_currency
import config

router = Router(name="admin_settings_router")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.callback_query(F.data == "adm_settings")
async def cb_admin_settings(callback: CallbackQuery):
    """Display settings menu"""
    text = f"""
⚙️ <b>Store & Payment Settings</b>

━━━━━━━━━━━━━━━━━━━━━
💰 <b>Minimum Wallet Deposit:</b> <code>{format_currency(config.MIN_DEPOSIT)}</code>
💳 <b>Receiver UPI ID:</b> <code>{escape_html(config.PAYTM_UPI_ID)}</code>
🏷️ <b>Merchant Name:</b> <code>{escape_html(config.PAYTM_MERCHANT_NAME)}</code>
📞 <b>Support Username:</b> <code>{escape_html(config.SUPPORT_USERNAME)}</code>
📢 <b>Official Channel:</b> <code>{escape_html(config.CHANNEL_USERNAME)}</code>
⚡ <b>Auto-Verify Check:</b> Every <code>{config.AUTO_VERIFY_INTERVAL}s</code>
🎁 <b>Referral Cashback:</b> <code>{config.REFERRAL_PERCENT}%</code>
━━━━━━━━━━━━━━━━━━━━━

<i>Choose an option below to update store configurations:</i>
"""
    await callback.message.edit_text(
        text,
        reply_markup=admin_settings_kb(
            paytm_api._cookies_valid if hasattr(paytm_api, "_cookies_valid") else True
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_test_paytm")
async def cb_test_paytm_health(callback: CallbackQuery):
    """Test Paytm API session validity"""
    await callback.answer("Testing connection to Paytm Dashboard API...")
    res = await paytm_api.check_cookie_health()

    status_icon = "🟢" if res.get("valid") else "🔴"
    text = f"""
🔍 <b>Paytm API Health Status:</b> {status_icon} <b>{'ACTIVE' if res.get('valid') else 'INACTIVE'}</b>

━━━━━━━━━━━━━━━━━━━━━
📊 <b>Status Code:</b> <code>{res.get('status')}</code>
📝 <b>Message:</b> <code>{escape_html(res.get('message'))}</code>
━━━━━━━━━━━━━━━━━━━━━

<i>If cookies are expired, click 'Update Cookies' below or run <code>python paytm_login.py</code> on your server.</i>
"""
    await callback.message.edit_text(
        text, reply_markup=admin_settings_kb(is_paytm_valid=res.get("valid", False))
    )


# ---------------------------------------------------------------------------
# Minimum Deposit Setting
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "adm_set_min_deposit")
async def cb_prompt_min_deposit(callback: CallbackQuery, state: FSMContext):
    """Prompt admin to set new minimum deposit amount"""
    await state.set_state(AdminSettingsStates.waiting_for_min_deposit)
    await callback.message.reply(
        f"💰 <b>Set Minimum Wallet Deposit Amount</b>\n\n"
        f"<i>Current Minimum: <b>{format_currency(config.MIN_DEPOSIT)}</b></i>\n\n"
        f"👉 Enter new minimum amount in INR (e.g. <code>10</code>, <code>50</code>, <code>100</code>):"
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_for_min_deposit)
async def process_min_deposit_change(message: Message, state: FSMContext):
    """Save new minimum deposit setting"""
    raw_text = message.text.strip()
    try:
        new_min = float(raw_text)
        if new_min < 1:
            await message.reply("❌ Minimum deposit amount must be at least ₹1.00. Enter again:")
            return
        if new_min > 10000:
            await message.reply("❌ Minimum deposit cannot exceed ₹10,000. Enter again:")
            return
    except ValueError:
        await message.reply("❌ Invalid number! Please enter a valid amount (e.g. 20):")
        return

    await state.clear()
    config.MIN_DEPOSIT = new_min
    update_env_file({"MIN_DEPOSIT": str(new_min)})

    await message.reply(
        f"✅ <b>Minimum Deposit Updated Successfully!</b>\n\n"
        f"💰 <b>New Minimum Deposit:</b> <code>{format_currency(new_min)}</code>\n\n"
        f"<i>Saved to .env and active immediately for all customers!</i>",
        reply_markup=admin_settings_kb(),
    )


# ---------------------------------------------------------------------------
# UPI ID & Merchant Name Setting
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "adm_set_upi")
async def cb_prompt_upi_update(callback: CallbackQuery, state: FSMContext):
    """Prompt for new UPI ID"""
    await state.set_state(AdminSettingsStates.waiting_for_upi_id)
    await callback.message.reply(
        f"💳 <b>Enter New UPI ID:</b>\n\n"
        f"<i>Current: <code>{config.PAYTM_UPI_ID}</code> (e.g. <code>store@paytm</code>)</i>"
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_for_upi_id)
async def process_upi_id_change(message: Message, state: FSMContext):
    new_upi = message.text.strip()
    config.PAYTM_UPI_ID = new_upi
    update_env_file({"PAYTM_UPI_ID": new_upi})
    await state.set_state(AdminSettingsStates.waiting_for_merchant_name)
    await message.reply(
        f"🏷️ <b>Enter Merchant Display Name:</b>\n\n"
        f"<i>Current: <code>{config.PAYTM_MERCHANT_NAME}</code></i>"
    )


@router.message(AdminSettingsStates.waiting_for_merchant_name)
async def process_merchant_name_change(message: Message, state: FSMContext):
    new_name = message.text.strip()
    config.PAYTM_MERCHANT_NAME = new_name
    update_env_file({"PAYTM_MERCHANT_NAME": new_name})
    await state.clear()

    await message.reply(
        f"✅ <b>UPI Payment Settings Updated!</b>\n\n"
        f"💳 UPI ID: <code>{config.PAYTM_UPI_ID}</code>\n"
        f"🏷️ Name: <code>{config.PAYTM_MERCHANT_NAME}</code>",
        reply_markup=admin_settings_kb(),
    )


# ---------------------------------------------------------------------------
# Support & Official Channel Setting
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "adm_set_social")
async def cb_prompt_social_update(callback: CallbackQuery, state: FSMContext):
    """Prompt for support username"""
    await state.set_state(AdminSettingsStates.waiting_for_support_user)
    await callback.message.reply(
        f"📞 <b>Enter Support Username / Link:</b>\n\n"
        f"<i>Current: <code>{config.SUPPORT_USERNAME}</code> (e.g. <code>@MySupportBot</code>)</i>"
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_for_support_user)
async def process_support_user_change(message: Message, state: FSMContext):
    new_support = message.text.strip()
    if not new_support.startswith("@") and not new_support.startswith("http"):
        new_support = f"@{new_support}"
    config.SUPPORT_USERNAME = new_support
    update_env_file({"SUPPORT_USERNAME": new_support})

    await state.set_state(AdminSettingsStates.waiting_for_channel_user)
    await message.reply(
        f"📢 <b>Enter Official Telegram Channel Username / Link:</b>\n\n"
        f"<i>Current: <code>{config.CHANNEL_USERNAME}</code> (e.g. <code>@MyStoreChannel</code>)</i>"
    )


@router.message(AdminSettingsStates.waiting_for_channel_user)
async def process_channel_user_change(message: Message, state: FSMContext):
    new_channel = message.text.strip()
    if not new_channel.startswith("@") and not new_channel.startswith("http"):
        new_channel = f"@{new_channel}"
    config.CHANNEL_USERNAME = new_channel
    update_env_file({"CHANNEL_USERNAME": new_channel})
    await state.clear()

    await message.reply(
        f"✅ <b>Support & Channel Settings Updated!</b>\n\n"
        f"📞 Support: <code>{config.SUPPORT_USERNAME}</code>\n"
        f"📢 Channel: <code>{config.CHANNEL_USERNAME}</code>",
        reply_markup=admin_settings_kb(),
    )


# ---------------------------------------------------------------------------
# Paytm Session Cookies Setting
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "adm_set_paytm_cookies")
async def cb_prompt_session_cookie(callback: CallbackQuery, state: FSMContext):
    """Prompt for Paytm SESSION cookie"""
    await state.set_state(AdminSettingsStates.waiting_for_session_cookie)
    await callback.message.reply(
        "🔑 <b>Paste the Paytm 'SESSION' Cookie value:</b>\n\n"
        "<i>(Inspect element -> Application -> Cookies -> dashboard.paytm.com -> SESSION)</i>"
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_for_session_cookie)
async def process_session_cookie(message: Message, state: FSMContext):
    session = message.text.strip()
    await state.update_data(session=session)
    await state.set_state(AdminSettingsStates.waiting_for_xsrf_token)
    await message.reply(
        "🔑 <b>Paste the Paytm 'XSRF-TOKEN' Cookie value:</b>\n\n"
        "<i>(Inspect element -> Application -> Cookies -> dashboard.paytm.com -> XSRF-TOKEN)</i>"
    )


@router.message(AdminSettingsStates.waiting_for_xsrf_token)
async def process_xsrf_cookie(message: Message, state: FSMContext):
    xsrf = message.text.strip()
    data = await state.get_data()
    session = data.get("session")
    await state.clear()

    config.PAYTM_SESSION = session
    config.PAYTM_XSRF_TOKEN = xsrf
    update_env_file({"PAYTM_SESSION": session, "PAYTM_XSRF_TOKEN": xsrf})

    paytm_api.configure(session=session, xsrf_token=xsrf)
    res = await paytm_api.check_cookie_health()

    status_icon = "🟢 ACTIVE" if res.get("valid") else "⚠️ SAVED (Check Health)"

    await message.reply(
        f"✅ <b>Paytm Credentials Updated!</b>\n\n"
        f"Status: {status_icon}\n"
        f"Message: <code>{res.get('message')}</code>",
        reply_markup=admin_settings_kb(is_paytm_valid=res.get("valid", False)),
    )


# ---------------------------------------------------------------------------
# Referral Program Admin Settings
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "adm_ref_settings")
async def cb_admin_referral_settings(callback: CallbackQuery):
    """Open referral program configuration menu"""
    from keyboards.admin_kb import admin_referral_settings_kb
    from database.db import db

    settings = await db.get_referral_settings()
    join_state = "🟢 Enabled (Active)" if settings.get("join_enabled") else "🔴 Disabled"
    purch_state = "🟢 Enabled (Active)" if settings.get("purchase_enabled") else "🔴 Disabled"

    text = f"""
🎁 <b>Referral & Anti-Fraud Program Configuration</b>

━━━━━━━━━━━━━━━━━━━━━
🎁 <b>Join / Device Reward:</b> {join_state}
💰 <b>Reward Per Verified Friend:</b> <code>{format_currency(settings.get('join_amount', 5.0))}</code>
🛒 <b>Purchase Cashback:</b> {purch_state}
📊 <b>Cashback Percentage:</b> <code>{settings.get('purchase_percent', 5.0):g}%</code>
📢 <b>Official Channel:</b> <code>{escape_html(settings.get('channel', config.CHANNEL_USERNAME))}</code>
━━━━━━━━━━━━━━━━━━━━━

🛡️ <b>Anti-Fraud Protection:</b> <i>Enforces 1 unique device and IP per account before distributing referral rewards.</i>
"""
    await callback.message.edit_text(text, reply_markup=admin_referral_settings_kb(settings))
    await callback.answer()


@router.callback_query(F.data == "adm_toggle_ref_join")
async def cb_toggle_ref_join(callback: CallbackQuery):
    """Toggle join reward ON/OFF"""
    from keyboards.admin_kb import admin_referral_settings_kb
    from database.db import db

    settings = await db.get_referral_settings()
    new_val = "0" if settings.get("join_enabled") else "1"
    await db.set_setting("ref_join_enabled", new_val)

    updated_settings = await db.get_referral_settings()
    await callback.message.edit_reply_markup(reply_markup=admin_referral_settings_kb(updated_settings))
    await callback.answer(f"Join reward {'enabled' if new_val == '1' else 'disabled'}")


@router.callback_query(F.data == "adm_set_ref_join_amt")
async def cb_prompt_ref_join_amt(callback: CallbackQuery, state: FSMContext):
    """Prompt for new join reward amount"""
    await state.set_state(AdminSettingsStates.waiting_for_ref_join_amt)
    await callback.message.reply(
        "💰 <b>Enter new Join Reward Amount in INR:</b>\n\n"
        "<i>(e.g. <code>2</code>, <code>5</code>, <code>10</code>)</i>"
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_for_ref_join_amt)
async def process_ref_join_amt(message: Message, state: FSMContext):
    from keyboards.admin_kb import admin_referral_settings_kb
    from database.db import db

    try:
        amt = float(message.text.strip())
        if amt < 0:
            raise ValueError()
    except ValueError:
        await message.reply("❌ Invalid amount. Enter a positive number (e.g. 5):")
        return

    await db.set_setting("ref_join_amount", str(amt))
    await state.clear()

    settings = await db.get_referral_settings()
    await message.reply(
        f"✅ <b>Join Reward Updated to {format_currency(amt)}!</b>",
        reply_markup=admin_referral_settings_kb(settings),
    )


@router.callback_query(F.data == "adm_toggle_ref_purch")
async def cb_toggle_ref_purch(callback: CallbackQuery):
    """Toggle purchase cashback ON/OFF"""
    from keyboards.admin_kb import admin_referral_settings_kb
    from database.db import db

    settings = await db.get_referral_settings()
    new_val = "0" if settings.get("purchase_enabled") else "1"
    await db.set_setting("ref_purch_enabled", new_val)

    updated_settings = await db.get_referral_settings()
    await callback.message.edit_reply_markup(reply_markup=admin_referral_settings_kb(updated_settings))
    await callback.answer(f"Purchase cashback {'enabled' if new_val == '1' else 'disabled'}")


@router.callback_query(F.data == "adm_set_ref_purch_pct")
async def cb_prompt_ref_purch_pct(callback: CallbackQuery, state: FSMContext):
    """Prompt for new purchase cashback percentage"""
    await state.set_state(AdminSettingsStates.waiting_for_ref_purch_pct)
    await callback.message.reply(
        "📊 <b>Enter new Purchase Cashback Percentage (1 - 50%):</b>\n\n"
        "<i>(e.g. <code>5</code>, <code>10</code>, <code>15</code>)</i>"
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_for_ref_purch_pct)
async def process_ref_purch_pct(message: Message, state: FSMContext):
    from keyboards.admin_kb import admin_referral_settings_kb
    from database.db import db

    try:
        pct = float(message.text.strip())
        if pct < 0 or pct > 100:
            raise ValueError()
    except ValueError:
        await message.reply("❌ Invalid percentage. Enter between 1 and 100 (e.g. 5):")
        return

    await db.set_setting("ref_purch_percent", str(pct))
    await state.clear()

    settings = await db.get_referral_settings()
    await message.reply(
        f"✅ <b>Purchase Cashback Updated to {pct:g}%!</b>",
        reply_markup=admin_referral_settings_kb(settings),
    )


@router.callback_query(F.data == "adm_set_ref_channel")
async def cb_prompt_ref_channel(callback: CallbackQuery, state: FSMContext):
    """Prompt for referral channel username"""
    await state.set_state(AdminSettingsStates.waiting_for_ref_channel)
    await callback.message.reply(
        "📢 <b>Enter Official Channel Username or Link:</b>\n\n"
        "<i>(e.g. <code>@MyStoreChannel</code>)</i>"
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_for_ref_channel)
async def process_ref_channel(message: Message, state: FSMContext):
    from keyboards.admin_kb import admin_referral_settings_kb
    from database.db import db

    ch = message.text.strip()
    if not ch.startswith("@") and not ch.startswith("http"):
        ch = f"@{ch}"

    await db.set_setting("ref_channel", ch)
    await state.clear()

    settings = await db.get_referral_settings()
    await message.reply(
        f"✅ <b>Referral Channel Updated to {escape_html(ch)}!</b>",
        reply_markup=admin_referral_settings_kb(settings),
    )


# ---------------------------------------------------------------------------
# Admin Referral Points Rewards Shop Management
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "adm_ref_rewards_menu")
async def cb_admin_ref_rewards_menu(callback: CallbackQuery):
    """List all redeemable rewards in admin panel"""
    from keyboards.admin_kb import admin_referral_rewards_list_kb
    from database.db import db

    rewards = await db.get_all_referral_rewards(only_active=False)
    text = f"""
🎁 <b>Referral Points Rewards Shop Management</b>

━━━━━━━━━━━━━━━━━━━━━
📦 <b>Total Rewards:</b> <code>{len(rewards)}</code>
💎 <i>Manage redeemable products, keys, and codes available for user referral points!</i>
━━━━━━━━━━━━━━━━━━━━━
"""
    await callback.message.edit_text(text, reply_markup=admin_referral_rewards_list_kb(rewards))
    await callback.answer()


@router.callback_query(F.data == "adm_add_ref_reward")
async def cb_admin_add_ref_reward_start(callback: CallbackQuery, state: FSMContext):
    """Start wizard to add new redeemable reward"""
    from utils.states import AdminReferralRewardStates

    await state.set_state(AdminReferralRewardStates.waiting_for_name)
    await callback.message.reply(
        "🎁 <b>Step 1/4: Enter Reward Title / Item Name:</b>\n\n"
        "<i>(e.g. <code>Netflix 1 Month Account</code> or <code>100 INR Discount Code</code>)</i>"
    )
    await callback.answer()


@router.message(AdminReferralRewardStates.waiting_for_name)
async def process_ref_rew_name(message: Message, state: FSMContext):
    from utils.states import AdminReferralRewardStates

    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(AdminReferralRewardStates.waiting_for_points)
    await message.reply(
        f"💎 <b>Step 2/4: Enter Referral Points Required for '{escape_html(name)}':</b>\n\n"
        f"<i>(e.g. <code>3</code>, <code>5</code>, <code>10</code>)</i>"
    )


@router.message(AdminReferralRewardStates.waiting_for_points)
async def process_ref_rew_points(message: Message, state: FSMContext):
    from utils.states import AdminReferralRewardStates

    try:
        pts = int(message.text.strip())
        if pts < 1:
            raise ValueError()
    except ValueError:
        await message.reply("❌ Please enter a valid positive integer (e.g. 3, 5):")
        return

    await state.update_data(points_cost=pts)
    await state.set_state(AdminReferralRewardStates.waiting_for_desc)
    await message.reply(
        "📝 <b>Step 3/4: Enter Short Description or Instructions for the user:</b>\n\n"
        "<i>(e.g. <code>Instant auto delivery. Contact support if any issue.</code>)</i>"
    )


@router.message(AdminReferralRewardStates.waiting_for_desc)
async def process_ref_rew_desc(message: Message, state: FSMContext):
    from utils.states import AdminReferralRewardStates

    desc = message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(AdminReferralRewardStates.waiting_for_content)
    await message.reply(
        "🔑 <b>Step 4/4: Send Delivery Content (Text, Account Credentials, Code, or upload a .txt Document):</b>"
    )


@router.message(AdminReferralRewardStates.waiting_for_content)
async def process_ref_rew_content(message: Message, state: FSMContext):
    from keyboards.admin_kb import admin_referral_rewards_list_kb
    from database.db import db

    data = await state.get_data()
    name = data.get("name")
    points_cost = data.get("points_cost", 1)
    desc = data.get("description", "")

    file_id = None
    delivery_type = "text"
    content = ""

    if message.document:
        file_id = message.document.file_id
        delivery_type = "file"
        content = message.caption or message.document.file_name or "Stock File"
    else:
        content = message.text or ""

    reward_id = await db.create_referral_reward(
        name=name,
        description=desc,
        points_cost=points_cost,
        delivery_type=delivery_type,
        content=content,
        file_id=file_id,
    )
    await state.clear()

    rewards = await db.get_all_referral_rewards(only_active=False)
    await message.reply(
        f"✅ <b>Referral Reward Created Successfully!</b>\n\n"
        f"🎁 <b>Item:</b> {escape_html(name)}\n"
        f"💎 <b>Points Cost:</b> <code>{points_cost} Points</code>\n"
        f"🆔 <b>Reward ID:</b> <code>#{reward_id}</code>",
        reply_markup=admin_referral_rewards_list_kb(rewards),
    )


@router.callback_query(F.data.startswith("adm_view_ref_rew_"))
async def cb_admin_view_ref_reward(callback: CallbackQuery):
    """View details of a referral reward in admin panel"""
    from keyboards.admin_kb import admin_referral_reward_detail_kb
    from database.db import db

    reward_id = int(callback.data.split("_")[4])
    reward = await db.get_referral_reward(reward_id)

    if not reward:
        await callback.answer("Reward not found.", show_alert=True)
        return

    text = f"""
🎁 <b>Reward Details: #{reward['id']}</b>

━━━━━━━━━━━━━━━━━━━━━
🏷️ <b>Name:</b> {escape_html(reward['name'])}
💎 <b>Points Cost:</b> <code>{reward['points_cost']} Points</code>
📊 <b>Total Redeemed:</b> <code>{reward.get('redeemed_count', 0)} times</code>
📝 <b>Description:</b> {escape_html(reward.get('description', 'N/A'))}
🔑 <b>Content / Code:</b>
<code>{escape_html(reward.get('content', 'N/A'))}</code>
━━━━━━━━━━━━━━━━━━━━━
"""
    await callback.message.edit_text(text, reply_markup=admin_referral_reward_detail_kb(reward_id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_del_ref_rew_"))
async def cb_admin_delete_ref_reward(callback: CallbackQuery):
    """Delete a referral reward item"""
    from keyboards.admin_kb import admin_referral_rewards_list_kb
    from database.db import db

    reward_id = int(callback.data.split("_")[4])
    await db.delete_referral_reward(reward_id)

    rewards = await db.get_all_referral_rewards(only_active=False)
    await callback.message.edit_text(
        "🗑️ <b>Referral Reward Deleted!</b>",
        reply_markup=admin_referral_rewards_list_kb(rewards),
    )
    await callback.answer("Reward deleted successfully!")


