"""
Library Service

Business logic layer for Library management.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.exc import IntegrityError
from loguru import logger

from ...databases.postgres.repository import library_repository
from ...databases.postgres.entities import Library


class LibraryService:
    """Service for managing Library entities"""

    @staticmethod
    def create_library(library_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new library with validation.

        Args:
            library_data: Library fields

        Returns:
            Created library as dict

        Raises:
            ValueError: If validation fails or duplicate exists
        """
        # Validate required fields
        if not library_data.get('name'):
            raise ValueError("Library name is required")

        if not library_data.get('source'):
            raise ValueError("Library source is required")

        # Check for duplicates
        existing = library_repository.get_library_by_name(
            library_data['name'],
            library_data.get('giturl')
        )
        if existing:
            raise ValueError(f"Library already exists: {library_data['name']}")

        # Create library
        try:
            library = library_repository.create_library(library_data)
            return LibraryService._serialize_library(library)
        except IntegrityError as e:
            logger.error(f"Failed to create library: {e}")
            raise ValueError(f"Failed to create library: duplicate constraint violated")

    @staticmethod
    def get_library(library_id: int) -> Optional[Dict[str, Any]]:
        """
        Get library by ID.

        Args:
            library_id: Library ID

        Returns:
            Library dict or None if not found
        """
        library = library_repository.get_library_by_id(library_id)
        if not library:
            return None
        return LibraryService._serialize_library(library)

    @staticmethod
    def get_library_detail(library_id: int) -> Optional[Dict[str, Any]]:
        """
        Get library with source codes.

        Args:
            library_id: Library ID

        Returns:
            Library dict with source_codes or None if not found
        """
        library = library_repository.get_library_with_source_codes(library_id)
        if not library:
            return None

        result = LibraryService._serialize_library(library)
        # Add source codes
        result['source_codes'] = [
            LibraryService._serialize_source_code(sc)
            for sc in library.source_codes
        ]
        return result

    @staticmethod
    def list_libraries(
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        vendor: Optional[str] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> Dict[str, Any]:
        """
        List libraries with pagination.

        Args:
            page: Page number
            page_size: Items per page
            search: Search term
            vendor: Vendor filter
            order_by: Order by field
            order_desc: Descending order

        Returns:
            Dict with items and pagination info
        """
        libraries, total = library_repository.list_libraries(
            page=page,
            page_size=page_size,
            search=search,
            vendor=vendor,
            order_by=order_by,
            order_desc=order_desc
        )

        return {
            'items': [LibraryService._serialize_library(lib) for lib in libraries],
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        }

    @staticmethod
    def update_library(library_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update library.

        Args:
            library_id: Library ID
            update_data: Fields to update

        Returns:
            Updated library dict or None if not found

        Raises:
            ValueError: If validation fails or duplicate exists
        """
        # Check if library exists
        existing = library_repository.get_library_by_id(library_id)
        if not existing:
            return None

        # Validate unique constraint if name/giturl changed
        if 'name' in update_data or 'giturl' in update_data:
            new_name = update_data.get('name', existing.name)
            new_giturl = update_data.get('giturl', existing.giturl)

            duplicate = library_repository.get_library_by_name(new_name, new_giturl)
            if duplicate and duplicate.id != library_id:
                raise ValueError(f"Library with this name and giturl already exists")

        # Update
        try:
            updated = library_repository.update_library(library_id, update_data)
            return LibraryService._serialize_library(updated) if updated else None
        except IntegrityError as e:
            logger.error(f"Failed to update library {library_id}: {e}")
            raise ValueError("Failed to update library: constraint violated")

    @staticmethod
    def delete_library(library_id: int, cascade: bool = False) -> bool:
        """
        Delete library.

        Args:
            library_id: Library ID
            cascade: If True, delete related SourceCodes

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If has related data and cascade=False
        """
        try:
            return library_repository.delete_library(library_id, cascade=cascade)
        except ValueError as e:
            # Re-raise validation error from repository
            raise e

    @staticmethod
    def _serialize_library(library: Library) -> Dict[str, Any]:
        """Serialize Library entity to dict"""
        return {
            'id': library.id,
            'name': library.name,
            'vendor': library.vendor,
            'source': library.source,
            'homepage': library.homepage,
            'giturl': library.giturl,
            'alias': library.alias,
            'description': library.description,
            'purl': library.purl,
            'language': library.language,
            'categories': library.categories,
            'created_at': library.created_at.isoformat() if library.created_at else None,
            'updated_at': library.updated_at.isoformat() if library.updated_at else None,
        }

    @staticmethod
    def _serialize_source_code(source_code) -> Dict[str, Any]:
        """Serialize SourceCode entity to dict (minimal)"""
        # 检查是否有提取的特征（通过 project_features relationship）
        has_features = bool(source_code.project_features) if source_code.project_features is not None else False

        return {
            'id': source_code.id,
            'commit_id': source_code.commit_id,
            'semantic_version_str': source_code.semantic_version_str,
            'version_source': source_code.version_source,
            'commit_datetime': source_code.commit_datetime.isoformat() if source_code.commit_datetime else None,
            'has_features': has_features,
        }

    # ============ Library Related Data Methods ============

    @staticmethod
    def get_library_vulnerabilities(
        library_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get vulnerabilities for a library.

        Args:
            library_id: Library ID
            page: Page number
            page_size: Items per page

        Returns:
            Dict with items and pagination info
        """
        vulnerabilities, total = library_repository.get_vulnerabilities_by_library(
            library_id=library_id,
            page=page,
            page_size=page_size
        )

        return {
            'items': vulnerabilities,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 0
        }

    @staticmethod
    def get_library_binaries(
        library_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get binaries for a library.

        Args:
            library_id: Library ID
            page: Page number
            page_size: Items per page

        Returns:
            Dict with items and pagination info
        """
        binaries, total = library_repository.get_binaries_by_library(
            library_id=library_id,
            page=page,
            page_size=page_size
        )

        return {
            'items': binaries,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 0
        }

    @staticmethod
    def get_library_string_features(
        library_id: int,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get string features for a library.

        Args:
            library_id: Library ID
            page: Page number
            page_size: Items per page
            search: Optional search term

        Returns:
            Dict with items and pagination info
        """
        strings, total = library_repository.get_string_features_by_library(
            library_id=library_id,
            page=page,
            page_size=page_size,
            search=search
        )

        return {
            'items': strings,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 0
        }

    @staticmethod
    def get_library_function_names(
        library_id: int,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get function names for a library.

        Args:
            library_id: Library ID
            page: Page number
            page_size: Items per page
            search: Optional search term

        Returns:
            Dict with items and pagination info
        """
        function_names, total = library_repository.get_function_names_by_library(
            library_id=library_id,
            page=page,
            page_size=page_size,
            search=search
        )

        return {
            'items': function_names,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 0
        }
