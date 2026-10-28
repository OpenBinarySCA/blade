"""
App API Endpoints - User-facing endpoints
"""
from .tpl_detection_task import router as tpl_detection_router
from .file_operations import router as file_operations_router
from .version import router as version_router
from .samples import router as samples_router
from .settings import router as public_settings_router

__all__ = [
    "tpl_detection_router",
    "file_operations_router",
    "version_router",
    "samples_router",
    "public_settings_router",
]
