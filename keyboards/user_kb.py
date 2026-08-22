"""
Inline Keyboards for Bot Users (With Native Telegram Colored Button Styles & Custom Emoji IDs)
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


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Generate colorful main menu with native Telegram button styles and custom emoji icons"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🛍️ ━━ BROWSE STORE ━━ 🛍️",
            callback_data="user_browse",
            style="primary",
            icon_custom_emoji_id=EMOJI_BULLET,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="💼 My Wallet",
            callback_data="user_wallet",
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        ),
        InlineKeyboardButton(
            text="📦 My Orders",
            callback_data="user_orders",
            style="primary",
            icon_custom_emoji_id=EMOJI_BULLET,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="👤 My Profile",
            callback_data="user_profile",
            style="primary",
            icon_custom_emoji_id=EMOJI_USER,
        ),
        InlineKeyboardButton(
            text="🎁 Refer & Earn",
            callback_data="user_referral",
            style="primary",
            icon_custom_emoji_id=EMOJI_GIFT,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🎟️ Promo Code",
            callback_data="user_apply_promo",
            style="primary",
            icon_custom_emoji_id=EMOJI_GIFT,
        ),
        InlineKeyboardButton(
            text="📞 24/7 Support",
            callback_data="user_support",
            style="primary",
            icon_custom_emoji_id=EMOJI_BULLET,
        ),
    )

    if is_admin:
        builder.row(
            InlineKeyboardButton(
                text="👑 ⚡ ADMIN DASHBOARD ⚡ 👑",
                callback_data="admin_dashboard",
                style="success",
                icon_custom_emoji_id=EMOJI_STAR,
            )
        )

    return builder.as_markup()


def categories_kb(categories: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """List all store categories with product count"""
    builder = InlineKeyboardBuilder()

    for cat in categories:
        count = cat.get("product_count", 0)
        builder.row(
            InlineKeyboardButton(
                text=f"📁 {cat['name']} ({count})",
                callback_data=f"cat_{cat['id']}",
                style="primary",
                icon_custom_emoji_id=EMOJI_BULLET,
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🏠 Main Menu",
            callback_data="menu_home",
            style="primary",
            icon_custom_emoji_id=EMOJI_BACK,
        )
    )
    return builder.as_markup()


def products_kb(products: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """List all store products with Green for in-stock and Red for out-of-stock"""
    builder = InlineKeyboardBuilder()

    for prod in products:
        stock = prod.get("stock_count", 0)
        price_str = format_currency(prod["price"])
        dtype = prod.get("delivery_type", "line_stock")

        if dtype in ("static_file", "static_text", "file", "manual"):
            btn_text = f"💎 {prod['name']} • {price_str} 🟢 [Available]"
            btn_style = "success"
            icon_id = EMOJI_STAR
        elif stock > 0:
            btn_text = f"💎 {prod['name']} • {price_str} 🟢 [{stock} in stock]"
            btn_style = "success"
            icon_id = EMOJI_SUCCESS
        else:
            btn_text = f"❌ {prod['name']} • {price_str} 🔴 [SOLD OUT]"
            btn_style = "danger"
            icon_id = EMOJI_FAIL

        builder.row(
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"prod_{prod['id']}",
                style=btn_style,
                icon_custom_emoji_id=icon_id,
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🏠 Main Menu",
            callback_data="menu_home",
            style="primary",
            icon_custom_emoji_id=EMOJI_BACK,
        ),
    )
    return builder.as_markup()


def product_detail_kb(product: Dict[str, Any], stock_count: int) -> InlineKeyboardMarkup:
    """Product detail action buttons with Green/Red colored styles"""
    builder = InlineKeyboardBuilder()
    prod_id = product["id"]
    delivery_type = product.get("delivery_type", "line_stock")

    is_static = delivery_type in ("static_file", "static_text", "file", "manual")

    if is_static or stock_count > 0:
        builder.row(
            InlineKeyboardButton(
                text=f"🛒 BUY NOW • {format_currency(product['price'])} ⚡",
                callback_data=f"buy_{prod_id}",
                style="success",
                icon_custom_emoji_id=EMOJI_SUCCESS,
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="🚫 CURRENTLY OUT OF STOCK",
                callback_data="noop",
                style="danger",
                icon_custom_emoji_id=EMOJI_FAIL,
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Store",
            callback_data="user_browse",
            style="primary",
            icon_custom_emoji_id=EMOJI_BACK,
        ),
        InlineKeyboardButton(
            text="🏠 Menu",
            callback_data="menu_home",
            style="primary",
            icon_custom_emoji_id=EMOJI_BACK,
        ),
    )
    return builder.as_markup()


def quantity_selector_kb(
    product_id: int, quantity: int, max_stock: int, unit_price: float, category_id: int = 1
) -> InlineKeyboardMarkup:
    """Interactive quantity selector with Red (-), Blue (Qty), Green (+) styles"""
    builder = InlineKeyboardBuilder()
    total = quantity * unit_price

    minus_cb = f"qty_{product_id}_{max(1, quantity - 1)}"
    plus_cb = f"qty_{product_id}_{min(max_stock, quantity + 1)}"

    builder.row(
        InlineKeyboardButton(text="➖ 1", callback_data=minus_cb, style="danger", icon_custom_emoji_id=EMOJI_FAIL),
        InlineKeyboardButton(text=f"🔢 Qty: {quantity}", callback_data="noop", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
        InlineKeyboardButton(text="➕ 1", callback_data=plus_cb, style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
    )
    builder.row(
        InlineKeyboardButton(
            text=f"💳 Proceed to Payment ({format_currency(total)})",
            callback_data=f"checkout_{product_id}_{quantity}",
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Back",
            callback_data=f"prod_{product_id}",
            style="danger",
            icon_custom_emoji_id=EMOJI_BACK,
        )
    )
    return builder.as_markup()


def checkout_payment_kb(
    order_id: int,
    product_id: int,
    final_amount: float,
    user_balance: float,
) -> InlineKeyboardMarkup:
    """Payment method selection with Green/Blue/Red colored styles"""
    builder = InlineKeyboardBuilder()

    if user_balance >= final_amount:
        builder.row(
            InlineKeyboardButton(
                text=f"💼 Pay with Wallet ({format_currency(user_balance)})",
                callback_data=f"pay_wallet_{order_id}",
                style="success",
                icon_custom_emoji_id=EMOJI_SUCCESS,
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=f"💼 Wallet Balance Low ({format_currency(user_balance)})",
                callback_data=f"topup_and_pay_{order_id}",
                style="danger",
                icon_custom_emoji_id=EMOJI_FAIL,
            )
        )

    builder.row(
        InlineKeyboardButton(
            text=f"⚡ Pay with UPI QR ({format_currency(final_amount)})",
            callback_data=f"pay_qr_{order_id}",
            style="primary",
            icon_custom_emoji_id=EMOJI_BULLET,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🎟️ Apply Promo",
            callback_data=f"apply_coupon_{order_id}",
            style="primary",
            icon_custom_emoji_id=EMOJI_GIFT,
        ),
        InlineKeyboardButton(
            text="❌ Cancel Order",
            callback_data=f"cancel_order_{order_id}",
            style="danger",
            icon_custom_emoji_id=EMOJI_FAIL,
        ),
    )
    return builder.as_markup()


def payment_qr_kb(order_id: int, upi_url: str = "", amount: float = 0.0) -> InlineKeyboardMarkup:
    """Payment screen with vibrant action buttons"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔄 Check Payment Status",
            callback_data=f"check_pay_{order_id}",
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔢 Submit 12-Digit UTR",
            callback_data=f"submit_utr_{order_id}",
            style="primary",
            icon_custom_emoji_id=EMOJI_BULLET,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Cancel Order",
            callback_data=f"cancel_order_{order_id}",
            style="danger",
            icon_custom_emoji_id=EMOJI_FAIL,
        ),
        InlineKeyboardButton(
            text="📞 Support",
            callback_data="user_support",
            style="primary",
            icon_custom_emoji_id=EMOJI_BULLET,
        ),
    )
    return builder.as_markup()


