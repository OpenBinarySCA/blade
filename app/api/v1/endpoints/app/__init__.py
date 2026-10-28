"""
App API Endpoints - User-facing endpoints
"""
from .tpl_detection_task import router as tpl_detection_router
from .file_operations import router as file_operations_router
from .result_chat import router as result_chat_router
from .version import router as version_router

__all__ = [
    "tpl_detection_router",
    "file_operations_router",
    "result_chat_router",
    "version_router",
]
