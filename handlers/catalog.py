"""
Direct Product Browsing Handlers (Without Categories)
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.db import db
from keyboards.user_kb import products_kb, product_detail_kb, back_to_menu_kb
from utils.helpers import format_currency, escape_html, get_delivery_badge

router = Router(name="catalog_router")


@router.callback_query(F.data == "user_browse")
async def cb_browse_all_products(callback: CallbackQuery):
    """Directly display all active store products"""
    products = await db.get_all_products(active_only=True)

    if not products:
        text = """
🛍️ <b>Store Products</b>

<i>No products are available right now. Please check back shortly!</i>
"""
        await callback.message.edit_text(text, reply_markup=back_to_menu_kb())
        await callback.answer()
        return

    text = """
🛍️ <b>Available Products in Store:</b>

<i>Select a product below to view details and pricing:</i>
"""
    try:
        await callback.message.edit_text(text, reply_markup=products_kb(products))
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=products_kb(products))
    await callback.answer()


@router.callback_query(F.data.startswith("prod_"))
async def cb_view_product(callback: CallbackQuery):
    """Display detailed product view"""
    prod_id = int(callback.data.split("_")[1])
    product = await db.get_product(prod_id)

    if not product:
        await callback.answer("Product not found!", show_alert=True)
        return

    stock_count = product.get("stock_count", 0)
    delivery_badge = get_delivery_badge(product.get("delivery_type", "stock"))

    if product.get("delivery_type") == "stock":
        stock_status = f"🟢 <b>In Stock:</b> {stock_count} unit(s)" if stock_count > 0 else "🔴 <b>Status:</b> Out of Stock"
    else:
        stock_status = "🟢 <b>Status:</b> Available"

    desc = f"\n📝 <b>Description:</b>\n{escape_html(product.get('description', ''))}\n" if product.get("description") else ""

    text = f"""
💎 <b>{escape_html(product['name'])}</b>

💵 <b>Price:</b> <code>{format_currency(product['price'])}</code>
{stock_status}
📦 <b>Delivery:</b> {delivery_badge}
{desc}
━━━━━━━━━━━━━━━━━━━━━
⚡ <i>Instant automated delivery to your Telegram chat right after payment!</i>
"""

    image_file_id = product.get("image_file_id")

    if image_file_id:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=image_file_id,
                caption=text,
                reply_markup=product_detail_kb(product, stock_count),
            )
            await callback.answer()
            return
        except Exception:
            pass

    try:
        await callback.message.edit_text(text, reply_markup=product_detail_kb(product, stock_count))
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=product_detail_kb(product, stock_count))

    await callback.answer()
