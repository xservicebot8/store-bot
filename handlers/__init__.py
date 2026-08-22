from .start import router as start_router
from .catalog import router as catalog_router
from .checkout import router as checkout_router
from .wallet import router as wallet_router
from .orders import router as orders_router
from .profile import router as profile_router
from .promo import router as promo_router
from .referral import router as referral_router
from .help import router as help_router
from .admin import admin_routers

user_routers = [
    start_router,
    catalog_router,
    checkout_router,
    wallet_router,
    orders_router,
    profile_router,
    referral_router,
    promo_router,
    help_router,
]

all_routers = user_routers + admin_routers

__all__ = ["all_routers"]

