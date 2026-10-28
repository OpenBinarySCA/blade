"""
TPL Detection Task Service

Manages TPL detection task information stored in Redis.
"""
import json
from typing import Optional, Dict, Any
from loguru import logger

from ...databases.redis.redis_clients import tpl_detection_task_redis_client


class TaskService:
    """Service for managing TPL detection tasks"""

    @staticmethod
    def get_task_info(task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task information from Redis.

        Args:
            task_id: The task ID

        Returns:
            Task information dict or None if not found
        """
        try:
            task_data_raw = tpl_detection_task_redis_client.get(task_id)
            if not task_data_raw:
                logger.warning(f"Task not found in Redis: {task_id}")
                return None

            task_data = json.loads(task_data_raw.decode('utf-8'))
            return task_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse task data for {task_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get task info for {task_id}: {e}")
            return None

    @staticmethod
    def update_task_info(task_id: str, task_data: Dict[str, Any]) -> bool:
        """
        Update task information in Redis.

        Args:
            task_id: The task ID
            task_data: Task data dict to store

        Returns:
            True if successful, False otherwise
        """
        try:
            task_json = json.dumps(task_data, ensure_ascii=False)
            tpl_detection_task_redis_client.set(task_id, task_json)
            logger.debug(f"Updated task info for {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update task info for {task_id}: {e}")
            return False

    @staticmethod
    def task_exists(task_id: str) -> bool:
        """
        Check if a task exists in Redis.

        Args:
            task_id: The task ID

        Returns:
            True if task exists, False otherwise
        """
        return tpl_detection_task_redis_client.exists(task_id) > 0
