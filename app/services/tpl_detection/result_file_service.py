"""
Result File Service

Manages retrieval of TPL detection result files.
Prioritizes local files, falls back to MinIO download.
"""
import os
import tempfile
from typing import Optional
from loguru import logger

from ..storage.minio_service import download_from_minio
from .task_service import TaskService
from ...config import settings


class ResultFileService:
    """Service for retrieving TPL detection result files"""

    @staticmethod
    def get_result_file_path(task_id: str, minio_path: str) -> str:
        """
        Get the local path to a result file.

        Strategy:
        1. Check if local file path exists in task info
        2. If local file exists, return it
        3. Otherwise, download from MinIO to temp directory

        Args:
            task_id: The TPL detection task ID
            minio_path: The MinIO object path for the result file

        Returns:
            Local file path to the result file

        Raises:
            FileNotFoundError: If file cannot be retrieved
            ValueError: If minio_path is not provided
        """
        if not minio_path:
            raise ValueError("minio_path is required")

        # Try to get local file path from task info
        local_path = ResultFileService._get_local_path_from_task(task_id)

        if local_path and os.path.exists(local_path):
            logger.info(f"Using local result file for task {task_id}: {local_path}")
            return local_path

        # Local file not available, download from MinIO
        logger.info(f"Local file not found, downloading from MinIO: {minio_path}")
        return ResultFileService._download_from_minio(minio_path)

    @staticmethod
    def _get_local_path_from_task(task_id: str) -> Optional[str]:
        """
        Get local result file path from task information.

        Args:
            task_id: The task ID

        Returns:
            Local file path or None if not found
        """
        try:
            task_info = TaskService.get_task_info(task_id)
            if not task_info:
                return None

            local_path = task_info.get('result_local_path')
            return local_path
        except Exception as e:
            logger.warning(f"Failed to get local path from task {task_id}: {e}")
            return None

    @staticmethod
    def _download_from_minio(minio_path: str) -> str:
        """
        Download result file from MinIO.

        Args:
            minio_path: The MinIO object path

        Returns:
            Local file path

        Raises:
            FileNotFoundError: If download fails
        """
        try:
            temp_dir = tempfile.mkdtemp()
            local_path = download_from_minio(
                minio_path,
                temp_dir,
                bucket=settings.MINIO_OUTPUT_BUCKET
            )
            logger.info(f"Downloaded result file to: {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"Failed to download from MinIO: {minio_path}, error: {e}")
            raise FileNotFoundError(f"Failed to download result file from MinIO: {str(e)}")
