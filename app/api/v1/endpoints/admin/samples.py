"""
Admin Samples API

管理后台示例管理接口
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from .....services.auth import require_admin
from .....databases.user_data.repository import sample_repository
from .....databases.user_data.models import User

router = APIRouter(prefix="/samples", tags=["Admin - Samples"])


# =============================================================================
# Request/Response Models
# =============================================================================

class SampleResponse(BaseModel):
    """示例响应"""
    id: int
    file_name: str
    description: str
    task_id: str
    sort_order: int
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]


class SampleWithViewCountResponse(BaseModel):
    """带访问统计的示例响应"""
    id: int
    file_name: str
    description: str
    task_id: str
    sort_order: int
    is_active: bool
    view_count: int
    created_at: Optional[str]
    updated_at: Optional[str]


class SampleListResponse(BaseModel):
    """示例列表响应"""
    items: list[SampleWithViewCountResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SampleViewResponse(BaseModel):
    """访问记录响应"""
    id: int
    sample_id: int
    ip_address: str
    user_agent: Optional[str]
    viewed_at: Optional[str]


class SampleViewListResponse(BaseModel):
    """访问记录列表响应"""
    items: list[SampleViewResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CreateSampleRequest(BaseModel):
    """创建示例请求"""
    file_name: str
    description: str
    task_id: str
    sort_order: int = 0
    is_active: bool = True


class UpdateSampleRequest(BaseModel):
    """更新示例请求"""
    file_name: Optional[str] = None
    description: Optional[str] = None
    task_id: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("", response_model=SampleListResponse)
async def list_samples(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    current_user: User = Depends(require_admin)
):
    """
    获取示例列表（带访问统计）

    支持分页和筛选
    """
    samples, total = sample_repository.get_all_samples_with_view_count(
        page=page,
        page_size=page_size,
        is_active=is_active
    )

    total_pages = (total + page_size - 1) // page_size

    return SampleListResponse(
        items=[SampleWithViewCountResponse(**s) for s in samples],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{sample_id}", response_model=SampleResponse)
async def get_sample(
    sample_id: int,
    current_user: User = Depends(require_admin)
):
    """获取单个示例"""
    sample = sample_repository.get_sample_by_id(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")

    return SampleResponse(**sample.to_dict())


@router.post("", response_model=SampleResponse)
async def create_sample(
    data: CreateSampleRequest,
    current_user: User = Depends(require_admin)
):
    """创建示例"""
    sample = sample_repository.create_sample(
        file_name=data.file_name,
        description=data.description,
        task_id=data.task_id,
        sort_order=data.sort_order,
        is_active=data.is_active
    )
    return SampleResponse(**sample.to_dict())


@router.put("/{sample_id}", response_model=SampleResponse)
async def update_sample(
    sample_id: int,
    data: UpdateSampleRequest,
    current_user: User = Depends(require_admin)
):
    """更新示例"""
    sample = sample_repository.update_sample(
        sample_id=sample_id,
        file_name=data.file_name,
        description=data.description,
        task_id=data.task_id,
        sort_order=data.sort_order,
        is_active=data.is_active
    )
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")

    return SampleResponse(**sample.to_dict())


@router.delete("/{sample_id}")
async def delete_sample(
    sample_id: int,
    current_user: User = Depends(require_admin)
):
    """删除示例"""
    success = sample_repository.delete_sample(sample_id)
    if not success:
        raise HTTPException(status_code=404, detail="Sample not found")

    return {"message": "Sample deleted successfully"}


@router.get("/{sample_id}/views", response_model=SampleViewListResponse)
async def get_sample_views(
    sample_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(require_admin)
):
    """获取示例的访问记录"""
    # Check sample exists
    sample = sample_repository.get_sample_by_id(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")

    views, total = sample_repository.get_sample_views(
        sample_id=sample_id,
        page=page,
        page_size=page_size
    )

    total_pages = (total + page_size - 1) // page_size

    return SampleViewListResponse(
        items=[SampleViewResponse(**v.to_dict()) for v in views],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )
