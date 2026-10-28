"""
SourceCode Service

Business logic layer for SourceCode management.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.exc import IntegrityError
from loguru import logger

from ...databases.postgres.repository import source_code_repository, library_repository
from ...databases.postgres.entities import SourceCode


class SourceCodeService:
    """Service for managing SourceCode entities"""

    @staticmethod
    def create_source_code(source_code_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new source code record with validation.

        Args:
            source_code_data: SourceCode fields

        Returns:
            Created source code as dict

        Raises:
            ValueError: If validation fails or duplicate exists
        """
        # Validate required fields
        if not source_code_data.get('library_id'):
            raise ValueError("library_id is required")

        if not source_code_data.get('commit_id'):
            raise ValueError("commit_id is required")

        # Validate library exists
        library = library_repository.get_library_by_id(source_code_data['library_id'])
        if not library:
            raise ValueError(f"Library not found: ID {source_code_data['library_id']}")

        # Check for duplicates
        existing = source_code_repository.get_source_code_by_commit(
            source_code_data['library_id'],
            source_code_data['commit_id']
        )
        if existing:
            raise ValueError(f"SourceCode already exists for this library and commit")

        # Create source code
        try:
            source_code = source_code_repository.create_source_code(source_code_data)
            return SourceCodeService._serialize_source_code(source_code)
        except IntegrityError as e:
            logger.error(f"Failed to create source code: {e}")
            raise ValueError("Failed to create source code: constraint violated")

    @staticmethod
    def get_source_code(source_code_id: int) -> Optional[Dict[str, Any]]:
        """
        Get source code by ID.

        Args:
            source_code_id: SourceCode ID

        Returns:
            SourceCode dict or None if not found
        """
        source_code = source_code_repository.get_source_code_by_id(source_code_id)
        if not source_code:
            return None
        return SourceCodeService._serialize_source_code(source_code)

    @staticmethod
    def get_source_code_with_library(source_code_id: int) -> Optional[Dict[str, Any]]:
        """
        Get source code with library information.

        Args:
            source_code_id: SourceCode ID

        Returns:
            SourceCode dict with library info or None if not found
        """
        source_code = source_code_repository.get_source_code_with_library(source_code_id)
        if not source_code:
            return None

        result = SourceCodeService._serialize_source_code(source_code)
        if source_code.library:
            result['library'] = {
                'id': source_code.library.id,
                'name': source_code.library.name,
                'vendor': source_code.library.vendor,
            }
        return result

    @staticmethod
    def list_source_codes_by_library(
        library_id: int,
        page: int = 1,
        page_size: int = 50,
        order_by: str = "commit_datetime",
        order_desc: bool = True
    ) -> Dict[str, Any]:
        """
        List source codes for a specific library.

        Args:
            library_id: Library ID
            page: Page number
            page_size: Items per page
            order_by: Order by field
            order_desc: Descending order

        Returns:
            Dict with items and pagination info
        """
        source_codes, total = source_code_repository.list_source_codes_by_library(
            library_id=library_id,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_desc=order_desc
        )

        return {
            'items': [SourceCodeService._serialize_source_code(sc) for sc in source_codes],
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        }

    @staticmethod
    def list_all_source_codes(
        page: int = 1,
        page_size: int = 20,
        library_id: Optional[int] = None,
        version_source: Optional[str] = None,
        order_by: str = "commit_datetime",
        order_desc: bool = True
    ) -> Dict[str, Any]:
        """
        List all source codes with pagination and filters.

        Args:
            page: Page number
            page_size: Items per page
            library_id: Optional filter by library
            version_source: Optional filter by version source
            order_by: Order by field
            order_desc: Descending order

        Returns:
            Dict with items and pagination info
        """
        source_codes, total = source_code_repository.list_all_source_codes(
            page=page,
            page_size=page_size,
            library_id=library_id,
            version_source=version_source,
            order_by=order_by,
            order_desc=order_desc
        )

        return {
            'items': [SourceCodeService._serialize_source_code(sc) for sc in source_codes],
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        }

    @staticmethod
    def update_source_code(source_code_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update source code.

        Args:
            source_code_id: SourceCode ID
            update_data: Fields to update

        Returns:
            Updated source code dict or None if not found

        Raises:
            ValueError: If validation fails
        """
        # Check if source code exists
        existing = source_code_repository.get_source_code_by_id(source_code_id)
        if not existing:
            return None

        # Validate library_id if changed
        if 'library_id' in update_data:
            library = library_repository.get_library_by_id(update_data['library_id'])
            if not library:
                raise ValueError(f"Library not found: ID {update_data['library_id']}")

        # Check for duplicate if library_id or commit_id changed
        if 'library_id' in update_data or 'commit_id' in update_data:
            new_library_id = update_data.get('library_id', existing.library_id)
            new_commit_id = update_data.get('commit_id', existing.commit_id)

            duplicate = source_code_repository.get_source_code_by_commit(new_library_id, new_commit_id)
            if duplicate and duplicate.id != source_code_id:
                raise ValueError("SourceCode with this library and commit already exists")

        # Update
        try:
            updated = source_code_repository.update_source_code(source_code_id, update_data)
            return SourceCodeService._serialize_source_code(updated) if updated else None
        except IntegrityError as e:
            logger.error(f"Failed to update source code {source_code_id}: {e}")
            raise ValueError("Failed to update source code: constraint violated")

    @staticmethod
    def delete_source_code(source_code_id: int) -> bool:
        """
        Delete source code.

        Args:
            source_code_id: SourceCode ID

        Returns:
            True if deleted, False if not found
        """
        return source_code_repository.delete_source_code(source_code_id)

    @staticmethod
    def _serialize_source_code(source_code: SourceCode) -> Dict[str, Any]:
        """Serialize SourceCode entity to dict"""
        # 检查是否有提取的特征（通过 project_features relationship）
        has_features = bool(source_code.project_features) if source_code.project_features is not None else False

        return {
            'id': source_code.id,
            'library_id': source_code.library_id,
            'commit_id': source_code.commit_id,
            'version_source': source_code.version_source,
            'original_version_strs': source_code.original_version_strs,
            'semantic_version_str': source_code.semantic_version_str,
            'commit_datetime': source_code.commit_datetime.isoformat() if source_code.commit_datetime else None,
            'tag_datetime': source_code.tag_datetime.isoformat() if source_code.tag_datetime else None,
            'created_at': source_code.created_at.isoformat() if source_code.created_at else None,
            'updated_at': source_code.updated_at.isoformat() if source_code.updated_at else None,
            'has_features': has_features,
        }
