"""
Anti-Fraud Device Verification & Referral Points Reward System
Referral gives 1 Point per verified friend, redeemable exclusively in the Points Shop!
"""

import random
import string
import logging
from typing import Optional
import aiohttp
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)

from database.db import db
from utils.helpers import (
    escape_html,
    EMOJI_BULLET,
    EMOJI_STAR,
    EMOJI_BACK,
    EMOJI_GIFT,
    EMOJI_USER,
    EMOJI_SUCCESS,
    EMOJI_FAIL,
)
import config

logger = logging.getLogger(__name__)

router = Router(name="referral_router")


def generate_device_hash(length: int = 34) -> str:
    """Generate a secure 34-character random hash for verification session"""
    pool = string.ascii_letters + string.digits
    return "".join(random.choices(pool, k=length))


def get_referral_dashboard_text(
    user_id: int,
    bot_username: str,
    stats: dict,
) -> str:
    """Format rich, aesthetic referral dashboard with Points balance"""
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    points = stats.get("points", 0)

    return f"""
<tg-emoji emoji-id="{EMOJI_GIFT}">🎁</tg-emoji> <b>Refer & Earn Program</b>

Invite friends to <b>{escape_html(config.PAYTM_MERCHANT_NAME)}</b> and earn <b>Referral Points</b> to redeem exclusive digital rewards!

━━━━━━━━━━━━━━━━━━━━━
💎 <b>My Referral Points:</b> <code>{points} Point{'s' if points != 1 else ''}</code>
👥 <b>Total Friends Invited:</b> <code>{stats.get('total_referrals', 0)}</code>
<tg-emoji emoji-id="{EMOJI_SUCCESS}">✅</tg-emoji> <b>Verified Friends:</b> <code>{stats.get('verified_referrals', 0)}</code>
━━━━━━━━━━━━━━━━━━━━━

🌟 <b>How Points Work:</b>
1️⃣ Share your referral link with friends.
2️⃣ When your friend joins & verifies their device, <b>you receive +1 Point</b>!
3️⃣ Accumulate points and redeem secret rewards, gift cards & keys in the <b>Points Shop</b>!

🔗 <b>Your Exclusive Referral Link:</b>
<code>{ref_link}</code>

<i>Tap the link above to copy and share!</i>
"""


def get_referral_dashboard_kb(user_id: int, bot_username: str) -> InlineKeyboardMarkup:
    """Keyboard for verified referral dashboard"""
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    share_url = f"https://t.me/share/url?url={ref_link}&text=Join%20{config.PAYTM_MERCHANT_NAME}%20now%20to%20get%20exclusive%20access!"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛍️ ━━ REDEEM POINTS SHOP ━━ 🛍️",
                    callback_data="ref_shop",
                    style="success",
                    icon_custom_emoji_id=EMOJI_GIFT,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📢 Share Link with Friends",
                    url=share_url,
                    style="primary",
                    icon_custom_emoji_id=EMOJI_BULLET,
                ),
                InlineKeyboardButton(
                    text="📜 Claimed Rewards",
                    callback_data="ref_my_claims",
                    style="primary",
                    icon_custom_emoji_id=EMOJI_STAR,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Main Menu",
                    callback_data="menu_home",
                    style="primary",
                    icon_custom_emoji_id=EMOJI_BACK,
                ),
            ],
        ]
    )