def wallet_menu_kb() -> InlineKeyboardMarkup:
    """Wallet options with color cues"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="➕ Add Balance (UPI QR)",
            callback_data="wallet_deposit",
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        ),
        InlineKeyboardButton(
            text="📜 History",
            callback_data="wallet_history",
            style="primary",
            icon_custom_emoji_id=EMOJI_BULLET,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🛍️ Shop Products",
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
    )
    return builder.as_markup()


def deposit_amount_presets_kb() -> InlineKeyboardMarkup:
    """Deposit quick amount presets in Blue & Green"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="₹50", callback_data="deposit_amt_50", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
        InlineKeyboardButton(text="₹100", callback_data="deposit_amt_100", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
        InlineKeyboardButton(text="₹250", callback_data="deposit_amt_250", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
    )
    builder.row(
        InlineKeyboardButton(text="₹500", callback_data="deposit_amt_500", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
        InlineKeyboardButton(text="₹1,000", callback_data="deposit_amt_1000", style="success", icon_custom_emoji_id=EMOJI_SUCCESS),
        InlineKeyboardButton(text="✏️ Custom", callback_data="deposit_custom", style="primary", icon_custom_emoji_id=EMOJI_BULLET),
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Wallet",
            callback_data="user_wallet",
            style="danger",
            icon_custom_emoji_id=EMOJI_BACK,
        )
    )
    return builder.as_markup()


def deposit_qr_kb(deposit_id: int, upi_url: str = "") -> InlineKeyboardMarkup:
    """Deposit QR screen actions"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔄 Check Deposit Status",
            callback_data=f"check_dep_{deposit_id}",
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔢 Submit 12-Digit UTR",
            callback_data=f"submit_dep_utr_{deposit_id}",
            style="primary",
            icon_custom_emoji_id=EMOJI_BULLET,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Wallet",
            callback_data="user_wallet",
            style="danger",
            icon_custom_emoji_id=EMOJI_BACK,
        )
    )
    return builder.as_markup()


def orders_list_kb(orders: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """List past orders with status color styles"""
    builder = InlineKeyboardBuilder()

    for o in orders:
        if o["status"] in ("delivered", "paid"):
            status_style = "success"
            status_emoji = "✅"
            icon_id = EMOJI_SUCCESS
        elif o["status"] == "pending":
            status_style = "primary"
            status_emoji = "⏳"
            icon_id = EMOJI_BULLET
        else:
            status_style = "danger"
            status_emoji = "❌"
            icon_id = EMOJI_FAIL

        builder.row(
            InlineKeyboardButton(
                text=f"{status_emoji} #{o['order_code']} • {o['product_name']} ({format_currency(o['final_amount'])})",
                callback_data=f"view_order_{o['id']}",
                style=status_style,
                icon_custom_emoji_id=icon_id,
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🏠 Main Menu",
            callback_data="menu_home",
            style="primary",
            icon_custom_emoji_id=EMOJI_BACK,
        )
    )
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    """Simple Back to Main Menu keyboard"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🏠 Main Menu",
            callback_data="menu_home",
            style="primary",
            icon_custom_emoji_id=EMOJI_BACK,
        )
    )
    return builder.as_markup()
