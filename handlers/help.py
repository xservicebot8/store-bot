"""
Customer Support Ticket Desk & Admin Ticket Resolution System
Allows users to raise tickets, attach screenshots/details, receive admin responses, and maintain full conversation threads.
"""

from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database.db import db
from keyboards.user_kb import (
    ticket_hub_kb,
    ticket_topics_kb,
    user_tickets_list_kb,
    ticket_detail_kb,
    main_menu_kb,
)
from keyboards.admin_kb import (
    admin_tickets_list_kb,
    admin_ticket_detail_kb,
    admin_ticket_notify_kb,
)
from utils.states import UserTicketStates, AdminTicketStates
from utils.helpers import escape_html, format_timestamp
import config

router = Router(name="help_router")


def format_ticket_thread(ticket: dict, is_admin: bool = False) -> str:
    """Format readable message history for a ticket"""
    status = ticket.get("status", "open")
    if status == "answered":
        status_badge = "🟢 <b>Replied by Support</b>"
    elif status == "open":
        status_badge = "🟡 <b>Open (Waiting for Support)</b>"
    else:
        status_badge = "⚪ <b>Closed</b>"

    code = ticket.get("ticket_code", f"#{ticket['id']}")
    subject = escape_html(ticket.get("subject", "General Support"))
    user_name = escape_html(ticket.get("full_name", "Customer"))
    created_date = format_timestamp(ticket.get("created_at"))

    text = f"""
🎫 <b>Ticket: <code>#{code}</code></b> • {status_badge}

👤 <b>User:</b> {user_name} (ID: <code>{ticket.get('user_id')}</code>)
🏷️ <b>Topic:</b> {subject}
📅 <b>Created:</b> {created_date}
━━━━━━━━━━━━━━━━━━━━━
💬 <b>Conversation Thread:</b>
"""
    messages = ticket.get("messages", [])
    if not messages:
        text += "\n<i>No messages in this ticket.</i>"
    else:
        for m in messages:
            sender_tag = "👑 <b>Support Team</b>" if m.get("sender") == "admin" else f"👤 <b>{escape_html(m.get('sender_name', 'Customer'))}</b>"
            m_time = format_timestamp(m.get("created_at"))
            m_text = escape_html(m.get("text", ""))
            has_photo = " <i>[📷 Photo Attached]</i>" if m.get("photo_id") else ""

            text += f"\n{sender_tag} <tg-spoiler>({m_time})</tg-spoiler>:{has_photo}\n{m_text}\n"

    text += "\n━━━━━━━━━━━━━━━━━━━━━"
    return text


# ===========================================================================
# USER TICKET HUB & CREATION FLOW
# ===========================================================================


@router.message(Command("support", "ticket", "help"))
@router.callback_query(F.data == "user_support")
async def cb_user_support_hub(event: Message | CallbackQuery, state: Optional[FSMContext] = None):
    """Display customer support ticket hub with active ticket counters"""
    if state:
        await state.clear()

    user_id = event.from_user.id
    stats = await db.get_tickets_stats(user_id=user_id)
    open_count = stats.get("open", 0)
    closed_count = stats.get("closed", 0)

    text = f"""
🎫 <b>Customer Support & Help Desk</b>

Need assistance with a payment, wallet deposit, product keys, or have a custom question?
<b>Raise a support ticket</b> below and our team will resolve it for you!

━━━━━━━━━━━━━━━━━━━━━
📊 <b>Your Support Tickets:</b>
• 🟡 <b>Active / Open:</b> <code>{open_count}</code>
• ⚪ <b>Resolved / Closed:</b> <code>{closed_count}</code>
━━━━━━━━━━━━━━━━━━━━━

<i>Click <b>'➕ Raise New Ticket'</b> below to submit your issue:</i>
"""
    kb = ticket_hub_kb(open_count=open_count, channel_username=config.CHANNEL_USERNAME)

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=kb)
        except Exception:
            await event.message.delete()
            await event.message.answer(text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb)


@router.callback_query(F.data == "ticket_new")
async def cb_start_new_ticket(callback: CallbackQuery, state: FSMContext):
    """Prompt user to select ticket category topic"""
    await state.clear()
    text = """
🎫 <b>Raise a Support Ticket • Step 1/2</b>

<i>Please select the category that best describes your issue:</i>
"""
    await callback.message.edit_text(text, reply_markup=ticket_topics_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("tkt_topic_"))