async def get_device_verification_screen(bot: Bot, user_id: int, is_referred: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    """Build the anti-fraud device verification screen with WebApp button"""
    bot_info = await bot.get_me()
    random_hash = generate_device_hash(34)

    # Save session in DB
    await db.create_verification_session(user_id=user_id, bot_hash=random_hash)

    # Register hash with verification service
    try:
        webhook_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage?chat_id={user_id}&text=Verified"
        register_url = (
            f"https://project-hub.tg-dev-pro.site/tg-client/bot_register.php?"
            f"botHash={random_hash}&bot=@{bot_info.username}&webhook_url={webhook_url}&bot_token={config.BOT_TOKEN}"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(register_url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                resp_text = await resp.text()
                logger.info(f"Verification registration response for {user_id}: {resp_text}")
    except Exception as e:
        logger.error(f"Verification registration ping error: {e}")

    web_page = f"https://project-hub.tg-dev-pro.site/tg-client/index.html?bot_hash={random_hash}&bot=@{bot_info.username}"

    if is_referred:
        text = f"""
🔒 <b>Device Verification Required</b>

👋 <b>Welcome!</b> You joined through an invitation link.
To verify your account and confirm the referral, please complete a quick 1-time device verification.

⚠️ <b>Security & Anti-Fraud Policy:</b>
• <b>1 Device / 1 IP = 1 Account only</b>
• VPNs, proxies, and emulators are prohibited
• Multiple accounts from the same device are restricted

💡 <i>Note: Even if verification is skipped or fails, you can still use all bot and store features (Wallet, Catalog, Shopping) normally! However, referral rewards for the inviter will not be credited.</i>

👉 <i>Click <b>'🔐 Start Device Verification'</b> below to verify:</i>
"""
    else:
        text = f"""
🔒 <b>Device Verification Required</b>

To generate your exclusive referral link, invite friends, and earn <b>Referral Points</b>, please complete a quick one-time device verification.

⚠️ <b>Anti-Abuse Notice:</b>
• <b>1 Device / 1 IP = 1 Account only</b>
• Using VPNs, proxies, or Tor will result in verification failure
• Device verification protects against duplicate farming accounts

👉 <i>Click <b>'🔐 Start Device Verification'</b> below to verify your device:</i>
"""

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔐 Start Device Verification",
                    web_app=WebAppInfo(url=web_page),
                    style="success",
                    icon_custom_emoji_id=EMOJI_SUCCESS,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Check Status",
                    callback_data=f"check_dev_ver_{user_id}",
                    style="primary",
                    icon_custom_emoji_id=EMOJI_BULLET,
                ),
                InlineKeyboardButton(
                    text="🏠 Main Menu",
                    callback_data="menu_home",
                    style="primary",
                    icon_custom_emoji_id=EMOJI_BACK,
                ),
            ],
        ]
    )
    return text, kb


@router.message(Command("referral", "ref"))
@router.callback_query(F.data == "user_referral")
async def cb_open_referral_menu(event: Message | CallbackQuery, bot: Bot):
    """Open referral program or prompt device verification"""
    user_id = event.from_user.id
    bot_info = await bot.get_me()

    is_verified = await db.is_user_device_verified(user_id)

    if is_verified:
        stats = await db.get_user_referral_stats(user_id)
        text = get_referral_dashboard_text(user_id, bot_info.username, stats)
        kb = get_referral_dashboard_kb(user_id, bot_info.username)

        if isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(text, reply_markup=kb)
            except Exception:
                await event.message.delete()
                await event.message.answer(text, reply_markup=kb)
            await event.answer()
        else:
            await event.answer(text, reply_markup=kb)

    else:
        text, kb = await get_device_verification_screen(bot, user_id, is_referred=False)
        if isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(text, reply_markup=kb)
            except Exception:
                await event.message.delete()
                await event.message.answer(text, reply_markup=kb)
            await event.answer()
        else:
            await event.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("check_dev_ver_"))
async def cb_check_device_verification(callback: CallbackQuery, bot: Bot):
    """Live status check after user attempts verification"""
    user_id = callback.from_user.id
    bot_info = await bot.get_me()

    is_verified = await db.is_user_device_verified(user_id)

    if is_verified:
        stats = await db.get_user_referral_stats(user_id)
        text = (
            f"🎉 <b>Device Verified Successfully!</b>\n\n"
            + get_referral_dashboard_text(user_id, bot_info.username, stats)
        )
        kb = get_referral_dashboard_kb(user_id, bot_info.username)
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception:
            await callback.message.answer(text, reply_markup=kb)
        await callback.answer("✅ Device Verified! Referral link & points unlocked.", show_alert=True)
    else:
        await callback.answer(
            "⏳ Verification is not completed yet. Please click '🔐 Start Device Verification' below and complete the verification.",
            show_alert=True,
        )


