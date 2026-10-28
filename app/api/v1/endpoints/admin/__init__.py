"""
Admin API Endpoints - Admin-only endpoints
"""
from .data_management import router as data_management_router
from .settings import router as settings_router
from .users import router as users_router
from .tasks import router as tasks_router
from .system_monitor import router as system_monitor_router

__all__ = [
    "data_management_router",
    "settings_router",
    "users_router",
    "tasks_router",
    "system_monitor_router",
]
