"""
Admin Product Management Handlers (Direct Products Catalog Without Categories)
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext

from database.db import db
from keyboards.admin_kb import (
    admin_products_list_kb,
    admin_product_detail_kb,
)
from middlewares.admin_middleware import AdminMiddleware
from utils.states import AdminProductStates
from utils.helpers import format_currency, escape_html, format_timestamp, get_delivery_badge

router = Router(name="admin_products_router")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


def get_product_card_text(product: dict, stock_count: int) -> str:
    """Format rich product overview card for admin"""
    badge = get_delivery_badge(product.get("delivery_type", "stock"))
    status_str = "🟢 <b>Active (Visible)</b>" if product.get("is_active", 1) else "🔴 <b>Inactive (Hidden)</b>"

    return f"""
💎 <b>Product:</b> {escape_html(product['name'])}

💵 <b>Current Price:</b> <code>{format_currency(product['price'])}</code>
📦 <b>Delivery Type:</b> {badge}
🟢 <b>Available Stock:</b> <code>{stock_count} item(s)</code>
👁️ <b>Store Status:</b> {status_str}

📝 <b>Description:</b>
{escape_html(product.get('description', 'None'))}
"""


async def render_admin_product_card(callback: CallbackQuery, product: dict, stock_count: int):
    """Re-render product detail card with updated controls"""
    text = get_product_card_text(product, stock_count)
    try:
        await callback.message.edit_text(text, reply_markup=admin_product_detail_kb(product, stock_count))
    except Exception:
        pass


@router.callback_query(F.data == "adm_products_menu")
async def cb_admin_products_menu(callback: CallbackQuery):
    """Directly list all products in store for admin"""
    products = await db.get_all_products(active_only=False)
    text = "📦 <b>Manage Products in Store:</b>\n\n<i>Select a product to edit, adjust price, or add stock:</i>"
    try:
        await callback.message.edit_text(text, reply_markup=admin_products_list_kb(products))
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=admin_products_list_kb(products))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_prod_"))
async def cb_admin_product_detail(callback: CallbackQuery):
    """View & manage single product"""
    prod_id = int(callback.data.split("_")[2])
    product = await db.get_product(prod_id)

    if not product:
        await callback.answer("Product not found!", show_alert=True)
        return

    stock_count = product.get("stock_count", 0)
    await render_admin_product_card(callback, product, stock_count)
    await callback.answer()


# ==========================================
# 1-CLICK PRICE ADJUSTMENT & VISIBILITY
# ==========================================


@router.callback_query(F.data.startswith("adm_pr_adj_"))
async def cb_quick_price_adjust(callback: CallbackQuery):
    """1-Click Price increase or decrease"""
    parts = callback.data.split("_")
    prod_id = int(parts[3])
    delta = float(parts[4])

    new_price = await db.adjust_product_price(prod_id, delta)
    product = await db.get_product(prod_id)
    stock_count = product.get("stock_count", 0) if product else 0

    sign = "+" if delta > 0 else ""
    await callback.answer(f"Price updated: {sign}₹{delta:g} ➡️ {format_currency(new_price)}")
    await render_admin_product_card(callback, product, stock_count)


@router.callback_query(F.data.startswith("adm_toggle_prod_"))
async def cb_toggle_product_visibility(callback: CallbackQuery):
    """Toggle product active/inactive in store"""
    prod_id = int(callback.data.split("_")[3])
    new_status = await db.toggle_product_status(prod_id)
    product = await db.get_product(prod_id)
    stock_count = product.get("stock_count", 0) if product else 0

    msg = "Product is now VISIBLE in store 🟢" if new_status else "Product is now HIDDEN from store 🔴"
    await callback.answer(msg, show_alert=True)
    await render_admin_product_card(callback, product, stock_count)


# ==========================================
# STOCK EXPORT & SOLD HISTORY
# ==========================================


@router.callback_query(F.data.startswith("adm_stock_export_"))
async def cb_export_stock_as_txt(callback: CallbackQuery):
    """Export all remaining stock keys as a downloadable .txt file"""
    prod_id = int(callback.data.split("_")[3])
    product = await db.get_product(prod_id)

    if not product:
        await callback.answer("Product not found!", show_alert=True)
        return

    items = await db.get_unallocated_stock_raw(prod_id)
    if not items:
        await callback.answer("No stock items available to export.", show_alert=True)
        return

    content_str = "\n".join(items)
    file_bytes = content_str.encode("utf-8")
    filename = f"Stock_{product['name'].replace(' ', '_')}_{len(items)}_items.txt"
    doc = BufferedInputFile(file_bytes, filename=filename)

    await callback.message.answer_document(
        document=doc,
        caption=f"📥 <b>Exported {len(items)} Unused Stock Item(s)</b>\n📦 Product: <b>{escape_html(product['name'])}</b>",
    )
    await callback.answer("Stock exported as .txt document!", show_alert=True)


@router.callback_query(F.data.startswith("adm_stock_sold_"))
async def cb_view_sold_stock_history(callback: CallbackQuery):
    """View audit history of sold keys and orders for this product"""
    prod_id = int(callback.data.split("_")[3])
    product = await db.get_product(prod_id)

    if not product:
        await callback.answer("Product not found!", show_alert=True)
        return

    sold_items = await db.get_sold_stock_history(prod_id, limit=20)

    if not sold_items:
        text = f"📜 <b>Sold History for '{escape_html(product['name'])}':</b>\n\n<i>No items have been sold yet.</i>"
    else:
        text = f"📜 <b>Recent Sold Items for '{escape_html(product['name'])}':</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
        for itm in sold_items:
            text += f"🔑 <code>{escape_html(itm['content'])}</code>\n"
            text += f"   🧾 Order: #{itm.get('order_code', 'N/A')} • User ID: <code>{itm.get('user_id')}</code>\n"
            text += f"   📅 Delivered: {format_timestamp(itm.get('used_at'))}\n\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Product", callback_data=f"adm_prod_{prod_id}")]]
    )
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ==========================================
# ADD PRODUCT FLOW (DIRECT)
# ==========================================


@router.callback_query(F.data == "adm_add_prod")
async def cb_add_product_start(callback: CallbackQuery, state: FSMContext):
    """Start adding product flow directly without category"""
    await state.set_state(AdminProductStates.waiting_for_name)
    await callback.message.reply("📦 <b>Enter Product Title / Name:</b>\n\n<i>Example: <code>Netflix 1 Month UHD [1 Screen]</code></i>")
    await callback.answer()


@router.message(AdminProductStates.waiting_for_name)
async def process_prod_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(AdminProductStates.waiting_for_price)
    await message.reply("💵 <b>Enter Price in INR:</b>\n\n<i>Example: <code>149</code></i>")


@router.message(AdminProductStates.waiting_for_price)
async def process_prod_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.reply("❌ Invalid price. Enter a positive number (e.g. 149):")
        return

    await state.update_data(price=price)
    await state.set_state(AdminProductStates.waiting_for_description)
    await message.reply(
        "📝 <b>Enter Product Description / Instructions:</b>\n\n"
        "<i>Send full details, or type <code>skip</code> to leave empty.</i>"
    )


@router.message(AdminProductStates.waiting_for_description)
async def process_prod_desc(message: Message, state: FSMContext):
    desc = message.text.strip()
    if desc.lower() == "skip":
        desc = ""

    await state.update_data(description=desc)
    await state.set_state(AdminProductStates.waiting_for_delivery_type)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📁 1. Unique Files Stock (1 File = 1 Buyer)",
                    callback_data="adm_dtype_file_stock",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚡ 2. Line-by-Line Stock (1 Line = 1 Buyer)",
                    callback_data="adm_dtype_line_stock",
                )
            ],
            [
                InlineKeyboardButton(
                    text="♾️ 3. Universal File (Same for All)",
                    callback_data="adm_dtype_static_file",
                )
            ],
            [
                InlineKeyboardButton(
                    text="♾️ 4. Universal Code / Text (Same for All)",
                    callback_data="adm_dtype_static_text",
                )
            ],
        ]
    )
    await message.reply(
        "📦 <b>Select Product Delivery Type:</b>\n\n"
        "1️⃣ <b>Unique Files Stock:</b> You upload 10-50 separate <code>.txt</code> files. Each customer gets 1 unique file.\n"
        "2️⃣ <b>Line-by-Line Stock:</b> You paste lines/keys. Each customer gets 1 unique line.\n"
        "3️⃣ <b>Universal File:</b> 1 file sent to ALL customers (Unlimited).\n"
        "4️⃣ <b>Universal Text:</b> 1 code/text/link sent to ALL customers (Unlimited).",
        reply_markup=kb,
    )


@router.callback_query(AdminProductStates.waiting_for_delivery_type, F.data.startswith("adm_dtype_"))
async def process_prod_delivery_type(callback: CallbackQuery, state: FSMContext):
    dtype = callback.data.replace("adm_dtype_", "")
    await state.update_data(delivery_type=dtype)

    if dtype == "static_file":
        await state.set_state(AdminProductStates.waiting_for_static_file)
        await callback.message.reply(
            "📁 <b>Upload Universal File:</b>\n\n"
            "<i>Please send/upload the file (e.g. <code>.txt</code>, <code>.zip</code>, <code>.pdf</code>) that every customer will receive:</i>"
        )
    elif dtype == "static_text":
        await state.set_state(AdminProductStates.waiting_for_static_text)
        await callback.message.reply(
            "📝 <b>Enter Universal Text / Code / Link:</b>\n\n"
            "<i>Send the permanent text content that every customer will receive upon purchase:</i>"
        )
    else:
        # file_stock or line_stock
        await state.set_state(AdminProductStates.waiting_for_image)
        await callback.message.reply(
            "🖼️ <b>Upload Product Photo / Cover (Optional):</b>\n\n"
            "<i>Send a photo to attach to this product, or type <code>skip</code>.\n"
            "(You can add stock files/lines right after creating the product!)</i>"
        )
    await callback.answer()


@router.message(AdminProductStates.waiting_for_static_file)
async def process_prod_static_file(message: Message, state: FSMContext):
    if not message.document:
        await message.reply("❌ Please send a valid document file (e.g. .txt, .zip, .pdf):")
        return

    await state.update_data(file_id=message.document.file_id)
    await state.set_state(AdminProductStates.waiting_for_image)
    await message.reply(
        f"✅ File <code>{escape_html(message.document.file_name)}</code> received!\n\n"
        "🖼️ <b>Upload Product Photo (Optional):</b>\n\n"
        "<i>Send a photo or type <code>skip</code>:</i>"
    )


@router.message(AdminProductStates.waiting_for_static_text)
async def process_prod_static_text(message: Message, state: FSMContext):
    text_content = message.text.strip()
    if not text_content:
        await message.reply("❌ Please send valid text content:")
        return

    await state.update_data(static_content=text_content)
    await state.set_state(AdminProductStates.waiting_for_image)
    await message.reply(
        "✅ Static content recorded!\n\n"
        "🖼️ <b>Upload Product Photo (Optional):</b>\n\n"
        "<i>Send a photo or type <code>skip</code>:</i>"
    )


@router.message(AdminProductStates.waiting_for_image)
async def process_prod_image_and_save(message: Message, state: FSMContext):
    image_file_id = None
    if message.photo:
        image_file_id = message.photo[-1].file_id
    elif message.text and message.text.strip().lower() != "skip":
        await message.reply("Please send a valid photo or type 'skip':")
        return

    data = await state.get_data()
    await state.clear()

    prod_id = await db.add_product(
        name=data["name"],
        description=data.get("description", ""),
        price=data["price"],
        delivery_type=data["delivery_type"],
        image_file_id=image_file_id,
        file_id=data.get("file_id"),
        static_content=data.get("static_content"),
    )

    product = await db.get_product(prod_id)
    dtype = data["delivery_type"]

    extra_tip = ""
    if dtype == "file_stock":
        extra_tip = "\n👉 Click <b>'📁 Add Files Stock'</b> below to upload your <code>.txt</code> files!"
    elif dtype == "line_stock":
        extra_tip = "\n👉 Click <b>'⚡ Add Stock (Bulk)'</b> below to paste your keys/accounts!"

    await message.reply(
        f"🎉 <b>Product '{escape_html(data['name'])}' Created Successfully!</b>\n\n"
        f"📦 <b>Delivery Type:</b> {get_delivery_badge(dtype)}{extra_tip}",
        reply_markup=admin_product_detail_kb(product, 0),
    )


# ==========================================
# EDIT & DELETE PRODUCT
# ==========================================


@router.callback_query(F.data.startswith("adm_edit_price_"))
async def cb_edit_price_prompt(callback: CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split("_")[3])
    await state.set_state(AdminProductStates.waiting_for_edit_price)
    await state.update_data(prod_id=prod_id)
    await callback.message.reply("💵 <b>Enter new custom price in INR:</b>")
    await callback.answer()


@router.message(AdminProductStates.waiting_for_edit_price)
async def process_edit_price(message: Message, state: FSMContext):
    try:
        new_price = float(message.text.strip())
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.reply("❌ Invalid price. Please enter a valid number:")
        return

    data = await state.get_data()
    prod_id = data.get("prod_id")
    await state.clear()

    await db.update_product(prod_id, price=new_price)
    product = await db.get_product(prod_id)
    await message.reply(
        f"✅ Price updated to <b>{format_currency(new_price)}</b>!",
        reply_markup=admin_product_detail_kb(product, product.get("stock_count", 0)),
    )


@router.callback_query(F.data.startswith("adm_edit_name_"))
async def cb_edit_name_prompt(callback: CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split("_")[3])
    await state.set_state(AdminProductStates.waiting_for_edit_name)
    await state.update_data(prod_id=prod_id)
    await callback.message.reply("✏️ <b>Enter new product title:</b>")
    await callback.answer()


@router.message(AdminProductStates.waiting_for_edit_name)
async def process_edit_name(message: Message, state: FSMContext):
    name = message.text.strip()
    data = await state.get_data()
    prod_id = data.get("prod_id")
    await state.clear()

    await db.update_product(prod_id, name=name)
    product = await db.get_product(prod_id)
    await message.reply(
        f"✅ Title updated to <b>{escape_html(name)}</b>!",
        reply_markup=admin_product_detail_kb(product, product.get("stock_count", 0)),
    )


@router.callback_query(F.data.startswith("adm_edit_desc_"))
async def cb_edit_desc_prompt(callback: CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split("_")[3])
    await state.set_state(AdminProductStates.waiting_for_edit_desc)
    await state.update_data(prod_id=prod_id)
    await callback.message.reply("📝 <b>Enter new description (or 'skip' to clear):</b>")
    await callback.answer()


@router.message(AdminProductStates.waiting_for_edit_desc)
async def process_edit_desc(message: Message, state: FSMContext):
    desc = message.text.strip()
    if desc.lower() == "skip":
        desc = ""
    data = await state.get_data()
    prod_id = data.get("prod_id")
    await state.clear()

    await db.update_product(prod_id, description=desc)
    product = await db.get_product(prod_id)
    await message.reply(
        "✅ Description updated!",
        reply_markup=admin_product_detail_kb(product, product.get("stock_count", 0)),
    )


@router.callback_query(F.data.startswith("adm_edit_file_"))
async def cb_edit_file_prompt(callback: CallbackQuery, state: FSMContext):
    """Change universal file"""
    prod_id = int(callback.data.split("_")[3])
    await state.set_state(AdminProductStates.waiting_for_edit_static_file)
    await state.update_data(prod_id=prod_id)
    await callback.message.reply("📁 <b>Upload new universal file (e.g. .txt, .zip, .pdf):</b>")
    await callback.answer()


@router.message(AdminProductStates.waiting_for_edit_static_file)
async def process_edit_file(message: Message, state: FSMContext):
    if not message.document:
        await message.reply("❌ Please send a valid document file:")
        return

    data = await state.get_data()
    prod_id = data.get("prod_id")
    await state.clear()

    await db.update_product(prod_id, file_id=message.document.file_id)
    product = await db.get_product(prod_id)
    await message.reply(
        f"✅ Universal file updated to <code>{escape_html(message.document.file_name)}</code>!",
        reply_markup=admin_product_detail_kb(product, product.get("stock_count", 0)),
    )


@router.callback_query(F.data.startswith("adm_edit_static_txt_"))
async def cb_edit_static_text_prompt(callback: CallbackQuery, state: FSMContext):
    """Change universal text/code"""
    prod_id = int(callback.data.split("_")[4])
    await state.set_state(AdminProductStates.waiting_for_edit_static_text)
    await state.update_data(prod_id=prod_id)
    await callback.message.reply("📝 <b>Enter new universal text / code:</b>")
    await callback.answer()


@router.message(AdminProductStates.waiting_for_edit_static_text)
async def process_edit_static_text(message: Message, state: FSMContext):
    text_content = message.text.strip()
    data = await state.get_data()
    prod_id = data.get("prod_id")
    await state.clear()

    await db.update_product(prod_id, static_content=text_content)
    product = await db.get_product(prod_id)
    await message.reply(
        "✅ Universal text updated!",
        reply_markup=admin_product_detail_kb(product, product.get("stock_count", 0)),
    )


@router.callback_query(F.data.startswith("adm_del_prod_"))
async def cb_delete_product(callback: CallbackQuery):
    """Delete product"""
    prod_id = int(callback.data.split("_")[3])
    await db.delete_product(prod_id)
    await callback.answer("Product deleted.", show_alert=True)
    products = await db.get_all_products(active_only=False)
    await callback.message.edit_text("📦 <b>Products List Updated:</b>", reply_markup=admin_products_list_kb(products))