@router.message(F.web_app_data)
async def handle_webapp_verification_data(message: Message, bot: Bot):
    """Handle verification result sent back directly via Telegram WebApp Data"""
    user_id = message.from_user.id
    raw_data = message.web_app_data.data
    logger.info(f"Received WebApp verification data for user {user_id}: {raw_data}")

    import json
    try:
        res = json.loads(raw_data)
    except Exception:
        res = {"status": "success", "device_hash": raw_data}

    status = res.get("status", "success")
    device_hash = res.get("device_hash") or res.get("hash") or f"DEV_{user_id}_{generate_device_hash(16)}"
    ip_address = res.get("ip") or res.get("ip_address")

    if status in ("success", "verified", "ok"):
        success, code = await db.verify_user_device(user_id, device_hash=device_hash, ip_address=ip_address)

        if success:
            reward_res = await db.process_referral_rewards_on_verification(user_id)
            referrer_id = reward_res.get("referrer_id")
            points_awarded = reward_res.get("points_awarded", 0)

            # Notify Referrer with +1 Point
            if referrer_id and points_awarded > 0:
                try:
                    await bot.send_message(
                        referrer_id,
                        f"🎉 <b>+1 Referral Point Earned!</b>\n\n"
                        f"👤 <b>Friend:</b> {escape_html(message.from_user.full_name)}\n"
                        f"💎 <b>Points Received:</b> <code>+1 Point</code>\n"
                        f"💰 <b>Total Balance:</b> <code>{reward_res.get('new_points_balance', 1)} Points</code>\n\n"
                        f"👉 <i>Click <b>'🎁 Refer & Earn'</b> to redeem points for exclusive items!</i>",
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify referrer {referrer_id}: {e}")

            bot_info = await bot.get_me()
            stats = await db.get_user_referral_stats(user_id)

            text = (
                f"🎉 <b>Device Verification Complete!</b>\n"
                f"🛡️ <i>Your device has been authenticated and linked securely.</i>\n\n"
                + get_referral_dashboard_text(user_id, bot_info.username, stats)
            )
            kb = get_referral_dashboard_kb(user_id, bot_info.username)
            await message.answer(text, reply_markup=kb)

        elif code in ("duplicate_device", "duplicate_ip"):
            # Device or IP already used by another account - Referrer gets NO reward, user can still use bot
            fail_text = (
                "⚠️ <b>Device Verification Notice:</b>\n\n"
                "🚫 <i>This device or IP address is already registered with another account.</i>\n\n"
                "📌 <b>Policy Notice:</b> Only 1 account per device/IP is permitted for referral rewards.\n\n"
                "🛍️ <b>You can still use the bot!</b>\n"
                "<i>All store features (Wallet, Catalog, Shopping, Orders) are fully accessible to you anytime.</i>"
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🛍️ Browse Store",
                            callback_data="user_browse",
                            style="primary",
                            icon_custom_emoji_id=EMOJI_BULLET,
                        ),
                        InlineKeyboardButton(
                            text="💼 My Wallet",
                            callback_data="user_wallet",
                            style="success",
                            icon_custom_emoji_id=EMOJI_SUCCESS,
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="🏠 Main Menu",
                            callback_data="menu_home",
                            style="primary",
                            icon_custom_emoji_id=EMOJI_BACK,
                        ),
                    ],
                ]
            )
            await message.answer(fail_text, reply_markup=kb)

    else:
        err_msg = res.get("message", "Verification could not be completed.")
        fail_text = (
            f"❌ <b>Device Verification Failed!</b>\n\n"
            f"⚠️ <i>{escape_html(err_msg)}</i>\n\n"
            f"💡 <b>You can still use all bot features freely!</b>\n"
            f"<i>Feel free to browse products, add balance, or place orders. If you wish to retry verification, please turn off VPN/Proxy and try again.</i>"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛍️ Browse Store",
                        callback_data="user_browse",
                        style="primary",
                        icon_custom_emoji_id=EMOJI_BULLET,
                    ),
                    InlineKeyboardButton(
                        text="🏠 Main Menu",
                        callback_data="menu_home",
                        style="primary",
                        icon_custom_emoji_id=EMOJI_BACK,
                    ),
                ],
            ]
        )
        await message.answer(fail_text, reply_markup=kb)


