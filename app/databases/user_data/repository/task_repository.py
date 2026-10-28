"""
Task Repository - CRUD operations for AnalysisTask model
"""
from typing import Optional, List
from datetime import datetime

from ..models import AnalysisTask
from ..database import session_generator


def create_task(
    task_id: str,
    file_name: str,
    file_minio_path: str,
    input_file_sha256: str,
    engine_version: str,
    user_id: int = None
) -> AnalysisTask:
    """Create a new analysis task record"""
    with session_generator() as db:
        task = AnalysisTask(
            task_id=task_id,
            user_id=user_id,
            engine_version=engine_version,
            input_file_sha256=input_file_sha256,
            file_name=file_name,
            file_minio_path=file_minio_path,
            status="pending",
            start_at=datetime.now()
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task


def get_task_by_id(task_id: str) -> Optional[AnalysisTask]:
    """Get task by task_id"""
    with session_generator() as db:
        return db.query(AnalysisTask).filter(AnalysisTask.task_id == task_id).first()


def update_task_completed(
    task_id: str,
    status: str,
    result_minio_path: str = None,
    report_minio_path: str = None,
    error_message: str = None,
    analysis_total_files: int = 0,
    analysis_completed_files: int = 0
) -> Optional[AnalysisTask]:
    """Update task when completed (success or failed)"""
    with session_generator() as db:
        task = db.query(AnalysisTask).filter(AnalysisTask.task_id == task_id).first()
        if task:
            task.status = status
            task.end_at = datetime.now()
            task.result_minio_path = result_minio_path
            task.report_minio_path = report_minio_path
            task.error_message = error_message
            task.analysis_total_files = analysis_total_files
            task.analysis_completed_files = analysis_completed_files
            db.commit()
            db.refresh(task)
        return task


def list_tasks_by_user(user_id: int, limit: int = 50) -> List[AnalysisTask]:
    """List tasks by user ID, ordered by created_at descending"""
    with session_generator() as db:
        return db.query(AnalysisTask)\
            .filter(AnalysisTask.user_id == user_id)\
            .order_by(AnalysisTask.created_at.desc())\
            .limit(limit)\
            .all()


def list_all_tasks(limit: int = 100) -> List[AnalysisTask]:
    """List all tasks (for admin), ordered by created_at descending"""
    with session_generator() as db:
        return db.query(AnalysisTask)\
            .order_by(AnalysisTask.created_at.desc())\
            .limit(limit)\
            .all()


def delete_task(task_id: str) -> bool:
    """Delete a task by task_id"""
    with session_generator() as db:
        task = db.query(AnalysisTask).filter(AnalysisTask.task_id == task_id).first()
        if task:
            db.delete(task)
            db.commit()
            return True
        return False


def find_cached_task(input_file_sha256: str, engine_version: str) -> Optional[AnalysisTask]:
    """
    查找相同 SHA256 和引擎版本的成功任务（用于结果缓存）
    返回最新的成功任务

    Args:
        input_file_sha256: 输入文件的 SHA256 哈希
        engine_version: 引擎版本号

    Returns:
        最新成功的任务记录（如果存在），否则返回 None
    """
    with session_generator() as db:
        return db.query(AnalysisTask).filter(
            AnalysisTask.input_file_sha256 == input_file_sha256,
            AnalysisTask.engine_version == engine_version,
            AnalysisTask.status == "success"
        ).order_by(AnalysisTask.created_at.desc()).first()


# =============================================================================
# Admin functions
# =============================================================================

def get_all_tasks_paginated(
    page: int = 1,
    page_size: int = 20,
    search: str = None,
    status: str = None,
    user_id: int = None
) -> tuple[List[AnalysisTask], int]:
    """
    Get all tasks with pagination and filtering (for admin)

    Returns:
        Tuple of (tasks list, total count)
    """
    with session_generator() as db:
        query = db.query(AnalysisTask)

        # Apply filters
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (AnalysisTask.file_name.ilike(search_pattern)) |
                (AnalysisTask.task_id.ilike(search_pattern))
            )

        if status:
            query = query.filter(AnalysisTask.status == status)

        if user_id is not None:
            query = query.filter(AnalysisTask.user_id == user_id)

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        tasks = query.order_by(AnalysisTask.created_at.desc()).offset(offset).limit(page_size).all()

        return tasks, total


def get_task_stats() -> dict:
    """Get task statistics"""
    with session_generator() as db:
        from sqlalchemy import func

        total = db.query(AnalysisTask).count()
        pending = db.query(AnalysisTask).filter(AnalysisTask.status == "pending").count()
        running = db.query(AnalysisTask).filter(AnalysisTask.status.in_(
            ["running", "file_downloading", "unpacking", "unpacking_result_uploading",
             "analyzing", "result_uploading", "cancelling"]
        )).count()
        success = db.query(AnalysisTask).filter(AnalysisTask.status == "success").count()
        failed = db.query(AnalysisTask).filter(AnalysisTask.status == "failed").count()
        cancelled = db.query(AnalysisTask).filter(AnalysisTask.status == "cancelled").count()

        return {
            "total": total,
            "pending": pending,
            "running": running,
            "success": success,
            "failed": failed,
            "cancelled": cancelled
        }
