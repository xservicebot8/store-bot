"""
Admin Stock Management Handlers (Supports Batch .txt Files, Document Parsing, and Line Stock)
"""

from io import BytesIO
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import db
from keyboards.admin_kb import admin_product_detail_kb
from middlewares.admin_middleware import AdminMiddleware
from utils.states import AdminStockStates
from utils.helpers import escape_html, get_delivery_badge

router = Router(name="admin_stock_router")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.callback_query(F.data.startswith("adm_stock_add_"))
async def cb_add_stock_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt admin to upload stock files or paste lines"""
    prod_id = int(callback.data.split("_")[3])
    product = await db.get_product(prod_id)

    if not product:
        await callback.answer("Product not found!", show_alert=True)
        return

    dtype = product.get("delivery_type", "line_stock")
    await state.set_state(AdminStockStates.waiting_for_stock_items)
    await state.update_data(prod_id=prod_id, files_added=0)

    if dtype == "file_stock":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Done Uploading Files", callback_data=f"adm_stock_done_{prod_id}")],
                [InlineKeyboardButton(text="🔙 Cancel", callback_data=f"adm_prod_{prod_id}")],
            ]
        )
        text = f"""
📁 <b>Add Stock Files for '{escape_html(product['name'])}'</b>

👉 <b>Send one or multiple <code>.txt</code> / document files to this chat.</b>
• You can send/forward 10, 50, or 100 files all at once!
• Each file will be delivered to 1 unique customer upon purchase.

<i>Send files now, then click 'Done Uploading Files' below:</i>
"""
        await callback.message.reply(text, reply_markup=kb)
    else:
        # Line-by-line stock
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Cancel", callback_data=f"adm_prod_{prod_id}")],
            ]
        )
        text = f"""
⚡ <b>Add Line Stock for '{escape_html(product['name'])}'</b>

👉 <b>Option 1:</b> Paste text lines (1 line per item/account/key).
👉 <b>Option 2:</b> Upload a single <code>.txt</code> file containing all lines.