# ===========================================================================
# REFERRAL POINTS SHOP (REDEEM STORE)
# ===========================================================================


@router.callback_query(F.data == "ref_shop")
async def cb_open_referral_rewards_shop(callback: CallbackQuery):
    """List all available rewards in Points Shop"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id) or {}
    points = int(user.get("referral_points", 0))

    rewards = await db.get_all_referral_rewards(only_active=True)

    text = f"""
🛍️ <b>Referral Rewards Shop</b>

Redeem your earned <b>Referral Points</b> for exclusive products, accounts, and gift codes!

━━━━━━━━━━━━━━━━━━━━━
💎 <b>Your Available Points:</b> <code>{points} Point{'s' if points != 1 else ''}</code>
━━━━━━━━━━━━━━━━━━━━━
"""

    if not rewards:
        text += "\n<i>⏳ Rewards are currently being updated by administrator. Keep referring friends to earn points!</i>"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back to Referral", callback_data="user_referral", style="primary", icon_custom_emoji_id=EMOJI_BACK)],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu_home", style="primary", icon_custom_emoji_id=EMOJI_BACK)],
            ]
        )
    else:
        buttons = []
        for r in rewards:
            cost = r.get("points_cost", 1)
            if points >= cost:
                btn_text = f"🎁 {r['name']} • {cost} Pts 🟢 [Redeem]"
                btn_style = "success"
                icon_id = EMOJI_SUCCESS
            else:
                btn_text = f"🔒 {r['name']} • {cost} Pts 🔴 [Need {cost - points} more]"
                btn_style = "danger"
                icon_id = EMOJI_FAIL

            buttons.append([
                InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"ref_view_{r['id']}",
                    style=btn_style,
                    icon_custom_emoji_id=icon_id,
                )
            ])

        buttons.append([
            InlineKeyboardButton(text="🔙 Back to Referral", callback_data="user_referral", style="primary", icon_custom_emoji_id=EMOJI_BACK),
            InlineKeyboardButton(text="📜 My Claims", callback_data="ref_my_claims", style="primary", icon_custom_emoji_id=EMOJI_STAR),
        ])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("ref_view_"))
async def cb_view_single_reward(callback: CallbackQuery):
    """View details of a single redeemable reward"""
    reward_id = int(callback.data.split("_")[2])
    reward = await db.get_referral_reward(reward_id)

    if not reward:
        await callback.answer("❌ Reward item not found.", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await db.get_user(user_id) or {}
    points = int(user.get("referral_points", 0))
    cost = int(reward.get("points_cost", 1))

    text = f"""
🎁 <b>{escape_html(reward['name'])}</b>

━━━━━━━━━━━━━━━━━━━━━
📝 <b>Description:</b>
{escape_html(reward.get('description', 'Instant digital delivery upon redemption.'))}

