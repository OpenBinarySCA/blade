"""
Admin Settings API

管理后台系统设置接口
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .....services.auth import require_admin
from .....services.settings import get_settings_service
from .....databases.user_data.repository import settings_repository
from .....databases.user_data.models import User

router = APIRouter(prefix="/settings", tags=["Admin - Settings"])


# =============================================================================
# Request/Response Models
# =============================================================================

class SettingUpdate(BaseModel):
    """更新设置请求"""
    value: str
    value_type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


class SettingCreate(BaseModel):
    """创建设置请求"""
    key: str
    value: str
    value_type: str = "str"
    category: str = "general"
    description: Optional[str] = None
    is_public: bool = False


class SettingResponse(BaseModel):
    """设置响应"""
    key: str
    value: str | int | bool | dict | list
    value_type: str
    category: str
    description: Optional[str]
    is_public: bool
    updated_at: Optional[str]


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("", response_model=list[SettingResponse])
async def get_all_settings(
    category: Optional[str] = None,
    current_user: User = Depends(require_admin)
):
    """
    获取所有设置

    Args:
        category: 可选，按分类过滤
    """
    if category:
        settings = settings_repository.get_settings_by_category(category)
    else:
        settings = settings_repository.get_all_settings()

    return [s.to_dict() for s in settings]


@router.get("/categories")
async def get_categories(
    current_user: User = Depends(require_admin)
):
    """获取所有设置分类"""
    settings = settings_repository.get_all_settings()
    categories = list(set(s.category for s in settings))
    return sorted(categories)


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    current_user: User = Depends(require_admin)
):
    """获取单个设置"""
    setting = settings_repository.get_setting(key)
    if setting is None:
        raise HTTPException(status_code=404, detail=f"Setting not found: {key}")
    return setting.to_dict()


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    data: SettingUpdate,
    current_user: User = Depends(require_admin)
):
    """
    更新设置值

    仅更新提供的字段，未提供的字段保持不变
    """
    existing = settings_repository.get_setting(key)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Setting not found: {key}")

    # 构建更新参数
    update_kwargs = {"key": key, "value": data.value}
    if data.value_type is not None:
        update_kwargs["value_type"] = data.value_type
    else:
        update_kwargs["value_type"] = existing.value_type
    if data.category is not None:
        update_kwargs["category"] = data.category
    else:
        update_kwargs["category"] = existing.category
    if data.description is not None:
        update_kwargs["description"] = data.description
    else:
        update_kwargs["description"] = existing.description
    if data.is_public is not None:
        update_kwargs["is_public"] = data.is_public
    else:
        update_kwargs["is_public"] = existing.is_public

    setting = settings_repository.upsert_setting(**update_kwargs)

    # 刷新缓存
    get_settings_service().refresh(key)

    return setting.to_dict()


@router.post("", response_model=SettingResponse)
async def create_setting(
    data: SettingCreate,
    current_user: User = Depends(require_admin)
):
    """创建新设置"""
    existing = settings_repository.get_setting(data.key)
    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Setting already exists: {data.key}"
        )

    setting = settings_repository.upsert_setting(
        key=data.key,
        value=data.value,
        value_type=data.value_type,
        category=data.category,
        description=data.description,
        is_public=data.is_public
    )

    return setting.to_dict()


@router.delete("/{key}")
async def delete_setting(
    key: str,
    current_user: User = Depends(require_admin)
):
    """删除设置"""
    success = settings_repository.delete_setting(key)
    if not success:
        raise HTTPException(status_code=404, detail=f"Setting not found: {key}")

    # 刷新缓存
    get_settings_service().refresh(key)

    return {"message": f"Setting deleted: {key}"}


@router.post("/refresh")
async def refresh_cache(
    key: Optional[str] = None,
    current_user: User = Depends(require_admin)
):
    """
    刷新设置缓存

    Args:
        key: 可选，指定刷新单个设置，不指定则刷新所有
    """
    get_settings_service().refresh(key)
    return {"message": f"Cache refreshed: {key or 'all'}"}


@router.post("/init-defaults")
async def init_default_settings(
    current_user: User = Depends(require_admin)
):
    """初始化默认设置（不会覆盖已有设置）"""
    settings_repository.init_default_settings()
    return {"message": "Default settings initialized"}