async def cb_select_ticket_topic(callback: CallbackQuery, state: FSMContext):
    """Store topic and prompt user to enter problem description"""
    topic_key = callback.data.replace("tkt_topic_", "")
    topics_map = {
        "payment": "💳 Payment / Wallet Deposit Issue",
        "order": "📦 Order / Product Key Issue",
        "general": "💬 General Question / Account",
    }
    subject = topics_map.get(topic_key, "General Support")
    await state.update_data(subject=subject)
    await state.set_state(UserTicketStates.waiting_for_message)

    text = f"""
🎫 <b>Raise a Support Ticket • Step 2/2</b>

🏷️ <b>Selected Topic:</b> {subject}

━━━━━━━━━━━━━━━━━━━━━
📝 <b>Please describe your issue or question below:</b>
• Provide details like <b>Order Code</b>, <b>UTR Number</b>, or issue description.
• You can also send a <b>Screenshot / Photo</b> with your message!
━━━━━━━━━━━━━━━━━━━━━

👉 <i>Type and send your message now:</i>
"""
    await callback.message.edit_text(text)
    await callback.answer()


@router.message(UserTicketStates.waiting_for_message)
async def process_user_ticket_creation(message: Message, state: FSMContext, bot: Bot):
    """Create ticket in DB and notify admins"""
    data = await state.get_data()
    subject = data.get("subject", "General Support")
    await state.clear()

    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else None
    full_name = message.from_user.full_name or "Valued Customer"

    msg_text = message.text or message.caption or "Issue details provided."
    photo_id = message.photo[-1].file_id if message.photo else None

    # Create ticket in DB
    ticket = await db.create_ticket(
        user_id=user_id,
        username=username,
        full_name=full_name,
        subject=subject,
        message_text=msg_text,
        photo_id=photo_id,
    )

    ticket_code = ticket.get("ticket_code", f"#{ticket['id']}")

    # Confirmation to user
    confirm_text = f"""
🎉 <b>Ticket Created Successfully!</b>

🎫 <b>Ticket ID:</b> <code>#{ticket_code}</code>
🏷️ <b>Topic:</b> {subject}
📊 <b>Status:</b> 🟡 <b>Open (Queued for Support Team)</b>

━━━━━━━━━━━━━━━━━━━━━
🛡️ <i>Our support team has been notified. When an admin replies, you will receive an instant notification here in this chat!</i>
"""
    await message.answer(confirm_text, reply_markup=ticket_detail_kb(ticket["id"], is_closed=False))

    # Notify all store admins
    admin_notify_text = f"""
🔔 <b>New Support Ticket Raised!</b>

🎫 <b>Ticket:</b> <code>#{ticket_code}</code>
👤 <b>From:</b> {escape_html(full_name)} (<code>{user_id}</code>) {username or ''}
🏷️ <b>Topic:</b> {subject}
━━━━━━━━━━━━━━━━━━━━━
📝 <b>Message:</b>
{escape_html(msg_text)}
"""
    admin_kb = admin_ticket_notify_kb(ticket["id"])
    for admin_id in config.ADMIN_IDS:
        try:
            if photo_id:
                await bot.send_photo(admin_id, photo=photo_id, caption=admin_notify_text, reply_markup=admin_kb)
            else:
                await bot.send_message(admin_id, text=admin_notify_text, reply_markup=admin_kb)
        except Exception:
            pass


@router.callback_query(F.data == "ticket_list")
async def cb_user_tickets_list(callback: CallbackQuery):
    """View list of all tickets raised by user"""
    user_id = callback.from_user.id
    tickets = await db.get_user_tickets(user_id=user_id)

    if not tickets:
        text = """
📜 <b>My Support Tickets</b>

<i>You haven't raised any support tickets yet. Need help? Click 'Raise New Ticket' below!</i>
"""
    else:
        text = """
📜 <b>My Support Tickets History:</b>

<i>Select a ticket below to view conversation thread and replies:</i>
"""
    try:
        await callback.message.edit_text(text, reply_markup=user_tickets_list_kb(tickets))
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=user_tickets_list_kb(tickets))
    await callback.answer()


@router.callback_query(F.data.startswith("view_tk_"))
async def cb_view_single_ticket_user(callback: CallbackQuery):
    """View ticket details & full conversation thread for user"""
    ticket_id = int(callback.data.split("_")[2])
    ticket = await db.get_ticket(ticket_id)

    if not ticket:
        await callback.answer("Ticket not found!", show_alert=True)
        return

    text = format_ticket_thread(ticket, is_admin=False)
    is_closed = ticket.get("status") == "closed"

    try:
        await callback.message.edit_text(text, reply_markup=ticket_detail_kb(ticket_id, is_closed=is_closed))
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=ticket_detail_kb(ticket_id, is_closed=is_closed))
    await callback.answer()


