"""
Aiogram FSM States for Store Bot
"""

from aiogram.fsm.state import State, StatesGroup


class AdminCategoryStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_edit_name = State()


class AdminProductStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_description = State()
    waiting_for_delivery_type = State()
    waiting_for_static_file = State()
    waiting_for_static_text = State()
    waiting_for_initial_stock = State()
    waiting_for_image = State()
    # Editing states
    waiting_for_edit_price = State()
    waiting_for_edit_name = State()
    waiting_for_edit_desc = State()
    waiting_for_edit_static_text = State()
    waiting_for_edit_static_file = State()


class AdminStockStates(StatesGroup):
    waiting_for_product_selection = State()
    waiting_for_stock_items = State()  # Can be single or bulk multi-line


class AdminCouponStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_type = State()  # 'percent' or 'flat'
    waiting_for_value = State()
    waiting_for_min_purchase = State()
    waiting_for_max_uses = State()


class AdminBroadcastStates(StatesGroup):
    waiting_for_broadcast_content = State()
    waiting_for_confirmation = State()


class AdminUserStates(StatesGroup):
    waiting_for_user_query = State()
    waiting_for_balance_adjust = State()


class AdminSettingsStates(StatesGroup):
    waiting_for_upi_id = State()
    waiting_for_merchant_name = State()
    waiting_for_session_cookie = State()
    waiting_for_xsrf_token = State()
    waiting_for_min_deposit = State()
    waiting_for_support_user = State()
    waiting_for_channel_user = State()
    waiting_for_ref_join_amt = State()
    waiting_for_ref_purch_pct = State()
    waiting_for_ref_channel = State()


class AdminReferralRewardStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_points = State()
    waiting_for_desc = State()
    waiting_for_content = State()


class UserCheckoutStates(StatesGroup):
    selecting_quantity = State()
    confirming_order = State()
    waiting_for_utr = State()


class UserDepositStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_deposit_utr = State()


class UserPromoStates(StatesGroup):
    waiting_for_coupon_code = State()
