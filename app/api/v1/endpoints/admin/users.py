"""
Admin Users API

管理后台用户管理接口
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from .....services.auth import require_admin
from .....databases.user_data.repository import (
    get_all_users,
    get_user_by_id,
    update_user_admin_status,
    delete_user,
    get_user_count,
    get_admin_count,
)
from .....databases.user_data.models import User

router = APIRouter(prefix="/users", tags=["Admin - Users"])


# =============================================================================
# Request/Response Models
# =============================================================================

class UserResponse(BaseModel):
    """用户响应"""
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    profile_picture: Optional[str]
    is_admin: bool
    created_at: Optional[str]
    updated_at: Optional[str]

    @classmethod
    def from_model(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            profile_picture=user.profile_picture,
            is_admin=user.is_admin,
            created_at=user.created_at.isoformat() if user.created_at else None,
            updated_at=user.updated_at.isoformat() if user.updated_at else None,
        )


class UserListResponse(BaseModel):
    """用户列表响应"""
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserStatsResponse(BaseModel):
    """用户统计响应"""
    total_users: int
    admin_users: int
    regular_users: int


class UpdateAdminStatusRequest(BaseModel):
    """更新管理员状态请求"""
    is_admin: bool


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    is_admin: Optional[bool] = Query(None, description="是否为管理员"),
    current_user: User = Depends(require_admin)
):
    """
    获取用户列表

    支持分页和搜索
    """
    users, total = get_all_users(
        page=page,
        page_size=page_size,
        search=search,
        is_admin=is_admin
    )

    total_pages = (total + page_size - 1) // page_size

    return UserListResponse(
        items=[UserResponse.from_model(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(
    current_user: User = Depends(require_admin)
):
    """获取用户统计信息"""
    total = get_user_count()
    admins = get_admin_count()

    return UserStatsResponse(
        total_users=total,
        admin_users=admins,
        regular_users=total - admins
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin)
):
    """获取单个用户信息"""
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse.from_model(user)


@router.put("/{user_id}/admin-status", response_model=UserResponse)
async def update_admin_status(
    user_id: int,
    data: UpdateAdminStatusRequest,
    current_user: User = Depends(require_admin)
):
    """
    更新用户的管理员状态

    注意：不能修改自己的管理员状态
    """
    # 不能修改自己的状态
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot modify your own admin status"
        )

    user = update_user_admin_status(user_id, data.is_admin)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse.from_model(user)


@router.delete("/{user_id}")
async def remove_user(
    user_id: int,
    current_user: User = Depends(require_admin)
):
    """
    删除用户

    注意：不能删除自己
    """
    # 不能删除自己
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete yourself"
        )

    success = delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User deleted successfully"}
