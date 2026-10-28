"""
Data Management API - CRUD operations for Library and SourceCode
"""
import uuid
import json
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from .....services.data_management import LibraryService, SourceCodeService, StatisticsService
from .....services.data_management.library_status_service import LibraryStatusService
from .....celery_tasks.batch_refresh_task import batch_refresh_library_status_task
from .....databases.redis.redis_clients import batch_refresh_task_redis_client
from .....databases.postgres.repository import license_repository
from .....interface import BatchRefreshTask
from ...schemas import (
    CreateLibraryRequest, UpdateLibraryRequest,
    LibraryResponse, LibraryDetailResponse, LibraryListResponse,
    CreateSourceCodeRequest, UpdateSourceCodeRequest,
    SourceCodeResponse, SourceCodeWithLibraryResponse, SourceCodeListResponse,
    LibraryStatisticsResponse,
    LibraryStatusResponse,
    BatchRefreshTaskResponse,
    CreateLicenseRequest, LicenseResponse, LicenseListResponse,
    AddLicenseToSourceCodeRequest
)

router = APIRouter()


# ============ Statistics Endpoints ============

@router.get("/statistics", response_model=LibraryStatisticsResponse)
def get_statistics():
    """
    Get data management statistics.

    Returns:
        Statistics including:
        - Total libraries
        - Total source codes
        - Average source codes per library
        - Libraries with/without source codes

    Raises:
        HTTPException: 500 if statistics retrieval fails
    """
    try:
        statistics = StatisticsService.get_library_statistics()
        logger.info("Retrieved library statistics")
        return statistics
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


# ============ Library Endpoints ============

@router.post("/libraries", response_model=LibraryResponse, status_code=201)
def create_library(request: CreateLibraryRequest):
    """
    Create a new library.

    Args:
        request: Library creation data

    Returns:
        Created library

    Raises:
        HTTPException: 400 if validation fails or duplicate exists
    """
    try:
        library = LibraryService.create_library(request.model_dump())
        logger.info(f"Created library: {library['name']} (ID: {library['id']})")
        return library
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create library: {e}")
        raise HTTPException(status_code=500, detail="Failed to create library")


@router.get("/libraries", response_model=LibraryListResponse)
def list_libraries(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str = Query(None, description="Search term for name/vendor/alias"),
    vendor: str = Query(None, description="Filter by vendor"),
    order_by: str = Query("created_at", description="Order by field"),
    order_desc: bool = Query(True, description="Descending order")
):
    """
    List libraries with pagination and filters.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        search: Search term
        vendor: Vendor filter
        order_by: Order by field
        order_desc: Descending order

    Returns:
        Paginated library list
    """
    try:
        result = LibraryService.list_libraries(
            page=page,
            page_size=page_size,
            search=search,
            vendor=vendor,
            order_by=order_by,
            order_desc=order_desc
        )
        return result
    except Exception as e:
        logger.error(f"Failed to list libraries: {e}")
        raise HTTPException(status_code=500, detail="Failed to list libraries")


