from app.routers.trips import router as trips_router
from app.routers.expenses import router as expenses_router
from app.routers.chat import router as chat_router
from app.routers.receipts import router as receipts_router
from app.routers.reports import router as reports_router

__all__ = [
    "trips_router",
    "expenses_router",
    "chat_router",
    "receipts_router",
    "reports_router",
]
