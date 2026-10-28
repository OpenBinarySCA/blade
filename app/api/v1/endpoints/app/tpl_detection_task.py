from typing import Optional
import hashlib
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from .....celery_tasks.tpl_detection_task import tpl_detection_task, tpl_detection_task_redis_client, get_celery_task_id, save_celery_task_mapping
from .....celery_tasks.celery_app import celery_app
from .....interface import TPLDetectionTask, TPLDetectionTaskStatus
from .....services.storage.minio_service import download_from_minio, upload_to_minio
from .....services.report_generation import ReportService
from .....services.auth import get_current_user_optional
from .....databases.user_data.models import User
from .....databases.user_data.repository import task_repository, guest_repository, sample_repository
from .....config import settings
from ...schemas import TPLDetectionTaskRequest, GenerateReportRequest, GenerateReportResponse
import uuid
import json
import os
import tempfile
import shutil


class CancelTaskResponse(BaseModel):
    """取消任务响应"""
    success: bool
    message: str
    task_id: str

router = APIRouter()


def get_device_fingerprint(request: Request) -> tuple[str, str]:
    """Get device fingerprint from request for guest tracking"""
    # Get IP address
    ip = request.client.host if request.client else "unknown"
    # Try to get real IP from proxy headers
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()

    # Create device fingerprint from User-Agent + Accept-Language
    ua = request.headers.get("User-Agent", "")
    lang = request.headers.get("Accept-Language", "")
    fingerprint = hashlib.sha256(f"{ua}:{lang}".encode()).hexdigest()[:32]

    return ip, fingerprint


@router.post("/tpl_detection_task")    # 创建TPL检测任务
def create_tpl_detection_task(
    request: TPLDetectionTaskRequest,
    http_request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    if not request.file_minio_path:
        raise HTTPException(status_code=400, detail="File path is required")

    # Guest limit check (only for unauthenticated users)
    if not current_user:
        ip, fingerprint = get_device_fingerprint(http_request)
        if not guest_repository.can_use(ip, fingerprint, settings.GUEST_ANALYSIS_LIMIT):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "guest_limit_exceeded",
                    "message": "Free analysis limit reached. Please sign in to continue.",
                    "limit": settings.GUEST_ANALYSIS_LIMIT
                }
            )
        # Increment guest usage count
        guest_repository.increment_usage(ip, fingerprint)

    print('Starting TPL detection task for file:', request.file_minio_path)

    try:
        # 1. 创建任务对象，赋值id
        task_id = str(uuid.uuid4())
        task = TPLDetectionTask(
            task_id=task_id,
            file_minio_path=request.file_minio_path,
            status=TPLDetectionTaskStatus.PENDING,
            force_reanalyze=request.force_reanalyze
        )

        # 2. 将task信息转换成json存储到redis中
        task_json = task.customer_serialize()
        tpl_detection_task_redis_client.set(task_id, json.dumps(task_json, ensure_ascii=False))

        # 3. 写入PostgreSQL (持久化记录)
        task_repository.create_task(
            task_id=task_id,
            file_name=request.file_name,
            file_minio_path=request.file_minio_path,
            input_file_sha256=request.file_sha256,
            engine_version=settings.ENGINE_VERSION,
            user_id=current_user.id if current_user else None
        )

        # 4. 创建celery异步任务
        celery_task = tpl_detection_task.delay(task_id)

        # 5. 保存 Celery task ID 映射（用于取消任务时的兜底强杀）
        save_celery_task_mapping(task_id, celery_task.id)

        # 6. 直接返回task的json
        return task_json

    except HTTPException:
        raise
    except Exception as e:
        # 如果任务启动失败，返回错误信息
        raise HTTPException(status_code=500, detail=f"Task failed to start: {str(e)}")


@router.get("/tpl_detection_task")
def get_tpl_detection_task(task_id: str, request: Request):
    """获取TPL检测任务信息"""
    redis_task_info = tpl_detection_task_redis_client.get(task_id)

    if not redis_task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        task_info = json.loads(redis_task_info.decode('utf-8'))

        # Record sample view if this task belongs to a sample
        try:
            sample = sample_repository.get_sample_by_task_id(task_id)
            if sample:
                ip, _ = get_device_fingerprint(request)
                user_agent = request.headers.get("User-Agent", "")[:500]  # Limit length
                sample_repository.record_sample_view(sample.id, ip, user_agent)
        except Exception:
            pass  # Silently ignore recording errors

        return task_info
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid task info format")


