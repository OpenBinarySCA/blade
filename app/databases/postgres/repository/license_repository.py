"""
License Repository - Data access layer for License and LicenseToSourceCode entities
"""
import hashlib
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import func
from loguru import logger

from ..entities import License, LicenseToSourceCode, SourceCode
from ..postgres import session_generator


def compute_content_hash(content: str) -> str:
    """
    Compute SHA256 hash of license content for deduplication.

    Args:
        content: License content text

    Returns:
        SHA256 hash string
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def create_license(license_data: Dict[str, Any]) -> License:
    """
    Create a new license record. If content is provided, compute content_hash for deduplication.

    Args:
        license_data: Dictionary containing license fields (name, content, content_hash)

    Returns:
        Created License object

    Raises:
        IntegrityError: If unique constraint violated (duplicate content_hash)
    """
    with session_generator() as session:
        # If content provided but no hash, compute it
        if 'content' in license_data and license_data['content'] and 'content_hash' not in license_data:
            license_data['content_hash'] = compute_content_hash(license_data['content'])

        license_obj = License(**license_data)
        session.add(license_obj)
        session.flush()
        session.refresh(license_obj)
        # logger.info(f"Created license: {license_obj.name} (ID: {license_obj.id})")
        return license_obj


def get_license_by_id(license_id: int) -> Optional[License]:
    """
    Get license by ID.

    Args:
        license_id: License ID

    Returns:
        License object or None if not found
    """
    with session_generator() as session:
        license_obj = session.query(License).filter(License.id == license_id).first()
        if license_obj:
            session.expunge(license_obj)
        return license_obj


def get_license_by_content_hash(content_hash: str) -> Optional[License]:
    """
    Get license by content hash (for deduplication lookup).

    Args:
        content_hash: SHA256 hash of license content

    Returns:
        License object or None if not found
    """
    with session_generator() as session:
        license_obj = session.query(License).filter(License.content_hash == content_hash).first()
        if license_obj:
            session.expunge(license_obj)
        return license_obj


def get_or_create_license(name: str, content: str) -> Tuple[License, bool]:
    """
    Get existing license by content hash or create new one.

    Args:
        name: License name
        content: License content

    Returns:
        Tuple of (License object, created: bool)
    """
    content_hash = compute_content_hash(content)

    # Try to find existing license by hash
    existing = get_license_by_content_hash(content_hash)
    if existing:
        return existing, False

    # Create new license
    license_obj = create_license({
        'name': name,
        'content': content,
        'content_hash': content_hash
    })
    return license_obj, True


def list_licenses(
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None
) -> Tuple[List[License], int]:
    """
    List all licenses with pagination.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        search: Optional search term for name

    Returns:
        Tuple of (licenses list, total count)
    """
    with session_generator() as session:
        query = session.query(License)

        # Apply search filter
        if search:
            query = query.filter(License.name.ilike(f'%{search}%'))

        # Get total count
        total = query.count()

        # Apply ordering
        query = query.order_by(License.name.asc())

        # Apply pagination
        offset = (page - 1) * page_size
        licenses = query.offset(offset).limit(page_size).all()

        # Detach from session
        for lic in licenses:
            session.expunge(lic)

        logger.debug(f"Listed {len(licenses)} licenses (page {page}, total {total})")
        return licenses, total


def update_license(license_id: int, update_data: Dict[str, Any]) -> Optional[License]:
    """
    Update license fields.

    Args:
        license_id: License ID
        update_data: Dictionary of fields to update

    Returns:
        Updated License object or None if not found
    """
    with session_generator() as session:
        license_obj = session.query(License).filter(License.id == license_id).first()
        if not license_obj:
            logger.warning(f"License not found for update: ID {license_id}")
            return None

        # If content is updated, recompute hash
        if 'content' in update_data and update_data['content']:
            update_data['content_hash'] = compute_content_hash(update_data['content'])

        # Update fields
        for key, value in update_data.items():
            if hasattr(license_obj, key):
                setattr(license_obj, key, value)

        session.flush()
        session.refresh(license_obj)
        session.expunge(license_obj)

        logger.info(f"Updated license ID {license_id}")
        return license_obj


def delete_license(license_id: int) -> bool:
    """
    Delete license and all its source code relations.

    Args:
        license_id: License ID

    Returns:
        True if deleted, False if not found
    """
    with session_generator() as session:
        license_obj = session.query(License).filter(License.id == license_id).first()
        if not license_obj:
            logger.warning(f"License not found for deletion: ID {license_id}")
            return False

        # Delete relations first
        session.query(LicenseToSourceCode).filter(
            LicenseToSourceCode.license_id == license_id
        ).delete()

        session.delete(license_obj)
        logger.info(f"Deleted license ID {license_id}")
        return True


# ============ LicenseToSourceCode (Relation) functions ============

def add_license_to_source_code(
    source_code_id: int,
    license_id: int,
    file_path: Optional[str] = None
) -> LicenseToSourceCode:
    """
    Link a license to a source code with optional file path.

    Args:
        source_code_id: SourceCode ID
        license_id: License ID
        file_path: Relative file path in source code (e.g., "LICENSE")

    Returns:
        Created LicenseToSourceCode relation object

    Raises:
        IntegrityError: If relation already exists or foreign key invalid
    """
    with session_generator() as session:
        relation = LicenseToSourceCode(
            source_code_id=source_code_id,
            license_id=license_id,
            file_path=file_path
        )
        session.add(relation)
        session.flush()
        session.refresh(relation)
        # logger.info(f"Linked license {license_id} to source code {source_code_id} (path: {file_path})")
        return relation


def remove_license_from_source_code(
    source_code_id: int,
    license_id: int,
    file_path: Optional[str] = None
) -> bool:
    """
    Remove license-source code relation.

    Args:
        source_code_id: SourceCode ID
        license_id: License ID
        file_path: Optional file path to match

    Returns:
        True if deleted, False if not found
    """
    with session_generator() as session:
        query = session.query(LicenseToSourceCode).filter(
            LicenseToSourceCode.source_code_id == source_code_id,
            LicenseToSourceCode.license_id == license_id
        )

        if file_path is not None:
            query = query.filter(LicenseToSourceCode.file_path == file_path)

        relation = query.first()
        if not relation:
            return False

        session.delete(relation)
        logger.info(f"Removed license {license_id} from source code {source_code_id}")
        return True


def get_licenses_by_source_code(
    source_code_id: int,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Get all licenses for a specific source code version.

    Args:
        source_code_id: SourceCode ID
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (license dicts with file_path, total count)
    """
    with session_generator() as session:
        query = session.query(License, LicenseToSourceCode.file_path)\
            .join(LicenseToSourceCode, License.id == LicenseToSourceCode.license_id)\
            .filter(LicenseToSourceCode.source_code_id == source_code_id)

        # Get total count
        total = query.count()

        # Apply ordering
        query = query.order_by(License.name.asc())

        # Apply pagination
        offset = (page - 1) * page_size
        results = query.offset(offset).limit(page_size).all()

        # Build response with file_path
        licenses = []
        for license_obj, file_path in results:
            licenses.append({
                'id': license_obj.id,
                'name': license_obj.name,
                'content': license_obj.content,
                'content_hash': license_obj.content_hash,
                'file_path': file_path,
                'created_at': license_obj.created_at.isoformat() if license_obj.created_at else None,
                'updated_at': license_obj.updated_at.isoformat() if license_obj.updated_at else None,
            })

        logger.debug(f"Listed {len(licenses)} licenses for source code {source_code_id}")
        return licenses, total


def get_licenses_by_library(
    library_id: int,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Get licenses for a library (from latest source code version by commit_datetime).

    Args:
        library_id: Library ID
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (license dicts with file_path, total count)
    """
    with session_generator() as session:
        # Find latest source code for this library
        latest_source_code = session.query(SourceCode)\
            .filter(SourceCode.library_id == library_id)\
            .order_by(SourceCode.commit_datetime.desc().nullslast())\
            .first()

        if not latest_source_code:
            return [], 0

        # Get licenses for latest source code
        return get_licenses_by_source_code(latest_source_code.id, page, page_size)