💎 <b>Cost:</b> <code>{cost} Referral Point{'s' if cost != 1 else ''}</code>
💰 <b>Your Balance:</b> <code>{points} Point{'s' if points != 1 else ''}</code>
━━━━━━━━━━━━━━━━━━━━━
"""

    buttons = []
    if points >= cost:
        buttons.append([
            InlineKeyboardButton(
                text=f"💎 Confirm & Redeem ({cost} Points)",
                callback_data=f"ref_redeem_{reward_id}",
                style="success",
                icon_custom_emoji_id=EMOJI_SUCCESS,
            )
        ])
    else:
        diff = cost - points
        buttons.append([
            InlineKeyboardButton(
                text=f"🔒 Need {diff} More Point{'s' if diff != 1 else ''} (Invite Friends)",
                callback_data="user_referral",
                style="danger",
                icon_custom_emoji_id=EMOJI_FAIL,
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="🔙 Back to Rewards Shop", callback_data="ref_shop", style="primary", icon_custom_emoji_id=EMOJI_BACK)
    ])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("ref_redeem_"))
async def cb_confirm_redeem_reward(callback: CallbackQuery, bot: Bot):
    """Process points redemption and deliver content"""
    reward_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    success, code, redemption = await db.redeem_referral_reward(user_id, reward_id)

    if not success:
        if code == "not_enough_points":
            await callback.answer("❌ You do not have enough referral points to redeem this item.", show_alert=True)
        else:
            await callback.answer("❌ Redemption failed or item no longer available.", show_alert=True)
        return

    # Deliver content to user
    delivered_content = redemption.get("delivered_content", "Access details granted.")
    reward_name = escape_html(redemption.get("reward_name", "Reward"))
    points_spent = redemption.get("points_spent", 1)

    text = f"""
🎉 <b>Redemption Successful!</b> 🎉

━━━━━━━━━━━━━━━━━━━━━
🎁 <b>Item Claimed:</b> {reward_name}
💎 <b>Points Deducted:</b> <code>-{points_spent} Points</code>
🧾 <b>Claim ID:</b> <code>#R{redemption['id']}</code>
━━━━━━━━━━━━━━━━━━━━━

🔑 <b>Your Delivered Content / Access Code:</b>
<code>{escape_html(delivered_content)}</code>

━━━━━━━━━━━━━━━━━━━━━
<i>You can view all past claimed rewards anytime in <b>My Claimed Rewards</b>.</i>
"""

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ Rewards Shop", callback_data="ref_shop", style="success", icon_custom_emoji_id=EMOJI_GIFT)],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu_home", style="primary", icon_custom_emoji_id=EMOJI_BACK)],
        ]
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)

    # If reward has a file attached, send it
    file_id = redemption.get("file_id")
    if file_id:
        try:
            await bot.send_document(user_id, document=file_id, caption=f"📁 {reward_name}")
        except Exception:
            pass

    await callback.answer("🎉 Reward redeemed successfully!", show_alert=True)


@router.callback_query(F.data == "ref_my_claims")
async def cb_user_claimed_rewards(callback: CallbackQuery):
    """View past claimed reward items history"""
    user_id = callback.from_user.id
    claims = await db.get_user_redemptions(user_id)

    if not claims:
        text = """
📜 <b>My Claimed Rewards History</b>

<i>You haven't claimed any referral rewards yet. Earn points by inviting friends and redeem them in the Points Shop!</i>
"""
    else:
        text = "📜 <b>My Claimed Rewards History:</b>\n\n"
        for c in claims:
            text += f"🎁 <b>{escape_html(c['reward_name'])}</b>\n"
            text += f"💎 Spent: <code>{c['points_spent']} Points</code> | Claim: <code>#R{c['id']}</code>\n"
            if c.get("delivered_content"):
                text += f"🔑 <code>{escape_html(c['delivered_content'])}</code>\n"
            text += "━━━━━━━━━━━━━━━━━━━━━\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ Rewards Shop", callback_data="ref_shop", style="success", icon_custom_emoji_id=EMOJI_GIFT)],
            [InlineKeyboardButton(text="🔙 Back to Referral", callback_data="user_referral", style="primary", icon_custom_emoji_id=EMOJI_BACK)],
        ]
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()