@router.get("/tpl_detection_tasks")
def get_tpl_detection_tasks(
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取用户的TPL检测任务列表（从PostgreSQL）"""
    try:
        if current_user:
            # Logged-in user: return their tasks from PostgreSQL
            tasks = task_repository.list_tasks_by_user(current_user.id)
            return {"tasks": [task.to_dict() for task in tasks]}
        else:
            # Guest user: return empty list (no history for guests)
            return {"tasks": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tasks: {str(e)}")


@router.get("/guest_status")
def get_guest_status(request: Request):
    """获取访客剩余使用次数"""
    ip, fingerprint = get_device_fingerprint(request)
    count = guest_repository.get_usage_count(ip, fingerprint)
    limit = settings.GUEST_ANALYSIS_LIMIT

    return {
        "used": count,
        "limit": limit,
        "remaining": max(0, limit - count)
    }


@router.post("/generate_report", response_model=GenerateReportResponse)
def generate_report(request: GenerateReportRequest):
    """
    Generate report for a completed task.

    - If report already exists, returns the cached path
    - If not, generates PDF, Excel, CSV and packages into ZIP
    - Uploads to MinIO and returns the path
    """
    task_id = request.task_id

    # 1. Get task from Redis
    redis_task_info = tpl_detection_task_redis_client.get(task_id)
    if not redis_task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        task_info = json.loads(redis_task_info.decode('utf-8'))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid task info format")

    # 2. Check if task is completed
    if task_info.get('status') != TPLDetectionTaskStatus.SUCCESS.value:
        raise HTTPException(
            status_code=400,
            detail=f"Task is not completed. Current status: {task_info.get('status')}"
        )

    # 3. Check if report already exists
    existing_report_path = task_info.get('report_minio_path')
    if existing_report_path:
        return GenerateReportResponse(
            success=True,
            task_id=task_id,
            report_minio_path=existing_report_path,
            message="Report already exists"
        )

    # 4. Generate new report
    result_minio_path = task_info.get('result_minio_path')
    if not result_minio_path:
        raise HTTPException(status_code=400, detail="Task has no result file")

    temp_dir = None
    try:
        # Create temp directory for report generation
        temp_dir = tempfile.mkdtemp(prefix="blade_report_")

        # Download result JSON from MinIO
        result_local_path = download_from_minio(
            result_minio_path,
            temp_dir,
            bucket=settings.MINIO_OUTPUT_BUCKET
        )

        # Load result data
        result_data = ReportService.load_result_data(result_local_path)

        # Prepare task data for report
        task_data = {
            'task_id': task_id,
            'status': task_info.get('status'),
            'start_at': task_info.get('start_at'),
            'end_at': task_info.get('end_at'),
        }

        # Generate reports (PDF, Excel, CSV) and package into ZIP
        report_service = ReportService()
        zip_path = report_service.generate_reports(result_data, task_data, temp_dir)

        # Upload ZIP to MinIO
        task_folder = f"task_{task_id}"
        report_minio_path = f"{task_folder}/blade_report.zip"
        upload_to_minio(zip_path, report_minio_path, bucket=settings.MINIO_OUTPUT_BUCKET)

        # Update task with report path
        task_info['report_minio_path'] = report_minio_path
        tpl_detection_task_redis_client.set(task_id, json.dumps(task_info, ensure_ascii=False))

        return GenerateReportResponse(
            success=True,
            task_id=task_id,
            report_minio_path=report_minio_path,
            message="Report generated successfully"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

    finally:
        # Clean up temp directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


# =============================================================================
# Task Cancellation
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


@router.post("/tpl_detection_task/{task_id}/cancel", response_model=CancelTaskResponse)
def cancel_tpl_detection_task(
    task_id: str,
    http_request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    取消正在执行的TPL检测任务

    用户只能取消自己的任务（或访客可以取消当前会话中的任务）。
    取消操作会：
    1. 设置取消标志，让正在执行的任务检测到取消请求
    2. 更新任务状态为 CANCELLING
    3. 30秒后如果任务仍未停止，强制终止 Celery 任务
    """
    # 1. 验证任务存在
    task_json = tpl_detection_task_redis_client.get(task_id)
    if not task_json:
        raise HTTPException(status_code=404, detail="任务不存在")

    task_info = json.loads(task_json.decode('utf-8'))
    current_status = task_info.get('status')

    # 2. 验证用户权限（如果已登录，检查任务是否属于该用户）
    if current_user:
        # 从 PostgreSQL 获取任务信息以验证所有权
        db_task = task_repository.get_task_by_id(task_id)
        if db_task and db_task.user_id and db_task.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权取消此任务")

    # 3. 检查任务是否可以取消
    non_cancellable = ['success', 'failed', 'cancelled', 'cancelling']
    if current_status in non_cancellable:
        raise HTTPException(
            status_code=400,
            detail=f"任务状态为 {current_status}，无法取消"
        )

    # 4. 设置取消标志
    cancel_key = f"task_cancel:{task_id}"
    cancel_info = {
        "requested_at": datetime.now().isoformat(),
        "requested_by": current_user.id if current_user else "guest",
        "reason": "user_requested"
    }
    tpl_detection_task_redis_client.set(
        cancel_key,
        json.dumps(cancel_info),
        ex=3600  # 1小时过期
    )

    # 5. 更新任务状态为 CANCELLING
    task_info['status'] = 'cancelling'
    tpl_detection_task_redis_client.set(task_id, json.dumps(task_info, ensure_ascii=False))

    # 6. 启动后台线程，30秒后强制终止
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