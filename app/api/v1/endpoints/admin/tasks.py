"""
Admin Tasks API

管理后台分析任务管理接口
"""
import json
import threading
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from .....services.auth import require_admin
from .....databases.user_data.repository import task_repository, get_user_by_id
from .....databases.user_data.models import User, AnalysisTask
from .....databases.redis.redis_clients import tpl_detection_task_redis_client
from .....celery_tasks.celery_app import celery_app
from .....celery_tasks.tpl_detection_task import get_celery_task_id

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
    cancelled: int = 0


class CancelTaskResponse(BaseModel):
    """取消任务响应"""
    success: bool
    message: str
    task_id: str


class BatchCancelRequest(BaseModel):
    """批量取消任务请求"""
    task_ids: List[str]


class BatchCancelResult(BaseModel):
    """单个任务取消结果"""
    task_id: str
    success: bool
    error: Optional[str] = None


class BatchCancelResponse(BaseModel):
    """批量取消任务响应"""
    results: List[BatchCancelResult]


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


# =============================================================================
# Task Cancellation Functions
# =============================================================================

def _force_revoke_after_timeout(task_id: str, timeout: int = 30):
    """
    后台线程：超时后强制终止任务

    Args:
        task_id: BLADE 任务 ID
        timeout: 等待时间（秒）
    """
    import time
    time.sleep(timeout)

    # 检查任务是否仍在运行
    task_json = tpl_detection_task_redis_client.get(task_id)
    if task_json:
        try:
            task_info = json.loads(task_json.decode('utf-8'))
            if task_info.get('status') == 'cancelling':
                # 任务仍在运行，强制终止
                celery_task_id = get_celery_task_id(task_id)
                if celery_task_id:
                    print(f"任务 {task_id} 超时未停止，强制终止 Celery 任务 {celery_task_id}")
                    celery_app.control.revoke(celery_task_id, terminate=True, signal='SIGTERM')

                # 更新状态为已取消
                task_info['status'] = 'cancelled'
                task_info['error_message'] = '任务被强制终止'
                task_info['end_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                tpl_detection_task_redis_client.set(task_id, json.dumps(task_info, ensure_ascii=False))

                # 更新 PostgreSQL
                task_repository.update_task_completed(
                    task_id=task_id,
                    status='cancelled',
                    error_message='任务被强制终止'
                )
        except Exception as e:
            print(f"强制终止任务 {task_id} 失败: {e}")


def _cancel_single_task(task_id: str, requested_by: str = "admin") -> CancelTaskResponse:
    """
    取消单个任务的内部逻辑

    Args:
        task_id: 任务 ID
        requested_by: 请求取消的用户

    Returns:
        CancelTaskResponse
    """
    # 1. 验证任务存在
    task_json = tpl_detection_task_redis_client.get(task_id)
    if not task_json:
        raise HTTPException(status_code=404, detail="任务不存在")

    task_info = json.loads(task_json.decode('utf-8'))
    current_status = task_info.get('status')

    # 2. 检查任务是否可以取消
    non_cancellable = ['success', 'failed', 'cancelled', 'cancelling']
    if current_status in non_cancellable:
        raise HTTPException(
            status_code=400,
            detail=f"任务状态为 {current_status}，无法取消"
        )

    # 3. 设置取消标志
    cancel_key = f"task_cancel:{task_id}"
    cancel_info = {
        "requested_at": datetime.now().isoformat(),
        "requested_by": requested_by,
        "reason": "admin_requested"
    }
    tpl_detection_task_redis_client.set(
        cancel_key,
        json.dumps(cancel_info),
        ex=3600  # 1小时过期
    )

    # 4. 更新任务状态为 CANCELLING
    task_info['status'] = 'cancelling'
    tpl_detection_task_redis_client.set(task_id, json.dumps(task_info, ensure_ascii=False))

    # 5. 启动后台线程，30秒后强制终止
    threading.Thread(
        target=_force_revoke_after_timeout,
        args=(task_id, 30),
        daemon=True
    ).start()

    return CancelTaskResponse(
        success=True,
        message="取消请求已发送",
        task_id=task_id
    )


@router.post("/{task_id}/cancel", response_model=CancelTaskResponse)
async def cancel_task(
    task_id: str,
    current_user: User = Depends(require_admin)
):
    """
    取消正在执行的分析任务

    管理员可以取消任意任务。取消操作会：
    1. 设置取消标志，让正在执行的任务检测到取消请求
    2. 更新任务状态为 CANCELLING
    3. 30秒后如果任务仍未停止，强制终止 Celery 任务
    """
    return _cancel_single_task(task_id, f"admin:{current_user.id}")


@router.post("/batch-cancel", response_model=BatchCancelResponse)
async def batch_cancel_tasks(
    request: BatchCancelRequest,
    current_user: User = Depends(require_admin)
):
    """
    批量取消多个分析任务

    返回每个任务的取消结果
    """
    results = []
    for task_id in request.task_ids:
        try:
            _cancel_single_task(task_id, f"admin:{current_user.id}")
            results.append(BatchCancelResult(task_id=task_id, success=True))
        except HTTPException as e:
            results.append(BatchCancelResult(task_id=task_id, success=False, error=e.detail))
        except Exception as e:
            results.append(BatchCancelResult(task_id=task_id, success=False, error=str(e)))

    return BatchCancelResponse(results=results)
