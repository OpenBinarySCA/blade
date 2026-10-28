"""
SourceCode Repository - Data access layer for SourceCode entity
"""
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import func
from loguru import logger

from ..entities import SourceCode, Library
from ..postgres import session_generator


def create_source_code(source_code_data: Dict[str, Any]) -> SourceCode:
    """
    Create a new source code record.

    Args:
        source_code_data: Dictionary containing source code fields

    Returns:
        Created SourceCode object

    Raises:
        IntegrityError: If unique constraint violated or library_id invalid
    """
    with session_generator() as session:
        source_code = SourceCode(**source_code_data)
        session.add(source_code)
        session.flush()
        session.refresh(source_code)
        # logger.info(f"Created source code: {source_code.semantic_version_str} (ID: {source_code.id})")
        return source_code


def get_source_code_by_id(source_code_id: int) -> Optional[SourceCode]:
    """
    Get source code by ID.

    Args:
        source_code_id: SourceCode ID

    Returns:
        SourceCode object or None if not found
    """
    with session_generator() as session:
        source_code = session.query(SourceCode).filter(SourceCode.id == source_code_id).first()
        if source_code:
            session.expunge(source_code)
        return source_code


def get_source_code_by_commit(library_id: int, commit_id: str) -> Optional[SourceCode]:
    """
    Get source code by library_id and commit_id.

    Args:
        library_id: Library ID
        commit_id: Git commit ID

    Returns:
        SourceCode object or None if not found
    """
    with session_generator() as session:
        source_code = session.query(SourceCode)\
            .filter(SourceCode.library_id == library_id)\
            .filter(SourceCode.commit_id == commit_id)\
            .first()
        if source_code:
            session.expunge(source_code)
        return source_code


def list_source_codes_by_library(
    library_id: int,
    page: int = 1,
    page_size: int = 50,
    order_by: str = "commit_datetime",
    order_desc: bool = True
) -> Tuple[List[SourceCode], int]:
    """
    List source codes for a specific library with pagination.

    Args:
        library_id: Library ID
        page: Page number (1-indexed)
        page_size: Items per page
        order_by: Field to order by
        order_desc: Descending order if True

    Returns:
        Tuple of (source codes list, total count)
    """
    with session_generator() as session:
        query = session.query(SourceCode).filter(SourceCode.library_id == library_id)

        # Get total count
        total = query.count()

        # Apply ordering
        order_column = getattr(SourceCode, order_by, SourceCode.commit_datetime)
        if order_desc:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        # Apply pagination
        offset = (page - 1) * page_size
        source_codes = query.offset(offset).limit(page_size).all()

        # Load project_features relationship before detaching (for has_features check)
        for sc in source_codes:
            _ = sc.project_features

        # Detach from session
        for sc in source_codes:
            session.expunge(sc)

        logger.debug(f"Listed {len(source_codes)} source codes for library {library_id} (page {page}, total {total})")
        return source_codes, total


def list_all_source_codes(
    page: int = 1,
    page_size: int = 20,
    library_id: Optional[int] = None,
    version_source: Optional[str] = None,
    order_by: str = "commit_datetime",
    order_desc: bool = True
) -> Tuple[List[SourceCode], int]:
    """
    List all source codes with pagination and filters.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        library_id: Optional filter by library_id
        version_source: Optional filter by version_source (tag/branch/commit)
        order_by: Field to order by
        order_desc: Descending order if True

    Returns:
        Tuple of (source codes list, total count)
    """
    with session_generator() as session:
        query = session.query(SourceCode)

        # Apply filters
        if library_id:
            query = query.filter(SourceCode.library_id == library_id)

        if version_source:
            query = query.filter(SourceCode.version_source == version_source)

        # Get total count
        total = query.count()

        # Apply ordering
        order_column = getattr(SourceCode, order_by, SourceCode.commit_datetime)
        if order_desc:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        # Apply pagination
        offset = (page - 1) * page_size
        source_codes = query.offset(offset).limit(page_size).all()

        # Load project_features relationship before detaching (for has_features check)
        for sc in source_codes:
            _ = sc.project_features

        # Detach from session
        for sc in source_codes:
            session.expunge(sc)

        logger.debug(f"Listed {len(source_codes)} source codes (page {page}, total {total})")
        return source_codes, total


def update_source_code(source_code_id: int, update_data: Dict[str, Any]) -> Optional[SourceCode]:
    """
    Update source code fields.

    Args:
        source_code_id: SourceCode ID
        update_data: Dictionary of fields to update

    Returns:
        Updated SourceCode object or None if not found

    Raises:
        IntegrityError: If unique constraint violated
    """
    with session_generator() as session:
        source_code = session.query(SourceCode).filter(SourceCode.id == source_code_id).first()
        if not source_code:
            logger.warning(f"SourceCode not found for update: ID {source_code_id}")
            return None

        # Update fields
        for key, value in update_data.items():
            if hasattr(source_code, key):
                setattr(source_code, key, value)

        session.flush()
        session.refresh(source_code)
        session.expunge(source_code)

        logger.info(f"Updated source code ID {source_code_id}")
        return source_code


def delete_source_code(source_code_id: int) -> bool:
    """
    Delete source code.

    Args:
        source_code_id: SourceCode ID

    Returns:
        True if deleted, False if not found
    """
    with session_generator() as session:
        source_code = session.query(SourceCode).filter(SourceCode.id == source_code_id).first()
        if not source_code:
            logger.warning(f"SourceCode not found for deletion: ID {source_code_id}")
            return False

        session.delete(source_code)
        logger.info(f"Deleted source code ID {source_code_id}")
        return True


def get_source_code_with_library(source_code_id: int) -> Optional[SourceCode]:
    """
    Get source code with library information eagerly loaded.

    Args:
        source_code_id: SourceCode ID

    Returns:
        SourceCode object with library loaded, or None if not found
    """
    with session_generator() as session:
        source_code = session.query(SourceCode)\
            .filter(SourceCode.id == source_code_id)\
            .first()

        if source_code:
            # Access library to trigger lazy loading
            _ = source_code.library
            session.expunge_all()

        return source_code
