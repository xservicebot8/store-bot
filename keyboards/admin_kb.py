"""
Inline Keyboards for Admin Panel (With Native Telegram Button Styles & Custom Emoji IDs)
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict, Any

from utils.helpers import (
    format_currency,
    EMOJI_BULLET,
    EMOJI_STAR,
    EMOJI_BACK,
    EMOJI_NEXT,
    EMOJI_GIFT,
    EMOJI_USER,
    EMOJI_SUCCESS,
    EMOJI_FAIL,
)


def admin_main_kb() -> InlineKeyboardMarkup:
    """Admin Dashboard navigation with native colored button styles and custom emoji icons"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📊 Analytics & Sales",
            callback_data="adm_stats",
            style="primary",
            icon_custom_emoji_id=EMOJI_STAR,
        ),
        InlineKeyboardButton(
            text="📦 Products & Stock",
            callback_data="adm_products_menu",
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 All Orders",
            callback_data="adm_orders_menu",
            style="primary",
            icon_custom_emoji_id=EMOJI_BULLET,
        ),
        InlineKeyboardButton(
            text="👥 Users & Balances",
            callback_data="adm_users_menu",
            style="primary",
            icon_custom_emoji_id=EMOJI_USER,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🎟️ Coupons / Promos",
            callback_data="adm_coupons_menu",
            style="primary",
            icon_custom_emoji_id=EMOJI_GIFT,
        ),
        InlineKeyboardButton(
            text="🎁 Referral Program",
            callback_data="adm_ref_settings",
            style="primary",
            icon_custom_emoji_id=EMOJI_GIFT,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📢 Broadcast Message",
            callback_data="adm_broadcast",
            style="primary",
            icon_custom_emoji_id=EMOJI_BULLET,
        ),
        InlineKeyboardButton(
            text="💾 Backup Database",
            callback_data="adm_backup_db",
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Store & Payment Settings",
            callback_data="adm_settings",
            style="primary",
            icon_custom_emoji_id=EMOJI_BULLET,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 User Store",
            callback_data="menu_home",
            style="primary",
            icon_custom_emoji_id=EMOJI_BACK,
        ),
    )
    return builder.as_markup()


def admin_referral_settings_kb(settings: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Referral system controls for admin"""
    builder = InlineKeyboardBuilder()

    join_text = "🟢 Join Reward: ON" if settings.get("join_enabled") else "🔴 Join Reward: OFF"
    join_style = "success" if settings.get("join_enabled") else "danger"
    join_icon = EMOJI_SUCCESS if settings.get("join_enabled") else EMOJI_FAIL

    purch_text = "🟢 Purchase Cashback: ON" if settings.get("purchase_enabled") else "🔴 Purchase Cashback: OFF"
    purch_style = "success" if settings.get("purchase_enabled") else "danger"
    purch_icon = EMOJI_SUCCESS if settings.get("purchase_enabled") else EMOJI_FAIL

    builder.row(
        InlineKeyboardButton(text=join_text, callback_data="adm_toggle_ref_join", style=join_style, icon_custom_emoji_id=join_icon),
        InlineKeyboardButton(text=f"💰 Set Reward (₹{settings.get('join_amount', 5.0):g})", callback_data="adm_set_ref_join_amt", style="primary", icon_custom_emoji_id=EMOJI_GIFT),
    )
    builder.row(
        InlineKeyboardButton(text=purch_text, callback_data="adm_toggle_ref_purch", style=purch_style, icon_custom_emoji_id=purch_icon),
        InlineKeyboardButton(text=f"📊 Set Cashback ({settings.get('purchase_percent', 5.0):g}%)", callback_data="adm_set_ref_purch_pct", style="primary", icon_custom_emoji_id=EMOJI_GIFT),
    )
    builder.row(
        InlineKeyboardButton(text=f"📢 Channel: {settings.get('channel', '@StoreChannel')}", callback_data="adm_set_ref_channel", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
    )
    builder.row(
        InlineKeyboardButton(
            text="🎁 Manage Points Rewards Shop",
            callback_data="adm_ref_rewards_menu",
            style="success",
            icon_custom_emoji_id=EMOJI_GIFT,
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Admin Dashboard", callback_data="admin_dashboard", style="primary", icon_custom_emoji_id=EMOJI_BACK)
    )
    return builder.as_markup()


def admin_referral_rewards_list_kb(rewards: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """List of all redeemable rewards in admin panel"""
    builder = InlineKeyboardBuilder()

    for r in rewards:
        cost = r.get("points_cost", 1)
        builder.row(
            InlineKeyboardButton(
                text=f"🎁 {r['name']} • {cost} Pts (Claimed: {r.get('redeemed_count', 0)})",
                callback_data=f"adm_view_ref_rew_{r['id']}",
                style="primary",
                icon_custom_emoji_id=EMOJI_GIFT,
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="➕ Add New Reward Item",
            callback_data="adm_add_ref_reward",
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Referral Settings",
            callback_data="adm_ref_settings",
            style="primary",
            icon_custom_emoji_id=EMOJI_BACK,
        )
    )
    return builder.as_markup()


def admin_referral_reward_detail_kb(reward_id: int) -> InlineKeyboardMarkup:
    """Detail actions for a single referral reward in admin panel"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🗑️ Delete Reward Item",
            callback_data=f"adm_del_ref_rew_{reward_id}",
            style="danger",
            icon_custom_emoji_id=EMOJI_FAIL,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Rewards Shop",
            callback_data="adm_ref_rewards_menu",
            style="primary",
            icon_custom_emoji_id=EMOJI_BACK,
        )
    )
    return builder.as_markup()


