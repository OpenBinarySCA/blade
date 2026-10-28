from typing import Optional
import hashlib
from fastapi import APIRouter, HTTPException, Request, Depends
from .....celery_tasks.tpl_detection_task import tpl_detection_task, tpl_detection_task_redis_client
from .....interface import TPLDetectionTask, TPLDetectionTaskStatus
from .....services.storage.minio_service import download_from_minio, upload_to_minio
from .....services.report_generation import ReportService
from .....services.auth import get_current_user_optional
from .....databases.user_data.models import User
from .....databases.user_data.repository import task_repository, guest_repository
from .....config import settings
from ...schemas import TPLDetectionTaskRequest, GenerateReportRequest, GenerateReportResponse
import uuid
import json
import os
import tempfile
import shutil

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
            status=TPLDetectionTaskStatus.PENDING
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

        # 5. 直接返回task的json
        return task_json

    except HTTPException:
        raise
    except Exception as e:
        # 如果任务启动失败，返回错误信息
        raise HTTPException(status_code=500, detail=f"Task failed to start: {str(e)}")


@router.get("/tpl_detection_task")
def get_tpl_detection_task(task_id: str):
    """获取TPL检测任务信息"""
    redis_task_info = tpl_detection_task_redis_client.get(task_id)
    
    if not redis_task_info:
        raise HTTPException(status_code=404, detail="Task not found")
    
    try:
        task_info = json.loads(redis_task_info.decode('utf-8'))
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