"""
Version Info API Endpoint
"""
from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/version")
def get_version():
    """获取应用版本信息"""
    return {
        "app_version": settings.APP_VERSION,
        "engine_version": settings.ENGINE_VERSION,
        "release_datetime": settings.RELEASE_DATETIME
    }
