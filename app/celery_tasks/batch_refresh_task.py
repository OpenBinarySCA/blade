"""
Batch Refresh Task

批量刷新所有 Library Status 的 Celery 异步任务
"""
import json
from datetime import datetime
from loguru import logger

from .celery_app import celery_app
from ..databases.redis.redis_clients import batch_refresh_task_redis_client
from ..interface import BatchRefreshTask, BatchRefreshStatus
from ..services.data_management.batch_refresh_service import batch_refresh_all_library_status
from ..config import settings


def _get_batch_refresh_task_from_redis(task_id: str) -> BatchRefreshTask:
    """
    从 Redis 中获取任务信息并初始化 BatchRefreshTask 对象

    Args:
        task_id: 任务 ID

    Returns:
        BatchRefreshTask object
    """
    redis_key = f"batch_refresh_task:{task_id}"
    task_info_json = batch_refresh_task_redis_client.get(redis_key)

    if not task_info_json:
        error_msg = f"No task found for task_id: {task_id}"
        logger.error(error_msg)
        # 创建一个失败的任务对象
        task = BatchRefreshTask(
            task_id=task_id,
            status=BatchRefreshStatus.FAILED,
            error_message=error_msg,
            end_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        _update_batch_refresh_task_redis(task)
        return task

    try:
        task_info = json.loads(task_info_json.decode('utf-8'))
        return BatchRefreshTask.init_from_dict(task_info)
    except Exception as e:
        error_msg = f"Failed to parse task info for task_id {task_id}: {str(e)}"
        logger.error(error_msg)
        # 创建一个失败的任务对象
        task = BatchRefreshTask(
            task_id=task_id,
            status=BatchRefreshStatus.FAILED,
            error_message=error_msg,
            end_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        _update_batch_refresh_task_redis(task)
        return task


def _update_batch_refresh_task_redis(task: BatchRefreshTask):
    """
    更新 Redis 中的任务信息，设置 3 小时过期时间

    Args:
        task: BatchRefreshTask object
    """
    try:
        redis_key = f"batch_refresh_task:{task.task_id}"
        task_json = task.customer_serialize()

        # 设置任务信息到 Redis，3 小时过期 (10800 秒)
        batch_refresh_task_redis_client.setex(
            redis_key,
            10800,  # 3 hours TTL
            json.dumps(task_json, ensure_ascii=False)
        )

        logger.debug(f"Task {task.task_id} status updated to: {task.status.value}")

    except Exception as e:
        logger.error(f"Failed to update Redis task info: {e}")


@celery_app.task
def batch_refresh_library_status_task(task_id: str):
    """
    批量刷新所有 Library Status 的异步任务

    Args:
        task_id: 任务 ID

    Returns:
        任务完成后的 JSON 数据
    """
    logger.info(f"Starting batch refresh task: {task_id}")

    # 1. 从 Redis 获取任务信息
    task = _get_batch_refresh_task_from_redis(task_id)

    if task.status == BatchRefreshStatus.FAILED:
        # 如果任务初始化就失败了，直接返回
        logger.error(f"Task {task_id} initialization failed, returning error info")
        return task.customer_serialize()

    try:
        # 2. 定义进度更新 hook（每完成一个 library 就更新 Redis）
        def update_progress_hook(completed: int, total: int, lib_info: dict, success: bool):
            """
            进度更新回调函数

            Args:
                completed: 已完成数量
                total: 总数量
                lib_info: 当前 library 信息 {library_id, library_name, success, error}
                success: 是否成功
            """
            # 更新任务状态
            task.total_libraries = total
            task.completed_libraries = completed
            task.current_library_id = lib_info['library_id']
            task.current_library_name = lib_info['library_name']

            if not success:
                # 记录失败的 library
                task.failed_libraries += 1
                task.failed_library_details[lib_info['library_id']] = lib_info['error']

            # 更新到 Redis
            _update_batch_refresh_task_redis(task)

            logger.debug(f"Progress: {completed}/{total}, Current: {lib_info['library_name']}, Success: {success}")

        # 3. 执行批量刷新（传入 progress hook）
        task.status = BatchRefreshStatus.RUNNING
        _update_batch_refresh_task_redis(task)

        logger.info("Calling batch_refresh_all_library_status...")

        success_count, failed_count, failed_details = batch_refresh_all_library_status(
            progress_hook=update_progress_hook,
            max_workers=getattr(settings, 'BATCH_REFRESH_CONCURRENCY', 4)  # 从配置读取并发数
        )

        logger.info(f"Batch refresh completed: {success_count} succeeded, {failed_count} failed")

        # 4. 设置最终状态
        if failed_count == 0:
            task.status = BatchRefreshStatus.SUCCESS
        elif success_count > 0:
            task.status = BatchRefreshStatus.PARTIAL_SUCCESS
        else:
            task.status = BatchRefreshStatus.FAILED
            task.error_message = "All libraries failed to refresh"

        task.end_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _update_batch_refresh_task_redis(task)

        logger.info(f"Task {task_id} finished with status: {task.status.value}")

        # 返回任务完成后的 JSON
        return task.customer_serialize()

    except Exception as e:
        # 捕获任何异常
        error_msg = f"Task execution failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        task.status = BatchRefreshStatus.FAILED
        task.error_message = error_msg
        task.end_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 更新任务状态为失败
        _update_batch_refresh_task_redis(task)

        # 返回任务的 JSON
        return task.customer_serialize()
