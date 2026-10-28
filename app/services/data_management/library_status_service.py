"""
Library Status Service

Business logic layer for Library Status management.
"""
from typing import Dict, Any, Optional
from loguru import logger

from ...databases.postgres.repository import library_status_repository
from ...databases.postgres.entities import LibraryStatus


class LibraryStatusService:
    """Service for managing LibraryStatus entities"""

    @staticmethod
    def get_library_status(library_id: int) -> Optional[Dict[str, Any]]:
        """
        Get library status by library ID.

        Args:
            library_id: Library ID

        Returns:
            Status dict or None if not found
        """
        status = library_status_repository.get_library_status(library_id)
        if not status:
            return None
        return LibraryStatusService._serialize_status(status)

    @staticmethod
    def get_or_create_library_status(library_id: int) -> Optional[Dict[str, Any]]:
        """
        Get or create library status.

        Args:
            library_id: Library ID

        Returns:
            Status dict or None if library not found
        """
        status = library_status_repository.get_or_create_library_status(library_id)
        if not status:
            return None
        return LibraryStatusService._serialize_status(status)

    @staticmethod
    def refresh_library_status(library_id: int) -> Optional[Dict[str, Any]]:
        """
        Refresh library status by recalculating based on current data.

        This will:
        1. Check basic info completeness
        2. Check if has description
        3. Count source codes
        4. Count string features
        5. Count function name features
        6. Count binaries
        7. Count vulnerabilities

        Args:
            library_id: Library ID

        Returns:
            Refreshed status dict or None if library not found
        """
        logger.info(f"Refreshing library status for library ID: {library_id}")
        status = library_status_repository.refresh_library_status(library_id)
        if not status:
            return None
        return LibraryStatusService._serialize_status(status)

    @staticmethod
    def update_library_status(library_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Manually update library status fields.

        Note: Usually you should use refresh_library_status instead.

        Args:
            library_id: Library ID
            update_data: Fields to update

        Returns:
            Updated status dict or None if not found
        """
        status = library_status_repository.update_library_status(library_id, update_data)
        if not status:
            return None
        return LibraryStatusService._serialize_status(status)

    @staticmethod
    def delete_library_status(library_id: int) -> bool:
        """
        Delete library status.

        Args:
            library_id: Library ID

        Returns:
            True if deleted, False if not found
        """
        return library_status_repository.delete_library_status(library_id)

    @staticmethod
    def _serialize_status(status: LibraryStatus) -> Dict[str, Any]:
        """
        Serialize LibraryStatus entity to dict.

        Args:
            status: LibraryStatus entity

        Returns:
            Dict representation
        """
        return {
            'id': status.id,
            'library_id': status.library_id,
            'has_basic_info': status.has_basic_info,
            'has_description': status.has_description,
            'has_features': status.has_features,
            'has_binaries': status.has_binaries,
            'has_vulnerabilities': status.has_vulnerabilities,
            'metadata_note': status.metadata_note,
            'features_note': status.features_note,
            'binaries_note': status.binaries_note,
            'vulnerabilities_note': status.vulnerabilities_note,
            'source_code_count': status.source_code_count,
            'string_feature_count': status.string_feature_count,
            'function_name_feature_count': status.function_name_feature_count,
            'binary_count': status.binary_count,
            'vulnerability_count': status.vulnerability_count,
            'last_refreshed_at': status.last_refreshed_at.isoformat() if status.last_refreshed_at else None,
            'created_at': status.created_at.isoformat() if status.created_at else None,
            'updated_at': status.updated_at.isoformat() if status.updated_at else None,
        }