<i>Example format:</i>
<code>email1@domain.com:password123
email2@domain.com:password456
XXXXX-XXXXX-XXXXX-XXXXX</code>
"""
        await callback.message.reply(text, reply_markup=kb)
    await callback.answer()


@router.message(AdminStockStates.waiting_for_stock_items, F.document)
async def process_document_stock_upload(message: Message, state: FSMContext, bot: Bot):
    """Handle document uploads - either as unique file stock OR parsing lines from txt file"""
    data = await state.get_data()
    prod_id = data.get("prod_id")
    product = await db.get_product(prod_id)

    if not product:
        await state.clear()
        await message.reply("Product not found.")
        return

    dtype = product.get("delivery_type", "line_stock")

    if dtype == "file_stock":
        # Save as 1 unique file in stock
        doc = message.document
        await db.add_stock_file(
            product_id=prod_id,
            file_id=doc.file_id,
            file_name=doc.file_name or "stock_file.txt",
        )
        files_added = data.get("files_added", 0) + 1
        await state.update_data(files_added=files_added)

        new_stock = await db.get_stock_count(prod_id)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Done Uploading Files", callback_data=f"adm_stock_done_{prod_id}")],
            ]
        )
        await message.reply(
            f"📥 <b>Added File #{files_added}:</b> <code>{escape_html(doc.file_name)}</code>\n"
            f"🟢 Current Stock Count: <code>{new_stock} files</code>\n\n"
            f"<i>Send more files, or click 'Done Uploading Files' when finished.</i>",
            reply_markup=kb,
        )

    else:
        # Line stock from .txt file
        doc = message.document
        if not doc.file_name.lower().endswith(".txt"):
            await message.reply("❌ Please send a .txt file containing text lines:")
            return

        file_obj = await bot.download(doc)
        content_bytes = file_obj.read()
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = content_bytes.decode("latin-1", errors="ignore")

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            await message.reply("❌ No valid lines found in the uploaded text file.")
            return

        added_count = await db.add_bulk_stock(prod_id, lines)
        await state.clear()

        product = await db.get_product(prod_id)
        new_stock = product.get("stock_count", 0) if product else added_count

        await message.reply(
            f"✅ <b>Successfully Parsed & Added {added_count} Lines from '{escape_html(doc.file_name)}'!</b>\n\n"
            f"📦 Total Stock Available: <code>{new_stock}</code>",
            reply_markup=admin_product_detail_kb(product, new_stock),
        )


@router.message(AdminStockStates.waiting_for_stock_items, F.text)
async def process_text_stock_ingestion(message: Message, state: FSMContext):
    """Parse pasted text lines for line stock"""
    data = await state.get_data()
    prod_id = data.get("prod_id")
    product = await db.get_product(prod_id)

    if not product:
        await state.clear()
        await message.reply("Product not found.")
        return

    dtype = product.get("delivery_type", "line_stock")

    if dtype == "file_stock":
        await message.reply(
            "⚠️ This product is set to <b>Unique Files Stock</b>.\n"
            "Please send <code>.txt</code> document files, or click <b>'Done Uploading Files'</b>."
        )
        return

    raw_text = message.text or ""
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

    if not lines:
        await message.reply("❌ No valid stock items found in message.")
        return

    added_count = await db.add_bulk_stock(prod_id, lines)
    await state.clear()

    product = await db.get_product(prod_id)
    new_stock = product.get("stock_count", 0) if product else added_count

    await message.reply(
        f"✅ <b>Successfully Added {added_count} Stock Item(s)!</b>\n\n"
        f"📦 Total Stock Available: <code>{new_stock}</code>",
        reply_markup=admin_product_detail_kb(product, new_stock),
    )


@router.callback_query(F.data.startswith("adm_stock_done_"))
async def cb_finish_file_stock_upload(callback: CallbackQuery, state: FSMContext):
    """Complete batch file upload session"""
    prod_id = int(callback.data.split("_")[3])
    data = await state.get_data()
    files_added = data.get("files_added", 0)
    await state.clear()

    product = await db.get_product(prod_id)
    stock_count = product.get("stock_count", 0) if product else 0

    await callback.message.reply(
        f"🎉 <b>Batch File Upload Finished!</b>\n\n"
        f"📁 Added this session: <code>{files_added} file(s)</code>\n"
        f"🟢 Total Stock Available: <code>{stock_count} item(s)</code>",
        reply_markup=admin_product_detail_kb(product, stock_count),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_stock_view_"))
async def cb_view_stock_items(callback: CallbackQuery):
    """View unused stock items for product"""
    prod_id = int(callback.data.split("_")[3])
    product = await db.get_product(prod_id)

    if not product:
        await callback.answer("Product not found!", show_alert=True)
        return

    dtype = product.get("delivery_type", "line_stock")
    items = await db.get_available_stock_items(prod_id, limit=25)
    stock_count = product.get("stock_count", 0)

    if not items:
        text = f"📦 <b>Available Stock for '{escape_html(product['name'])}':</b>\n\n<i>No stock available (Out of stock).</i>"
    else:
        text = f"📦 <b>Available Stock ({stock_count} Total) for '{escape_html(product['name'])}':</b>\n\n"
        for idx, itm in enumerate(items, 1):
            if dtype == "file_stock":
                fname = itm.get("file_name") or itm.get("content") or "file.txt"
                text += f"{idx}. 📁 <code>{escape_html(fname)}</code>\n"
            else:
                text += f"{idx}. 🔑 <code>{escape_html(itm['content'])}</code>\n"
        if stock_count > 25:
            text += f"\n<i>...and {stock_count - 25} more items in stock.</i>"

    add_btn_text = "📁 Add Files Stock" if dtype == "file_stock" else "⚡ Add More Stock"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=add_btn_text, callback_data=f"adm_stock_add_{prod_id}")],
            [InlineKeyboardButton(text="🗑️ Clear All Unused Stock", callback_data=f"adm_stock_clear_{prod_id}")],
            [InlineKeyboardButton(text="🔙 Back to Product", callback_data=f"adm_prod_{prod_id}")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm_stock_clear_"))
async def cb_clear_stock(callback: CallbackQuery):
    """Clear unused stock"""
    prod_id = int(callback.data.split("_")[3])
    cleared = await db.clear_unused_stock(prod_id)
    await callback.answer(f"Cleared {cleared} unused items.", show_alert=True)
    product = await db.get_product(prod_id)
    await callback.message.edit_text("✅ <b>Stock cleared.</b>", reply_markup=admin_product_detail_kb(product, 0))

