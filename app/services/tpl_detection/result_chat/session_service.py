"""
Session Service

Manages chat session data in Redis with TTL.
"""
import json
import uuid
from typing import Optional, Dict, Any, Tuple
from loguru import logger

from ....databases.redis.redis_clients import result_chat_redis_client


# Configuration constants
SESSION_TTL_SECONDS = 1800  # 30 minutes
SESSION_KEY_PREFIX = "result_chat_session"


class SessionService:
    """Service for managing chat sessions"""

    @staticmethod
    def get_session_key(session_id: str) -> str:
        """
        Generate Redis key for session.

        Args:
            session_id: The session ID

        Returns:
            Redis key string
        """
        return f"{SESSION_KEY_PREFIX}:{session_id}"

    @staticmethod
    def get_or_create_session(
        session_id: Optional[str],
        task_id: str,
        result_minio_path: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Get existing session or create new one.

        Args:
            session_id: Optional session ID (generates new if None)
            task_id: TPL detection task ID
            result_minio_path: MinIO path to result file

        Returns:
            Tuple of (session_id, session_data)
        """
        # Generate session_id if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"Generated new session ID: {session_id}")

        session_key = SessionService.get_session_key(session_id)

        # Try to get existing session
        session_data_raw = result_chat_redis_client.get(session_key)

        if session_data_raw:
            # Session exists - update TTL
            session_data = json.loads(session_data_raw.decode('utf-8'))
            SessionService._extend_session_ttl(session_key, session_data)
            logger.info(f"Retrieved existing session: {session_id}")
        else:
            # Create new session
            session_data = {
                'task_id': task_id,
                'result_minio_path': result_minio_path,
                'created_at': str(uuid.uuid4())  # Timestamp placeholder
            }
            SessionService._save_session(session_key, session_data)
            logger.info(f"Created new session: {session_id}")

        return session_id, session_data

    @staticmethod
    def clear_session(session_id: str) -> bool:
        """
        Clear chat history for a session.

        Args:
            session_id: The session ID to clear

        Returns:
            True if session was deleted, False if not found
        """
        session_key = SessionService.get_session_key(session_id)
        deleted = result_chat_redis_client.delete(session_key)

        if deleted > 0:
            logger.info(f"Cleared session: {session_id}")
            return True
        else:
            logger.warning(f"Session not found: {session_id}")
            return False

    @staticmethod
    def _save_session(session_key: str, session_data: Dict[str, Any]) -> None:
        """Save session data to Redis with TTL."""
        result_chat_redis_client.setex(
            session_key,
            SESSION_TTL_SECONDS,
            json.dumps(session_data, ensure_ascii=False)
        )

    @staticmethod
    def _extend_session_ttl(session_key: str, session_data: Dict[str, Any]) -> None:
        """Extend session TTL by updating last access time."""
        session_data['last_access'] = str(uuid.uuid4())  # Timestamp placeholder
        result_chat_redis_client.setex(
            session_key,
            SESSION_TTL_SECONDS,
            json.dumps(session_data, ensure_ascii=False)
        )