@router.get("/libraries/{library_id}", response_model=LibraryDetailResponse)
def get_library(library_id: int):
    """
    Get library detail with source codes.

    Args:
        library_id: Library ID

    Returns:
        Library detail

    Raises:
        HTTPException: 404 if not found
    """
    try:
        library = LibraryService.get_library_detail(library_id)
        if not library:
            raise HTTPException(status_code=404, detail=f"Library not found: ID {library_id}")
        return library
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get library {library_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get library")


@router.put("/libraries/{library_id}", response_model=LibraryResponse)
def update_library(library_id: int, request: UpdateLibraryRequest):
    """
    Update library.

    Args:
        library_id: Library ID
        request: Update data

    Returns:
        Updated library

    Raises:
        HTTPException: 404 if not found, 400 if validation fails
    """
    try:
        # Only include non-None fields
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        library = LibraryService.update_library(library_id, update_data)
        if not library:
            raise HTTPException(status_code=404, detail=f"Library not found: ID {library_id}")

        logger.info(f"Updated library ID {library_id}")
        return library
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update library {library_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update library")


@router.delete("/libraries/{library_id}", status_code=204)
def delete_library(
    library_id: int,
    cascade: bool = Query(False, description="Delete related source codes")
):
    """
    Delete library.

    Args:
        library_id: Library ID
        cascade: If True, delete related source codes

    Raises:
        HTTPException: 404 if not found, 400 if has related data and cascade=False
    """
    try:
        deleted = LibraryService.delete_library(library_id, cascade=cascade)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Library not found: ID {library_id}")

        logger.info(f"Deleted library ID {library_id} (cascade={cascade})")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete library {library_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete library")


# ============ SourceCode Endpoints ============

@router.post("/source_codes", response_model=SourceCodeResponse, status_code=201)
def create_source_code(request: CreateSourceCodeRequest):
    """
    Create a new source code record.

    Args:
        request: SourceCode creation data

    Returns:
        Created source code

    Raises:
        HTTPException: 400 if validation fails or duplicate exists
    """
    try:
        source_code = SourceCodeService.create_source_code(request.model_dump())
        logger.info(f"Created source code for library {source_code['library_id']} (ID: {source_code['id']})")
        return source_code
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create source code: {e}")
        raise HTTPException(status_code=500, detail="Failed to create source code")


@router.get("/source_codes", response_model=SourceCodeListResponse)
def list_source_codes(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    library_id: int = Query(None, description="Filter by library"),
    version_source: str = Query(None, description="Filter by version source"),
    order_by: str = Query("commit_datetime", description="Order by field"),
    order_desc: bool = Query(True, description="Descending order")
):
    """
    List source codes with pagination and filters.

    Args:
        page: Page number
        page_size: Items per page
        library_id: Optional library filter
        version_source: Optional version source filter
        order_by: Order by field
        order_desc: Descending order

    Returns:
        Paginated source code list
    """
    try:
        result = SourceCodeService.list_all_source_codes(
            page=page,
            page_size=page_size,
            library_id=library_id,
            version_source=version_source,
            order_by=order_by,
            order_desc=order_desc
        )
        return result
    except Exception as e:
        logger.error(f"Failed to list source codes: {e}")
        raise HTTPException(status_code=500, detail="Failed to list source codes")


@router.get("/libraries/{library_id}/source_codes", response_model=SourceCodeListResponse)
def list_library_source_codes(
    library_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    order_by: str = Query("commit_datetime", description="Order by field"),
    order_desc: bool = Query(True, description="Descending order")
):
    """
    List source codes for a specific library.

    Args:
        library_id: Library ID
        page: Page number
        page_size: Items per page
        order_by: Order by field
        order_desc: Descending order

    Returns:
        Paginated source code list
    """
    try:
        result = SourceCodeService.list_source_codes_by_library(
            library_id=library_id,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_desc=order_desc
        )
        return result
    except Exception as e:
        logger.error(f"Failed to list source codes for library {library_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list source codes")


@router.get("/source_codes/{source_code_id}", response_model=SourceCodeWithLibraryResponse)
def get_source_code(source_code_id: int):
    """
    Get source code detail with library info.

    Args:
        source_code_id: SourceCode ID

    Returns:
        SourceCode detail

    Raises:
        HTTPException: 404 if not found
    """
    try:
        source_code = SourceCodeService.get_source_code_with_library(source_code_id)
        if not source_code:
            raise HTTPException(status_code=404, detail=f"SourceCode not found: ID {source_code_id}")
        return source_code
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get source code {source_code_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get source code")


@router.put("/source_codes/{source_code_id}", response_model=SourceCodeResponse)
def update_source_code(source_code_id: int, request: UpdateSourceCodeRequest):
    """
    Update source code.

    Args:
        source_code_id: SourceCode ID
        request: Update data

    Returns:
        Updated source code

    Raises:
        HTTPException: 404 if not found, 400 if validation fails
    """
    try:
        # Only include non-None fields
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        source_code = SourceCodeService.update_source_code(source_code_id, update_data)
        if not source_code:
            raise HTTPException(status_code=404, detail=f"SourceCode not found: ID {source_code_id}")

        logger.info(f"Updated source code ID {source_code_id}")
        return source_code
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update source code {source_code_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update source code")


@router.delete("/source_codes/{source_code_id}", status_code=204)
def delete_source_code(source_code_id: int):
    """
    Delete source code.

    Args:
        source_code_id: SourceCode ID

    Raises:
        HTTPException: 404 if not found
    """
    try:
        deleted = SourceCodeService.delete_source_code(source_code_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"SourceCode not found: ID {source_code_id}")

        logger.info(f"Deleted source code ID {source_code_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete source code {source_code_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete source code")


# ============ Library Status Endpoints ============

@router.get("/libraries/{library_id}/status", response_model=LibraryStatusResponse)
def get_library_status(library_id: int):
    """
    Get library status.

    Args:
        library_id: Library ID

    Returns:
        Library status

    Raises:
        HTTPException: 404 if not found
    """
    try:
        status = LibraryStatusService.get_or_create_library_status(library_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Library not found: ID {library_id}")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get library status for library {library_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get library status")


@router.post("/libraries/{library_id}/status/refresh", response_model=LibraryStatusResponse)
def refresh_library_status(library_id: int):
    """
    Refresh library status by recalculating based on current data.

    This will update:
    - Basic info completeness
    - Description presence
    - Feature counts (string and function name)
    - Source code count
    - Binary count
    - Vulnerability count

    Args:
        library_id: Library ID

    Returns:
        Refreshed library status

    Raises:
        HTTPException: 404 if library not found
    """
    try:
        status = LibraryStatusService.refresh_library_status(library_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Library not found: ID {library_id}")

        logger.info(f"Refreshed library status for library ID {library_id}")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh library status for library {library_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh library status")


# ============ Batch Refresh Endpoints ============

@router.post("/libraries/batch-refresh-status", response_model=BatchRefreshTaskResponse)
def start_batch_refresh_library_status():
    """
    Start batch refresh task for all library statuses.

    创建一个异步任务，批量刷新所有 library 的状态。

    Returns:
        Task information including task_id for progress tracking

    Raises:
        HTTPException: 500 if task creation fails
    """
    try:
        # 1. Create task
        task_id = str(uuid.uuid4())
        task = BatchRefreshTask(task_id=task_id)

        # 2. Store to Redis with 3 hours TTL
        redis_key = f"batch_refresh_task:{task_id}"
        task_json = task.customer_serialize()
        batch_refresh_task_redis_client.setex(
            redis_key,
            10800,  # 3 hours
            json.dumps(task_json, ensure_ascii=False)
        )

        # 3. Start Celery task
        batch_refresh_library_status_task.delay(task_id)

        logger.info(f"Started batch refresh task: {task_id}")
        return task_json

    except Exception as e:
        logger.error(f"Failed to start batch refresh task: {e}")
        raise HTTPException(status_code=500, detail="Failed to start batch refresh task")


@router.get("/libraries/batch-refresh-status/{task_id}", response_model=BatchRefreshTaskResponse)
def get_batch_refresh_status(task_id: str):
    """
    Get batch refresh task status and progress.

    查询批量刷新任务的进度。

    Args:
        task_id: Task ID

    Returns:
        Task status and progress information

    Raises:
        HTTPException: 404 if task not found or expired
    """
    redis_key = f"batch_refresh_task:{task_id}"
    task_info = batch_refresh_task_redis_client.get(redis_key)

    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found or expired")

    try:
        task_data = json.loads(task_info.decode('utf-8'))

        # Calculate progress percentage
        if task_data.get('total_libraries', 0) > 0:
            task_data['progress_percent'] = round(
                (task_data['completed_libraries'] / task_data['total_libraries']) * 100,
                1
            )
        else:
            task_data['progress_percent'] = 0

        return task_data

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid task info format")


# ============ Library Related Data Endpoints ============

@router.get("/libraries/{library_id}/vulnerabilities")
def get_library_vulnerabilities(
    library_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Get vulnerabilities associated with a library.

    Args:
        library_id: Library ID
        page: Page number
        page_size: Items per page

    Returns:
        Paginated vulnerabilities list
    """
    try:
        result = LibraryService.get_library_vulnerabilities(
            library_id=library_id,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        logger.error(f"Failed to get vulnerabilities for library {library_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get library vulnerabilities")


@router.get("/libraries/{library_id}/binaries")
def get_library_binaries(
    library_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Get binaries associated with a library.

    Args:
        library_id: Library ID
        page: Page number
        page_size: Items per page

    Returns:
        Paginated binaries list
    """
    try:
        result = LibraryService.get_library_binaries(
            library_id=library_id,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        logger.error(f"Failed to get binaries for library {library_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get library binaries")


@router.get("/libraries/{library_id}/string-features")
def get_library_string_features(
    library_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    search: str = Query(None, description="Search term for string value")
):
    """
    Get string features associated with a library.

    Args:
        library_id: Library ID
        page: Page number
        page_size: Items per page
        search: Optional search term

    Returns:
        Paginated string features list
    """
    try:
        result = LibraryService.get_library_string_features(
            library_id=library_id,
            page=page,
            page_size=page_size,
            search=search
        )
        return result
    except Exception as e:
        logger.error(f"Failed to get string features for library {library_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get library string features")


@router.get("/libraries/{library_id}/function-names")
def get_library_function_names(
    library_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    search: str = Query(None, description="Search term for function name")
):
    """
    Get function name features associated with a library.

    Args:
        library_id: Library ID
        page: Page number
        page_size: Items per page
        search: Optional search term

    Returns:
        Paginated function names list
    """
    try:
        result = LibraryService.get_library_function_names(
            library_id=library_id,
            page=page,
            page_size=page_size,
            search=search
        )
        return result
    except Exception as e:
        logger.error(f"Failed to get function names for library {library_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get library function names")


# ============ License Endpoints ============

@router.get("/libraries/{library_id}/licenses", response_model=LicenseListResponse)
def get_library_licenses(
    library_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Get licenses for a library (from latest source code version).

    Args:
        library_id: Library ID
        page: Page number
        page_size: Items per page

    Returns:
        Paginated licenses list with file paths
    """
    try:
        licenses, total = license_repository.get_licenses_by_library(
            library_id=library_id,
            page=page,
            page_size=page_size
        )
        return {
            'items': licenses,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 0
        }
    except Exception as e:
        logger.error(f"Failed to get licenses for library {library_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get library licenses")


@router.get("/source_codes/{source_code_id}/licenses", response_model=LicenseListResponse)
def get_source_code_licenses(
    source_code_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Get licenses for a specific source code version.

    Args:
        source_code_id: SourceCode ID
        page: Page number
        page_size: Items per page

    Returns:
        Paginated licenses list with file paths
    """
    try:
        licenses, total = license_repository.get_licenses_by_source_code(
            source_code_id=source_code_id,
            page=page,
            page_size=page_size
        )
        return {
            'items': licenses,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 0
        }
    except Exception as e:
        logger.error(f"Failed to get licenses for source code {source_code_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get source code licenses")


@router.post("/licenses", response_model=LicenseResponse, status_code=201)
def create_license(request: CreateLicenseRequest):
    """
    Create a new license. If content matches an existing license (by hash),
    returns the existing license instead of creating a duplicate.

    Args:
        request: License creation data (name, content)

    Returns:
        Created or existing license
    """
    try:
        if request.content:
            # Use get_or_create to deduplicate by content
            license_obj, created = license_repository.get_or_create_license(
                name=request.name,
                content=request.content
            )
            if not created:
                logger.info(f"Returning existing license with same content: {license_obj.name} (ID: {license_obj.id})")
        else:
            # Create license without content
            license_obj = license_repository.create_license({
                'name': request.name,
                'content': None
            })

        return {
            'id': license_obj.id,
            'name': license_obj.name,
            'content': license_obj.content,
            'content_hash': license_obj.content_hash,
            'created_at': license_obj.created_at.isoformat() if license_obj.created_at else None,
            'updated_at': license_obj.updated_at.isoformat() if license_obj.updated_at else None,
        }
    except Exception as e:
        logger.error(f"Failed to create license: {e}")
        raise HTTPException(status_code=500, detail="Failed to create license")


@router.post("/source_codes/{source_code_id}/licenses", response_model=LicenseResponse, status_code=201)
def add_license_to_source_code(
    source_code_id: int,
    request: AddLicenseToSourceCodeRequest
):
    """
    Link a license to a source code with optional file path.

    Args:
        source_code_id: SourceCode ID
        request: License ID and optional file path

    Returns:
        The linked license
    """
    try:
        # Verify license exists
        license_obj = license_repository.get_license_by_id(request.license_id)
        if not license_obj:
            raise HTTPException(status_code=404, detail=f"License not found: ID {request.license_id}")

        # Add the relation
        license_repository.add_license_to_source_code(
            source_code_id=source_code_id,
            license_id=request.license_id,
            file_path=request.file_path
        )

        logger.info(f"Linked license {request.license_id} to source code {source_code_id}")
        return {
            'id': license_obj.id,
            'name': license_obj.name,
            'content': license_obj.content,
            'content_hash': license_obj.content_hash,
            'file_path': request.file_path,
            'created_at': license_obj.created_at.isoformat() if license_obj.created_at else None,
            'updated_at': license_obj.updated_at.isoformat() if license_obj.updated_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add license to source code {source_code_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to add license to source code")


