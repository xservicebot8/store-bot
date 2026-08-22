"""
Helper utilities for formatting, escaping, and message templates
"""

import html
from datetime import datetime
from typing import Optional, List, Dict, Any


def format_currency(amount: float) -> str:
    """Format number to Indian Rupee representation"""
    return f"₹{amount:,.2f}"


def escape_html(text: Optional[str]) -> str:
    """Safely escape HTML entities"""
    if text is None:
        return ""
    return html.escape(str(text))


def format_timestamp(ts: Any) -> str:
    """Format timestamp into readable date & time"""
    if not ts:
        return "N/A"
    try:
        if isinstance(ts, str):
            # Parse SQLite timestamp
            clean_ts = ts.replace("T", " ").split(".")[0]
            dt = datetime.fromisoformat(clean_ts)
        elif isinstance(ts, datetime):
            dt = ts
        else:
            return str(ts)
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return str(ts)


def truncate_text(text: str, max_len: int = 100) -> str:
    """Truncate text with ellipsis if too long"""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


# Premium Emoji Constants (Telebot / Telegram Custom Emojis)
EMOJI_BULLET = "5381813206954025989"
EMOJI_STAR = "5258185631355378853"
EMOJI_BACK = "4997256682972121121"
EMOJI_NEXT = "6301076413210429176"
EMOJI_GIFT = "5274682732159636249"
EMOJI_USER = "5316727448644103237"
EMOJI_SUCCESS = "5260341314095947411"
EMOJI_FAIL = "5258318620722733379"


def apply_premium_emojis(text: str) -> str:
    """Replace standard emojis in text with Telegram Premium <tg-emoji> tags"""
    if not text:
        return ""
    replacements = [
        ("✨", f'<tg-emoji emoji-id="{EMOJI_BULLET}">✨</tg-emoji>'),
        ("⭐", f'<tg-emoji emoji-id="{EMOJI_STAR}">⭐</tg-emoji>'),
        ("🎁", f'<tg-emoji emoji-id="{EMOJI_GIFT}">🎁</tg-emoji>'),
        ("👤", f'<tg-emoji emoji-id="{EMOJI_USER}">👤</tg-emoji>'),
        ("✅", f'<tg-emoji emoji-id="{EMOJI_SUCCESS}">✅</tg-emoji>'),
        ("❌", f'<tg-emoji emoji-id="{EMOJI_FAIL}">❌</tg-emoji>'),
        ("⬅️", f'<tg-emoji emoji-id="{EMOJI_BACK}">⬅️</tg-emoji>'),
        ("➡️", f'<tg-emoji emoji-id="{EMOJI_NEXT}">➡️</tg-emoji>'),
    ]
    for old_emoji, new_tag in replacements:
        text = text.replace(old_emoji, new_tag)
    return text


def get_delivery_badge(delivery_type: str) -> str:
    """Return icon badge for delivery type"""
    if delivery_type in ("file_stock", "file_stocks"):
        return "📁 Unique Files Stock (1 File per Buyer)"
    elif delivery_type in ("line_stock", "stock"):
        return "⚡ Line-by-Line Stock (1 Line per Buyer)"
    elif delivery_type in ("static_file", "file"):
        return "♾️ Universal File (Same for All)"
    elif delivery_type in ("static_text", "manual"):
        return "♾️ Universal Text / Code (Same for All)"
    else:
        return "⚡ Instant Auto-Delivery"