@router.callback_query(F.data.startswith("user_reply_tk_"))
async def cb_user_reply_ticket_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt user for reply message to ticket"""
    ticket_id = int(callback.data.split("_")[3])
    ticket = await db.get_ticket(ticket_id)

    if not ticket or ticket.get("status") == "closed":
        await callback.answer("This ticket is closed and cannot be replied to.", show_alert=True)
        return

    await state.set_state(UserTicketStates.waiting_for_reply)
    await state.update_data(ticket_id=ticket_id)

    await callback.message.reply(
        f"💬 <b>Reply to Ticket #{ticket.get('ticket_code', ticket_id)}:</b>\n\n"
        "<i>Type your reply or send a photo/screenshot below:</i>"
    )
    await callback.answer()


@router.message(UserTicketStates.waiting_for_reply)
async def process_user_ticket_reply(message: Message, state: FSMContext, bot: Bot):
    """Append user reply to ticket and alert admins"""
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    await state.clear()

    user_id = message.from_user.id
    full_name = message.from_user.full_name or "Customer"
    reply_text = message.text or message.caption or "Reply details."
    photo_id = message.photo[-1].file_id if message.photo else None

    ticket = await db.add_ticket_message(
        ticket_id=ticket_id,
        sender="user",
        sender_name=full_name,
        text=reply_text,
        photo_id=photo_id,
    )

    if not ticket:
        await message.reply("Ticket not found.")
        return

    await message.reply(
        f"✅ <b>Reply Sent to Support Team!</b> (Ticket <code>#{ticket.get('ticket_code', ticket_id)}</code>)",
        reply_markup=ticket_detail_kb(ticket_id, is_closed=False),
    )

    # Notify Admins
    admin_notify_text = f"""
📩 <b>User Replied to Ticket #{ticket.get('ticket_code', ticket_id)}!</b>

👤 <b>User:</b> {escape_html(full_name)} (<code>{user_id}</code>)
💬 <b>Reply:</b>
{escape_html(reply_text)}
"""
    admin_kb = admin_ticket_notify_kb(ticket_id)
    for admin_id in config.ADMIN_IDS:
        try:
            if photo_id:
                await bot.send_photo(admin_id, photo=photo_id, caption=admin_notify_text, reply_markup=admin_kb)
            else:
                await bot.send_message(admin_id, text=admin_notify_text, reply_markup=admin_kb)
        except Exception:
            pass


@router.callback_query(F.data.startswith("user_close_tk_"))
async def cb_user_close_ticket(callback: CallbackQuery):
    """User closes their own ticket"""
    ticket_id = int(callback.data.split("_")[3])
    await db.close_ticket(ticket_id, closed_by="user")
    await callback.answer("Ticket marked as resolved & closed.", show_alert=True)

    ticket = await db.get_ticket(ticket_id)
    if ticket:
        text = format_ticket_thread(ticket, is_admin=False)
        try:
            await callback.message.edit_text(text, reply_markup=ticket_detail_kb(ticket_id, is_closed=True))
        except Exception:
            pass


# ===========================================================================
# ADMIN TICKET MANAGEMENT & LIVE REPLIES
# ===========================================================================


@router.callback_query(F.data == "adm_tickets_menu")
@router.callback_query(F.data == "adm_tickets_open")
async def cb_admin_tickets_menu_open(callback: CallbackQuery):
    """List open / active tickets for admin"""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("Admin access required.", show_alert=True)
        return

    tickets = await db.get_all_tickets(status=None)
    # Filter active
    active_tickets = [t for t in tickets if t.get("status") in ("open", "answered")]

    text = f"""
🎫 <b>Support Tickets Desk (Admin)</b>

📊 <b>Active / Open Tickets:</b> <code>{len(active_tickets)}</code>
<i>Select a ticket to read full conversation and reply:</i>
"""
    await callback.message.edit_text(text, reply_markup=admin_tickets_list_kb(active_tickets, filter_status="open"))
    await callback.answer()


@router.callback_query(F.data == "adm_tickets_closed")
async def cb_admin_tickets_menu_closed(callback: CallbackQuery):
    """List closed tickets for admin"""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("Admin access required.", show_alert=True)
        return

    tickets = await db.get_all_tickets(status="closed")
    text = f"""
🎫 <b>Resolved & Closed Tickets (Admin)</b>

