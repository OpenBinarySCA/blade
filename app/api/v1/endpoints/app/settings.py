"""
Public Settings API

公开设置接口 - 前端可以获取公开的系统设置
"""
from fastapi import APIRouter

from .....services.settings import get_settings_service

router = APIRouter()


@router.get("/settings/public")
async def get_public_settings():
    """
    获取所有公开设置

    Returns:
        公开设置的键值对
    """
    service = get_settings_service()
    return service.get_public_settings()
