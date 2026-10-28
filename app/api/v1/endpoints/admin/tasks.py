"""
Admin Tasks API

管理后台分析任务管理接口
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from .....services.auth import require_admin
from .....databases.user_data.repository import task_repository, get_user_by_id
from .....databases.user_data.models import User, AnalysisTask

router = APIRouter(prefix="/tasks", tags=["Admin - Tasks"])


# =============================================================================
# Request/Response Models
# =============================================================================

class TaskUserInfo(BaseModel):
    """任务关联的用户信息"""
    id: int
    username: str
    email: Optional[str]


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    user_id: Optional[int]
    user: Optional[TaskUserInfo]
    engine_version: str
    input_file_sha256: str
    file_name: str
    file_minio_path: str
    status: str
    start_at: Optional[str]
    end_at: Optional[str]
    result_minio_path: Optional[str]
    report_minio_path: Optional[str]
    error_message: Optional[str]
    analysis_total_files: int
    analysis_completed_files: int
    created_at: Optional[str]
    updated_at: Optional[str]

    @classmethod
    def from_model(cls, task: AnalysisTask, user: User = None) -> "TaskResponse":
        user_info = None
        if user:
            user_info = TaskUserInfo(
                id=user.id,
                username=user.username,
                email=user.email
            )

        return cls(
            task_id=task.task_id,
            user_id=task.user_id,
            user=user_info,
            engine_version=task.engine_version,
            input_file_sha256=task.input_file_sha256,
            file_name=task.file_name,
            file_minio_path=task.file_minio_path,
            status=task.status,
            start_at=task.start_at.isoformat() if task.start_at else None,
            end_at=task.end_at.isoformat() if task.end_at else None,
            result_minio_path=task.result_minio_path,
            report_minio_path=task.report_minio_path,
            error_message=task.error_message,
            analysis_total_files=task.analysis_total_files,
            analysis_completed_files=task.analysis_completed_files,
            created_at=task.created_at.isoformat() if task.created_at else None,
            updated_at=task.updated_at.isoformat() if task.updated_at else None,
        )


class TaskListResponse(BaseModel):
    """任务列表响应"""
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TaskStatsResponse(BaseModel):
    """任务统计响应"""
    total: int
    pending: int
    running: int
    success: int
    failed: int


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("", response_model=TaskListResponse)
async def list_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词（文件名或任务ID）"),
    status: Optional[str] = Query(None, description="状态过滤"),
    user_id: Optional[int] = Query(None, description="用户ID过滤"),
    current_user: User = Depends(require_admin)
):
    """
    获取分析任务列表

    支持分页和搜索
    """
    tasks, total = task_repository.get_all_tasks_paginated(
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        user_id=user_id
    )

    total_pages = (total + page_size - 1) // page_size

    # Get user info for each task
    task_responses = []
    user_cache = {}  # Cache user lookups

    for task in tasks:
        user = None
        if task.user_id:
            if task.user_id not in user_cache:
                user_cache[task.user_id] = get_user_by_id(task.user_id)
            user = user_cache[task.user_id]

        task_responses.append(TaskResponse.from_model(task, user))

    return TaskListResponse(
        items=task_responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/stats", response_model=TaskStatsResponse)
async def get_stats(
    current_user: User = Depends(require_admin)
):
    """获取任务统计信息"""
    stats = task_repository.get_task_stats()
    return TaskStatsResponse(**stats)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(require_admin)
):
    """获取单个任务详情"""
    task = task_repository.get_task_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    user = None
    if task.user_id:
        user = get_user_by_id(task.user_id)

    return TaskResponse.from_model(task, user)


@router.delete("/{task_id}")
async def remove_task(
    task_id: str,
    current_user: User = Depends(require_admin)
):
    """删除分析任务记录"""
    success = task_repository.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"message": "Task deleted successfully"}