📊 <b>Total Closed:</b> <code>{len(tickets)}</code>
<i>Select a ticket to review history:</i>
"""
    await callback.message.edit_text(text, reply_markup=admin_tickets_list_kb(tickets, filter_status="closed"))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_view_tk_"))
async def cb_admin_view_ticket(callback: CallbackQuery):
    """View full ticket conversation from admin dashboard"""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("Admin access required.", show_alert=True)
        return

    ticket_id = int(callback.data.split("_")[3])
    ticket = await db.get_ticket(ticket_id)

    if not ticket:
        await callback.answer("Ticket not found.", show_alert=True)
        return

    text = format_ticket_thread(ticket, is_admin=True)
    is_closed = ticket.get("status") == "closed"
    await callback.message.edit_text(text, reply_markup=admin_ticket_detail_kb(ticket_id, is_closed=is_closed))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_reply_tk_"))
async def cb_admin_reply_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt admin to type response for a ticket"""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("Admin access required.", show_alert=True)
        return

    ticket_id = int(callback.data.split("_")[3])
    ticket = await db.get_ticket(ticket_id)

    if not ticket:
        await callback.answer("Ticket not found.", show_alert=True)
        return

    await state.set_state(AdminTicketStates.waiting_for_reply)
    await state.update_data(ticket_id=ticket_id)

    await callback.message.reply(
        f"👑 <b>Admin Response to Ticket #{ticket.get('ticket_code', ticket_id)}:</b>\n\n"
        f"👤 <b>Customer:</b> {escape_html(ticket.get('full_name', 'Customer'))} (<code>{ticket.get('user_id')}</code>)\n\n"
        "👉 <i>Type your message below (it will be delivered directly to the user):</i>"
    )
    await callback.answer()


@router.message(AdminTicketStates.waiting_for_reply)
async def process_admin_reply_submission(message: Message, state: FSMContext, bot: Bot):
    """Deliver admin reply to user and log in DB"""
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    await state.clear()

    reply_text = message.text or message.caption or "Response from store support team."
    photo_id = message.photo[-1].file_id if message.photo else None

    ticket = await db.add_ticket_message(
        ticket_id=ticket_id,
        sender="admin",
        sender_name="Support Team",
        text=reply_text,
        photo_id=photo_id,
    )

    if not ticket:
        await message.reply("Ticket not found.")
        return

    user_id = ticket["user_id"]
    ticket_code = ticket.get("ticket_code", f"#{ticket_id}")

    # Deliver to user
    user_notify_text = f"""
📩 <b>Support Team Replied to Your Ticket!</b>

🎫 <b>Ticket:</b> <code>#{ticket_code}</code>
━━━━━━━━━━━━━━━━━━━━━
💬 <b>Message from Support:</b>
{escape_html(reply_text)}
━━━━━━━━━━━━━━━━━━━━━

<i>You can reply back or close the ticket anytime below:</i>
"""
    delivered = False
    try:
        if photo_id:
            await bot.send_photo(
                user_id,
                photo=photo_id,
                caption=user_notify_text,
                reply_markup=ticket_detail_kb(ticket_id, is_closed=False),
            )
        else:
            await bot.send_message(
                user_id,
                text=user_notify_text,
                reply_markup=ticket_detail_kb(ticket_id, is_closed=False),
            )
        delivered = True
    except Exception as e:
        logger.warning(f"Could not deliver ticket reply to user {user_id}: {e}")

    status_msg = "✅ Delivered to user" if delivered else "⚠️ Sent (User may have blocked bot)"
    await message.reply(
        f"✅ <b>Reply Logged Successfully!</b>\n\n"
        f"🎫 Ticket: <code>#{ticket_code}</code>\n"
        f"📬 Delivery: {status_msg}",
        reply_markup=admin_ticket_detail_kb(ticket_id, is_closed=False),
    )


@router.callback_query(F.data.startswith("adm_close_tk_"))
async def cb_admin_close_ticket(callback: CallbackQuery, bot: Bot):
    """Admin marks ticket as closed"""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("Admin access required.", show_alert=True)
        return

    ticket_id = int(callback.data.split("_")[3])
    await db.close_ticket(ticket_id, closed_by="admin")
    await callback.answer("Ticket closed successfully.", show_alert=True)

    ticket = await db.get_ticket(ticket_id)
    if ticket:
        user_id = ticket["user_id"]
        ticket_code = ticket.get("ticket_code", f"#{ticket_id}")

        # Notify user
        try:
            await bot.send_message(
                user_id,
                f"ℹ️ <b>Ticket #{ticket_code} has been resolved and closed by support.</b>\n\n"
                f"<i>Thank you for shopping with us! If you need anything else, feel free to raise a new ticket.</i>",
                reply_markup=main_menu_kb(),
            )
        except Exception:
            pass

        text = format_ticket_thread(ticket, is_admin=True)
        try:
            await callback.message.edit_text(text, reply_markup=admin_ticket_detail_kb(ticket_id, is_closed=True))
        except Exception:
            pass

