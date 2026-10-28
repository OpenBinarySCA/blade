"""
Public Samples API

公开的示例接口，供前端展示
"""
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from .....databases.user_data.repository import sample_repository

router = APIRouter(prefix="/samples", tags=["Samples"])


# =============================================================================
# Response Models
# =============================================================================

class PublicSampleResponse(BaseModel):
    """公开示例响应"""
    id: int
    file_name: str
    description: str
    task_id: str


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("", response_model=list[PublicSampleResponse])
async def get_samples():
    """
    获取所有启用的示例列表

    供前端上传页面展示，无需登录
    """
    samples = sample_repository.get_active_samples()
    return [
        PublicSampleResponse(
            id=s.id,
            file_name=s.file_name,
            description=s.description,
            task_id=s.task_id
        )
        for s in samples
    ]
