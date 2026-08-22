from .panel import router as panel_router
from .categories import router as categories_router
from .products import router as products_router
from .stock import router as stock_router
from .orders import router as orders_router
from .users import router as users_router
from .coupons import router as coupons_router
from .broadcast import router as broadcast_router
from .settings import router as settings_router

admin_routers = [
    panel_router,
    categories_router,
    products_router,
    stock_router,
    orders_router,
    users_router,
    coupons_router,
    broadcast_router,
    settings_router,
]

__all__ = ["admin_routers"]