def admin_products_list_kb(products: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """List all products for admin with green/red colored styles"""
    builder = InlineKeyboardBuilder()

    for p in products:
        stock = p.get("stock_count", 0)
        is_active = bool(p.get("is_active", 1))

        if not is_active:
            btn_text = f"🔴 {p['name']} • {format_currency(p['price'])} [HIDDEN]"
            btn_style = "danger"
            icon_id = EMOJI_FAIL
        elif p.get("delivery_type") == "line_stock" and stock <= 0:
            btn_text = f"❌ {p['name']} • {format_currency(p['price'])} [SOLD OUT]"
            btn_style = "danger"
            icon_id = EMOJI_FAIL
        else:
            stock_str = f"[{stock} in stock]" if p.get("delivery_type") in ("line_stock", "file_stock", "stock") else "[Universal]"
            btn_text = f"💎 {p['name']} • {format_currency(p['price'])} {stock_str}"
            btn_style = "success"
            icon_id = EMOJI_SUCCESS

        builder.row(
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"adm_prod_{p['id']}",
                style=btn_style,
                icon_custom_emoji_id=icon_id,
            )
        )

    builder.row(
        InlineKeyboardButton(text="➕ Add New Product", callback_data="adm_add_prod", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Admin Dashboard", callback_data="admin_dashboard", style="primary", icon_custom_emoji_id=EMOJI_BACK),
    )
    return builder.as_markup()


def admin_product_detail_kb(product: Dict[str, Any], stock_count: int) -> InlineKeyboardMarkup:
    """Manage single product with 1-click price increase/decrease and stock controls"""
    prod_id = product["id"]
    delivery_type = product.get("delivery_type", "line_stock")
    is_active = bool(product.get("is_active", 1))

    builder = InlineKeyboardBuilder()

    # Row 1: Quick 1-Click Price Adjustment
    builder.row(
        InlineKeyboardButton(text="➖ ₹10", callback_data=f"adm_pr_adj_{prod_id}_-10", style="danger", icon_custom_emoji_id=EMOJI_FAIL),
        InlineKeyboardButton(text="➖ ₹50", callback_data=f"adm_pr_adj_{prod_id}_-50", style="danger", icon_custom_emoji_id=EMOJI_FAIL),
        InlineKeyboardButton(text="➕ ₹10", callback_data=f"adm_pr_adj_{prod_id}_10", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
        InlineKeyboardButton(text="➕ ₹50", callback_data=f"adm_pr_adj_{prod_id}_50", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
    )

    # Row 2: Custom Price & Visibility Switch
    vis_text = "🟢 Status: Active (Shown)" if is_active else "🔴 Status: Inactive (Hidden)"
    vis_style = "success" if is_active else "danger"
    vis_icon = EMOJI_SUCCESS if is_active else EMOJI_FAIL
    builder.row(
        InlineKeyboardButton(text="✏️ Custom Price", callback_data=f"adm_edit_price_{prod_id}", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
        InlineKeyboardButton(text=vis_text, callback_data=f"adm_toggle_prod_{prod_id}", style=vis_style, icon_custom_emoji_id=vis_icon),
    )

    # Row 3: Stock Management according to delivery type
    if delivery_type in ("line_stock", "file_stock", "stock"):
        add_btn_text = "📁 Add Files Stock" if delivery_type == "file_stock" else "⚡ Add Stock (Bulk)"
        builder.row(
            InlineKeyboardButton(text=add_btn_text, callback_data=f"adm_stock_add_{prod_id}", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
            InlineKeyboardButton(text=f"📋 View ({stock_count})", callback_data=f"adm_stock_view_{prod_id}", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
            InlineKeyboardButton(text="📥 Export .txt", callback_data=f"adm_stock_export_{prod_id}", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
        )
    elif delivery_type in ("static_file", "file"):
        builder.row(
            InlineKeyboardButton(text="📁 Change / Upload File", callback_data=f"adm_edit_file_{prod_id}", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
        )
    elif delivery_type in ("static_text", "manual"):
        builder.row(
            InlineKeyboardButton(text="📝 Edit Universal Code/Text", callback_data=f"adm_edit_static_txt_{prod_id}", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
        )

    # Row 4: Sold History & Content Edit
    builder.row(
        InlineKeyboardButton(text="📜 Sold History", callback_data=f"adm_stock_sold_{prod_id}", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
        InlineKeyboardButton(text="✏️ Title", callback_data=f"adm_edit_name_{prod_id}", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
        InlineKeyboardButton(text="✏️ Desc", callback_data=f"adm_edit_desc_{prod_id}", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
    )

    # Row 5: Delete & Back
    builder.row(
        InlineKeyboardButton(text="🗑️ Delete Product", callback_data=f"adm_del_prod_{prod_id}", style="danger", icon_custom_emoji_id=EMOJI_FAIL),
        InlineKeyboardButton(text="🔙 Back to Products", callback_data="adm_products_menu", style="primary", icon_custom_emoji_id=EMOJI_BACK),
    )
    return builder.as_markup()


def admin_orders_filter_kb(filter_type: str = "all") -> InlineKeyboardMarkup:
    """Filter orders in admin panel with colored styles"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏳ Pending", callback_data="adm_orders_pending", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
        InlineKeyboardButton(text="✅ Paid / Delivered", callback_data="adm_orders_paid", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
        InlineKeyboardButton(text="📦 All Orders", callback_data="adm_orders_all", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Admin Dashboard", callback_data="admin_dashboard", style="primary", icon_custom_emoji_id=EMOJI_BACK)
    )
    return builder.as_markup()


def admin_order_actions_kb(order: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Actions on single order"""
    builder = InlineKeyboardBuilder()
    order_id = order["id"]
    status = order.get("status")

    if status == "pending":
        builder.row(
            InlineKeyboardButton(text="✅ Force Approve & Deliver", callback_data=f"adm_approve_order_{order_id}", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
            InlineKeyboardButton(text="❌ Cancel Order", callback_data=f"adm_cancel_order_{order_id}", style="danger", icon_custom_emoji_id=EMOJI_FAIL),
        )
    elif status in ("paid", "delivered"):
        builder.row(
            InlineKeyboardButton(text="↩️ Refund to Wallet", callback_data=f"adm_refund_order_{order_id}", style="danger", icon_custom_emoji_id=EMOJI_FAIL)
        )

    builder.row(
        InlineKeyboardButton(text="🔙 Back to Orders", callback_data="adm_orders_menu", style="primary", icon_custom_emoji_id=EMOJI_BACK)
    )
    return builder.as_markup()


def admin_user_actions_kb(user: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Actions on a searched user with color styles"""
    builder = InlineKeyboardBuilder()
    user_id = user["user_id"]
    is_banned = bool(user.get("is_banned", 0))

    builder.row(
        InlineKeyboardButton(text="➕ Add Balance", callback_data=f"adm_usr_addbal_{user_id}", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
        InlineKeyboardButton(text="➖ Deduct Balance", callback_data=f"adm_usr_dedbal_{user_id}", style="danger", icon_custom_emoji_id=EMOJI_FAIL),
    )
    builder.row(
        InlineKeyboardButton(
            text="🔓 Unban User" if is_banned else "🚫 Ban User",
            callback_data=f"adm_usr_toggleban_{user_id}",
            style="success" if is_banned else "danger",
            icon_custom_emoji_id=EMOJI_SUCCESS if is_banned else EMOJI_FAIL,
        ),
        InlineKeyboardButton(text="📦 User Orders", callback_data=f"adm_usr_orders_{user_id}", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Users Menu", callback_data="adm_users_menu", style="primary", icon_custom_emoji_id=EMOJI_BACK)
    )
    return builder.as_markup()


def admin_coupons_kb(coupons: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Coupon management list"""
    builder = InlineKeyboardBuilder()

    for c in coupons:
        val_str = f"{c['discount_value']}%" if c["discount_type"] == "percent" else f"₹{c['discount_value']}"
        builder.row(
            InlineKeyboardButton(
                text=f"🎟️ {c['code']} ({val_str} off) [Used: {c['used_count']}]",
                callback_data=f"adm_view_coupon_{c['id']}",
                style="primary",
                icon_custom_emoji_id=EMOJI_GIFT,
            )
        )

    builder.row(
        InlineKeyboardButton(text="➕ Create Coupon", callback_data="adm_add_coupon", style="success", icon_custom_emoji_id=EMOJI_SUCCESS)
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Admin Dashboard", callback_data="admin_dashboard", style="primary", icon_custom_emoji_id=EMOJI_BACK)
    )
    return builder.as_markup()


def admin_settings_kb(is_paytm_valid: bool = False) -> InlineKeyboardMarkup:
    """Settings, Min Deposit, and Paytm configuration"""
    import config
    builder = InlineKeyboardBuilder()

    status_icon = "🟢 Connected" if is_paytm_valid else "🔴 Needs Attention"
    paytm_style = "success" if is_paytm_valid else "danger"
    paytm_icon = EMOJI_SUCCESS if is_paytm_valid else EMOJI_FAIL

    builder.row(
        InlineKeyboardButton(text=f"🔍 Paytm Health ({status_icon})", callback_data="adm_test_paytm", style=paytm_style, icon_custom_emoji_id=paytm_icon)
    )
    builder.row(
        InlineKeyboardButton(text=f"💰 Min Deposit: ₹{config.MIN_DEPOSIT:g}", callback_data="adm_set_min_deposit", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
        InlineKeyboardButton(text="💳 Change UPI ID / Name", callback_data="adm_set_upi", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
    )
    builder.row(
        InlineKeyboardButton(text="📞 Support & Channel", callback_data="adm_set_social", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
        InlineKeyboardButton(text="🔑 Update Cookies", callback_data="adm_set_paytm_cookies", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Referral Settings", callback_data="adm_ref_settings", style="primary", icon_custom_emoji_id=EMOJI_GIFT),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Admin Dashboard", callback_data="admin_dashboard", style="primary", icon_custom_emoji_id=EMOJI_BACK)
    )
    return builder.as_markup()
