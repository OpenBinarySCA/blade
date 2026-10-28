"""
Batch Refresh Service

批量刷新所有 Library Status 的业务逻辑
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional, Tuple, List, Dict
import time
from loguru import logger

from ...databases.postgres.repository import library_repository, library_status_repository


def batch_refresh_all_library_status(
    progress_hook: Optional[Callable[[int, int, Dict, bool], None]] = None,
    max_workers: int = 4
) -> Tuple[int, int, List[Dict]]:
    """
    批量刷新所有 library status（并发执行，带重试机制）

    Args:
        progress_hook: 进度回调函数 (completed, total, current_lib_info, success)
        max_workers: 并发线程数，默认 4

    Returns:
        Tuple[成功数, 失败数, 失败详情列表]
    """
    logger.info("Starting batch refresh of all library statuses")

    # 1. 获取所有 library IDs
    library_ids = library_repository.list_all_library_ids()
    total = len(library_ids)
    logger.info(f"Found {total} libraries to refresh")

    if total == 0:
        logger.warning("No libraries found to refresh")
        return (0, 0, [])

    completed = 0
    failed_details = []

    def refresh_single_library(lib_id: int) -> Dict:
        """
        刷新单个 library status，带重试机制

        Args:
            lib_id: Library ID

        Returns:
            结果字典包含：library_id, library_name, success, error
        """
        MAX_RETRIES = 2  # 最多重试 2 次（总共 3 次尝试）

        # 获取 library 信息用于日志
        library = library_repository.get_library_by_id(lib_id)
        library_name = library.name if library else f'ID:{lib_id}'

        last_error = None
        for attempt in range(MAX_RETRIES + 1):  # 0, 1, 2
            try:
                # 执行刷新
                library_status_repository.refresh_library_status(lib_id)

                logger.debug(f"Successfully refreshed library {lib_id} ({library_name}) on attempt {attempt + 1}")
                return {
                    'library_id': lib_id,
                    'library_name': library_name,
                    'success': True,
                    'error': None
                }

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed for library {lib_id} ({library_name}): {e}")

                if attempt < MAX_RETRIES:
                    # 还有重试机会，等待一小段时间后重试
                    time.sleep(0.5)  # 等待 500ms
                else:
                    # 所有尝试都失败了
                    logger.error(f"All {MAX_RETRIES + 1} attempts failed for library {lib_id} ({library_name})")

        # 所有重试都失败
        return {
            'library_id': lib_id,
            'library_name': library_name,
            'success': False,
            'error': last_error
        }

    # 2. 使用线程池并发处理
    logger.info(f"Starting concurrent refresh with {max_workers} workers")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_lib = {executor.submit(refresh_single_library, lid): lid for lid in library_ids}

        # 处理完成的任务
        for future in as_completed(future_to_lib):
            result = future.result()
            completed += 1

            if not result['success']:
                # 失败的记录下来
                failed_details.append(result)

            # 调用进度 hook
            if progress_hook:
                try:
                    progress_hook(completed, total, result, result['success'])
                except Exception as e:
                    logger.error(f"Progress hook failed: {e}")

    # 3. 计算结果
    success_count = completed - len(failed_details)
    failed_count = len(failed_details)

    logger.info(f"Batch refresh completed: {success_count} succeeded, {failed_count} failed")

    return (success_count, failed_count, failed_details)
