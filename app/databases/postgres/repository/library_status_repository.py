from typing import Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from loguru import logger

from ..entities import LibraryStatus, Library, SourceCode, StringToLibrary, FunctionNameToLibrary, BinaryToLibrary, VulnerabilityToLibrary
from ..postgres import session_generator


def get_library_status(library_id: int) -> Optional[LibraryStatus]:
    """
    Get library status by library ID.

    Args:
        library_id: Library ID

    Returns:
        LibraryStatus object or None if not found
    """
    with session_generator() as session:
        status = session.query(LibraryStatus).filter(LibraryStatus.library_id == library_id).first()
        if status:
            session.expunge(status)
        return status


def create_library_status(library_id: int) -> LibraryStatus:
    """
    Create a new library status entry.

    Args:
        library_id: Library ID

    Returns:
        Created LibraryStatus object

    Raises:
        IntegrityError: If status already exists for this library
    """
    with session_generator() as session:
        status = LibraryStatus(
            library_id=library_id,
            has_basic_info=False,
            has_description=False,
            has_features=False,
            has_binaries=False,
            has_vulnerabilities=False,
            source_code_count=0,
            string_feature_count=0,
            function_name_feature_count=0,
            binary_count=0,
            vulnerability_count=0,
            last_refreshed_at=func.now()
        )
        session.add(status)
        session.flush()
        session.refresh(status)
        session.expunge(status)
        logger.info(f"Created library status for library ID: {library_id}")
        return status


def update_library_status(library_id: int, update_data: Dict[str, Any]) -> Optional[LibraryStatus]:
    """
    Update library status fields.

    Args:
        library_id: Library ID
        update_data: Dictionary of fields to update

    Returns:
        Updated LibraryStatus object or None if not found
    """
    with session_generator() as session:
        status = session.query(LibraryStatus).filter(LibraryStatus.library_id == library_id).first()
        if not status:
            logger.warning(f"Library status not found for library ID: {library_id}")
            return None

        # Update fields
        for key, value in update_data.items():
            if hasattr(status, key):
                setattr(status, key, value)

        # Update timestamp
        status.last_refreshed_at = func.now()

        session.flush()
        session.refresh(status)
        session.expunge(status)

        logger.info(f"Updated library status for library ID: {library_id}")
        return status


def delete_library_status(library_id: int) -> bool:
    """
    Delete library status.

    Args:
        library_id: Library ID

    Returns:
        True if deleted, False if not found
    """
    with session_generator() as session:
        status = session.query(LibraryStatus).filter(LibraryStatus.library_id == library_id).first()
        if not status:
            logger.warning(f"Library status not found for deletion: library ID {library_id}")
            return False

        session.delete(status)
        logger.info(f"Deleted library status for library ID: {library_id}")
        return True


