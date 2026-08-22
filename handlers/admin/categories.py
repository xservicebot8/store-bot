"""
Admin Category Management Handlers
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database.db import db
from keyboards.admin_kb import admin_categories_kb, admin_category_detail_kb, admin_main_kb
from middlewares.admin_middleware import AdminMiddleware
from utils.states import AdminCategoryStates
from utils.helpers import escape_html

router = Router(name="admin_categories_router")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.callback_query(F.data == "adm_categories_menu")
async def cb_admin_categories(callback: CallbackQuery, state: FSMContext):
    """List all categories for admin"""
    await state.clear()
    categories = await db.get_categories(active_only=False)

    text = """
📁 <b>Manage Store Categories</b>

<i>Select a category to view/edit products or add a new category:</i>
"""
    await callback.message.edit_text(text, reply_markup=admin_categories_kb(categories))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cat_"))
async def cb_admin_category_detail(callback: CallbackQuery):
    """Show options for selected category"""
    cat_id_raw = callback.data.replace("adm_cat_", "")
    if not cat_id_raw.isdigit():
        return
    cat_id = int(cat_id_raw)
    cat = await db.get_category(cat_id)

    if not cat:
        await callback.answer("Category not found!", show_alert=True)
        return

    text = f"""
📁 <b>Category:</b> {escape_html(cat['name'])}
📝 <b>Description:</b> {escape_html(cat.get('description', 'None'))}
"""
    await callback.message.edit_text(text, reply_markup=admin_category_detail_kb(cat_id))
    await callback.answer()


@router.callback_query(F.data == "adm_add_category")
async def cb_add_category_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt for category name"""
    await state.set_state(AdminCategoryStates.waiting_for_name)
    await callback.message.reply("📁 <b>Enter Name for the New Category:</b>\n\n<i>Example: <code>Accounts & Subscriptions</code></i>")
    await callback.answer()


@router.message(AdminCategoryStates.waiting_for_name)
async def process_cat_name(message: Message, state: FSMContext):
    """Save name and prompt for description"""
    name = message.text.strip()
    if len(name) < 2:
        await message.reply("Name is too short. Please enter a valid name:")
        return

    await state.update_data(name=name)
    await state.set_state(AdminCategoryStates.waiting_for_description)
    await message.reply(
        "📝 <b>Enter Category Description (optional):</b>\n\n"
        "<i>Send a short description, or type <code>skip</code> to leave empty.</i>"
    )


@router.message(AdminCategoryStates.waiting_for_description)
async def process_cat_desc(message: Message, state: FSMContext):
    """Save category to database"""
    desc = message.text.strip()
    if desc.lower() == "skip":
        desc = ""

    data = await state.get_data()
    name = data.get("name")
    await state.clear()

    cat_id = await db.add_category(name=name, description=desc)
    await message.reply(
        f"✅ <b>Category '{escape_html(name)}' Created Successfully!</b>",
        reply_markup=admin_category_detail_kb(cat_id),
    )


@router.callback_query(F.data.startswith("adm_edit_cat_"))
async def cb_edit_category(callback: CallbackQuery, state: FSMContext):
    """Prompt to edit category name"""
    cat_id = int(callback.data.split("_")[3])
    await state.set_state(AdminCategoryStates.waiting_for_edit_name)
    await state.update_data(cat_id=cat_id)
    await callback.message.reply("✏️ <b>Enter new name for this category:</b>")
    await callback.answer()


@router.message(AdminCategoryStates.waiting_for_edit_name)
async def process_edit_cat_name(message: Message, state: FSMContext):
    """Save updated category name"""
    name = message.text.strip()
    data = await state.get_data()
    cat_id = data.get("cat_id")
    await state.clear()

    cat = await db.get_category(cat_id)
    desc = cat.get("description", "") if cat else ""
    await db.update_category(cat_id, name=name, description=desc)
    await message.reply(
        f"✅ Category name updated to <b>{escape_html(name)}</b>!",
        reply_markup=admin_category_detail_kb(cat_id),
    )


@router.callback_query(F.data.startswith("adm_del_cat_"))
async def cb_delete_category(callback: CallbackQuery):
    """Delete category"""
    cat_id = int(callback.data.split("_")[3])
    await db.delete_category(cat_id)
    await callback.answer("Category deleted.", show_alert=True)
    categories = await db.get_categories(active_only=False)
    await callback.message.edit_text("📁 <b>Categories Updated:</b>", reply_markup=admin_categories_kb(categories))