def refresh_library_status(library_id: int) -> Optional[LibraryStatus]:
    """
    Calculate and update library status based on current data.

    This checks:
    1. Metadata completeness (name, vendor, giturl, homepage, description, source_code_count > 0)
    2. Has features (string > 5 OR function_name > 5)
    3. Has binaries
    4. Has vulnerabilities

    Args:
        library_id: Library ID

    Returns:
        Updated LibraryStatus object or None if library not found
    """
    with session_generator() as session:
        # Get library
        library = session.query(Library).filter(Library.id == library_id).first()
        if not library:
            logger.warning(f"Library not found for status refresh: ID {library_id}")
            return None

        # Count source codes
        source_code_count = session.query(func.count(SourceCode.id))\
            .filter(SourceCode.library_id == library_id)\
            .scalar() or 0

        # Count string features
        string_feature_count = session.query(func.count(StringToLibrary.string_id.distinct()))\
            .filter(StringToLibrary.library_id == library_id)\
            .scalar() or 0

        # Count function name features
        function_name_feature_count = session.query(func.count(FunctionNameToLibrary.function_name_id.distinct()))\
            .filter(FunctionNameToLibrary.library_id == library_id)\
            .scalar() or 0

        # Count binaries
        binary_count = session.query(func.count(BinaryToLibrary.binary_id.distinct()))\
            .filter(BinaryToLibrary.library_id == library_id)\
            .scalar() or 0

        # Count vulnerabilities
        vulnerability_count = session.query(func.count(VulnerabilityToLibrary.vulnerability_id.distinct()))\
            .filter(VulnerabilityToLibrary.library_id == library_id)\
            .scalar() or 0

        # 1. Check metadata completeness
        required_fields = {
            'name': library.name,
            'vendor': library.vendor,
            'giturl': library.giturl,
            'homepage': library.homepage,
            'description': library.description and library.description.strip(),
            'source_code': source_code_count > 0
        }
        has_basic_info = all(required_fields.values())

        # Generate metadata note
        if not has_basic_info:
            missing = [k for k, v in required_fields.items() if not v]
            metadata_note = f"Missing: {', '.join(missing)}"
        else:
            metadata_note = None

        # 2. Check has features (at least one type > 5)
        has_features = (string_feature_count > 5) or (function_name_feature_count > 5)

        # Generate features note
        if not has_features:
            if string_feature_count == 0 and function_name_feature_count == 0:
                features_note = "No features extracted"
            else:
                features_note = f"Insufficient features (strings: {string_feature_count}, functions: {function_name_feature_count})"
        else:
            features_note = None

        # 3. Check has binaries
        has_binaries = binary_count > 0

        # Generate binaries note
        if not has_binaries:
            binaries_note = "No binaries added"
        else:
            binaries_note = None

        # 4. Check has vulnerabilities
        has_vulnerabilities = vulnerability_count > 0

        # Generate vulnerabilities note
        if not has_vulnerabilities:
            vulnerabilities_note = "No vulnerabilities found"
        else:
            vulnerabilities_note = f"{vulnerability_count} vulnerability/vulnerabilities found"

        # Get or create status
        status = session.query(LibraryStatus).filter(LibraryStatus.library_id == library_id).first()

        if not status:
            # Create new status
            status = LibraryStatus(library_id=library_id)
            session.add(status)

        # Update status fields
        status.has_basic_info = has_basic_info
        status.has_description = has_basic_info  # Keep for backward compatibility
        status.has_features = has_features
        status.has_binaries = has_binaries
        status.has_vulnerabilities = has_vulnerabilities

        # Update note fields
        status.metadata_note = metadata_note
        status.features_note = features_note
        status.binaries_note = binaries_note
        status.vulnerabilities_note = vulnerabilities_note

        # Update counts
        status.source_code_count = source_code_count
        status.string_feature_count = string_feature_count
        status.function_name_feature_count = function_name_feature_count
        status.binary_count = binary_count
        status.vulnerability_count = vulnerability_count
        status.last_refreshed_at = func.now()

        session.flush()
        session.refresh(status)
        session.expunge(status)

        # logger.info(f"Refreshed library status for library ID {library_id}: "
        #            f"metadata={has_basic_info}, features={has_features}, "
        #            f"sources={source_code_count}, binaries={binary_count}, vulns={vulnerability_count}")

        return status


def get_or_create_library_status(library_id: int) -> Optional[LibraryStatus]:
    """
    Get existing library status or create a new one if not exists.

    Args:
        library_id: Library ID

    Returns:
        LibraryStatus object or None if library not found
    """
    # Try to get existing status
    status = get_library_status(library_id)
    if status:
        return status

    # Check if library exists
    with session_generator() as session:
        library = session.query(Library).filter(Library.id == library_id).first()
        if not library:
            logger.warning(f"Library not found: ID {library_id}")
            return None

    # Create new status
    try:
        status = create_library_status(library_id)
        return status
    except IntegrityError:
        # Race condition: status was created between get and create
        logger.debug(f"Status already exists for library ID {library_id}, retrieving...")
        return get_library_status(library_id)
