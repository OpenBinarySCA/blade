from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import func, or_, case
from sqlalchemy.exc import IntegrityError
from loguru import logger

from ..entities import (
    StringFeature, StringToLibrary, Library, SourceCode, LibraryStatus,
    BinaryToLibrary, VulnerabilityToLibrary, FunctionNameToLibrary, FunctionNameFeature,
    ProjectFeature, FileMeta, FunctionNameToProject, StringToProject,
    BinaryToSourceCode, VulnerabilityToSourceCode, Binary, Vulnerability,
    LicenseToSourceCode
)
from ..postgres import session_generator


def list_libraries_by_strings(strings: List[str], min_match_num: int = 5, top_n: int = 5,
                              library_name_filter: str = None):
    """
    查询与给定字符串列表至少有指定数量交集的库

    策略：返回按匹配数量排序的 top_n 和按覆盖率排序的 top_n 的并集，最大化召回率

    Args:
        strings: 要查询的字符串列表
        min_match_num: 最小匹配字符串数量，默认5
        top_n: 每种排序策略取前N个，默认5
        library_name_filter: 可选，只查询指定名称的库

    Returns:
        匹配的库列表，每个库对象包含匹配的字符串列表
    """
    with session_generator() as session:
        # 1. 首先查询匹配的字符串ID和内容
        string_features = (
            session.query(StringFeature.id, StringFeature.string_value)
            .filter(StringFeature.string_value.in_(strings))
            .all()
        )

        if not string_features:
            return []

        # 2. 查询字符串-库关联关系，并找到满足条件的库ID
        query = (
            session.query(
                StringToLibrary.library_id,
                func.array_agg(StringFeature.string_value).label('matched_strings')
            )
            .join(
                StringFeature,
                StringFeature.id == StringToLibrary.string_id
            )
            .filter(StringToLibrary.string_id.in_([sf_id for sf_id, _ in string_features]))
        )

        # 如果指定了库名过滤，先获取库ID
        if library_name_filter:
            target_library = session.query(Library.id).filter(Library.name == library_name_filter).first()
            if not target_library:
                return []
            query = query.filter(StringToLibrary.library_id == target_library.id)

        library_matches = (
            query
            .group_by(StringToLibrary.library_id)
            .having(func.count(StringToLibrary.string_id) >= min_match_num)
            .all()
        )

        if not library_matches:
            return []

        # 3. 查询匹配的库信息，同时获取库的总字符串数用于计算覆盖率
        matched_library_ids = [lib_id for lib_id, _ in library_matches]
        library_with_status = (
            session.query(Library, LibraryStatus.string_feature_count)
            .outerjoin(LibraryStatus, Library.id == LibraryStatus.library_id)
            .filter(Library.id.in_(matched_library_ids))
            .all()
        )

        # 4. 构建结果
        library_strings_map = {
            lib_id: sorted(set(matched_strings), key=lambda x: len(x), reverse=True)
            for lib_id, matched_strings in library_matches
        }

        # 为每个库计算匹配数和覆盖率
        all_libraries = []
        for library, total_count in library_with_status:
            library.matched_strings = library_strings_map[library.id]
            match_count = len(library.matched_strings)
            total = total_count if total_count and total_count > 0 else 1
            library.match_coverage = match_count / total
            library.match_count = match_count
            all_libraries.append(library)

        # 策略：取匹配数量 top_n 和覆盖率 top_n 的并集
        # 按匹配数量排序取 top_n
        by_count = sorted(all_libraries, key=lambda x: x.match_count, reverse=True)[:top_n]
        # 按覆盖率排序取 top_n
        by_coverage = sorted(all_libraries, key=lambda x: x.match_coverage, reverse=True)[:top_n]

        # 合并去重
        seen_ids = set()
        result = []
        for lib in by_count:
            if lib.id not in seen_ids:
                seen_ids.add(lib.id)
                result.append(lib)
        for lib in by_coverage:
            if lib.id not in seen_ids:
                seen_ids.add(lib.id)
                result.append(lib)

        return result


def list_libraries_by_function_names(function_names: List[str], min_match_num: int = 5, top_n: int = 5,
                                     library_name_filter: str = None):
    """
    查询与给定函数名列表至少有指定数量交集的库

    策略：返回按匹配数量排序的 top_n 和按覆盖率排序的 top_n 的并集，最大化召回率

    Args:
        function_names: 要查询的函数名列表
        min_match_num: 最小匹配函数名数量，默认5
        top_n: 每种排序策略取前N个，默认5
        library_name_filter: 如果指定，只查询该库名对应的库

    Returns:
        匹配的库列表，每个库对象包含匹配的函数名列表
    """
    with session_generator() as session:
        # 如果指定了 library_name_filter，先获取该库的 ID
        target_library_id = None
        if library_name_filter:
            target_library = session.query(Library.id).filter(
                func.lower(Library.name) == library_name_filter.lower()
            ).first()
            if not target_library:
                return []
            target_library_id = target_library[0]

        # 1. 首先查询匹配的函数名ID和内容
        func_name_features = (
            session.query(FunctionNameFeature.id, FunctionNameFeature.function_name)
            .filter(FunctionNameFeature.function_name.in_(function_names))
            .all()
        )

        if not func_name_features:
            return []

        # 2. 查询函数名-库关联关系，并找到满足条件的库ID
        library_matches_query = (
            session.query(
                FunctionNameToLibrary.library_id,
                func.array_agg(FunctionNameFeature.function_name).label('matched_function_names')
            )
            .join(
                FunctionNameFeature,
                FunctionNameFeature.id == FunctionNameToLibrary.function_name_id
            )
            .filter(FunctionNameToLibrary.function_name_id.in_([fn_id for fn_id, _ in func_name_features]))
        )

        # 如果指定了库名过滤，添加过滤条件
        if target_library_id:
            library_matches_query = library_matches_query.filter(
                FunctionNameToLibrary.library_id == target_library_id
            )

        library_matches = (
            library_matches_query
            .group_by(FunctionNameToLibrary.library_id)
            .having(func.count(FunctionNameToLibrary.function_name_id) >= min_match_num)
            .all()
        )

        if not library_matches:
            return []

        # 3. 查询匹配的库信息，同时获取库的总函数数用于计算覆盖率
        matched_library_ids = [lib_id for lib_id, _ in library_matches]
        library_with_status = (
            session.query(Library, LibraryStatus.function_name_feature_count)
            .outerjoin(LibraryStatus, Library.id == LibraryStatus.library_id)
            .filter(Library.id.in_(matched_library_ids))
            .all()
        )

        # 4. 构建结果
        library_func_names_map = {
            lib_id: sorted(set(matched_func_names), key=lambda x: len(x), reverse=True)
            for lib_id, matched_func_names in library_matches
        }

        # 为每个库计算匹配数和覆盖率
        all_libraries = []
        for library, total_count in library_with_status:
            library.matched_function_names = library_func_names_map[library.id]
            match_count = len(library.matched_function_names)
            total = total_count if total_count and total_count > 0 else 1
            library.match_coverage = match_count / total
            library.match_count = match_count
            all_libraries.append(library)

        # 策略：取匹配数量 top_n 和覆盖率 top_n 的并集
        # 按匹配数量排序取 top_n
        by_count = sorted(all_libraries, key=lambda x: x.match_count, reverse=True)[:top_n]
        # 按覆盖率排序取 top_n
        by_coverage = sorted(all_libraries, key=lambda x: x.match_coverage, reverse=True)[:top_n]

        # 合并去重（保持按匹配数量的顺序，再补充覆盖率高的）
        seen_ids = set()
        result = []
        for lib in by_count:
            if lib.id not in seen_ids:
                seen_ids.add(lib.id)
                result.append(lib)
        for lib in by_coverage:
            if lib.id not in seen_ids:
                seen_ids.add(lib.id)
                result.append(lib)

        return result



def list_libraries_by_strings_batch(
    strings: List[str],
    library_names: List[str],
    min_match_num: int = 1
) -> Dict[str, Dict[str, Any]]:
    """
    批量查询多个库的字符串匹配情况（一次查询返回所有库的匹配结果）

    Args:
        strings: 要查询的字符串列表
        library_names: 要查询的库名列表
        min_match_num: 最小匹配字符串数量，默认1

    Returns:
        Dict[str, Dict]: {
            库名: {
                "library_id": int,
                "matched_strings": List[str],
                "match_count": int
            }
        }
    """
    if not strings or not library_names:
        return {}

    with session_generator() as session:
        # 1. 获取目标库的 ID 映射
        target_libraries = (
            session.query(Library.id, Library.name)
            .filter(Library.name.in_(library_names))
            .all()
        )
        if not target_libraries:
            return {}

        library_id_to_name = {lib_id: name for lib_id, name in target_libraries}
        target_library_ids = list(library_id_to_name.keys())

        # 2. 查询匹配的字符串 ID
        string_features = (
            session.query(StringFeature.id, StringFeature.string_value)
            .filter(StringFeature.string_value.in_(strings))
            .all()
        )
        if not string_features:
            return {}

        string_feature_ids = [sf_id for sf_id, _ in string_features]

        # 3. 一次查询所有目标库的字符串匹配
        library_matches = (
            session.query(
                StringToLibrary.library_id,
                func.array_agg(StringFeature.string_value).label('matched_strings')
            )
            .join(StringFeature, StringFeature.id == StringToLibrary.string_id)
            .filter(
                StringToLibrary.string_id.in_(string_feature_ids),
                StringToLibrary.library_id.in_(target_library_ids)
            )
            .group_by(StringToLibrary.library_id)
            .having(func.count(StringToLibrary.string_id) >= min_match_num)
            .all()
        )

        # 4. 构建结果
        result = {}
        for lib_id, matched_strings in library_matches:
            lib_name = library_id_to_name.get(lib_id)
            if lib_name:
                unique_strings = sorted(set(matched_strings), key=lambda x: len(x), reverse=True)
                result[lib_name] = {
                    "library_id": lib_id,
                    "matched_strings": unique_strings,
                    "match_count": len(unique_strings)
                }

        return result


def list_libraries_by_function_names_batch(
    function_names: List[str],
    library_names: List[str],
    min_match_num: int = 1
) -> Dict[str, Dict[str, Any]]:
    """
    批量查询多个库的函数名匹配情况（一次查询返回所有库的匹配结果）

    Args:
        function_names: 要查询的函数名列表
        library_names: 要查询的库名列表
        min_match_num: 最小匹配函数名数量，默认1

    Returns:
        Dict[str, Dict]: {
            库名: {
                "library_id": int,
                "matched_function_names": List[str],
                "match_count": int
            }
        }
    """
    if not function_names or not library_names:
        return {}

    with session_generator() as session:
        # 1. 获取目标库的 ID 映射
        target_libraries = (
            session.query(Library.id, Library.name)
            .filter(func.lower(Library.name).in_([n.lower() for n in library_names]))
            .all()
        )
        if not target_libraries:
            return {}

        library_id_to_name = {lib_id: name for lib_id, name in target_libraries}
        target_library_ids = list(library_id_to_name.keys())

        # 2. 查询匹配的函数名 ID
        func_name_features = (
            session.query(FunctionNameFeature.id, FunctionNameFeature.function_name)
            .filter(FunctionNameFeature.function_name.in_(function_names))
            .all()
        )
        if not func_name_features:
            return {}

        func_name_feature_ids = [fn_id for fn_id, _ in func_name_features]

        # 3. 一次查询所有目标库的函数名匹配
        library_matches = (
            session.query(
                FunctionNameToLibrary.library_id,
                func.array_agg(FunctionNameFeature.function_name).label('matched_function_names')
            )
            .join(FunctionNameFeature, FunctionNameFeature.id == FunctionNameToLibrary.function_name_id)
            .filter(
                FunctionNameToLibrary.function_name_id.in_(func_name_feature_ids),
                FunctionNameToLibrary.library_id.in_(target_library_ids)
            )
            .group_by(FunctionNameToLibrary.library_id)
            .having(func.count(FunctionNameToLibrary.function_name_id) >= min_match_num)
            .all()
        )

        # 4. 构建结果
        result = {}
        for lib_id, matched_func_names in library_matches:
            lib_name = library_id_to_name.get(lib_id)
            if lib_name:
                unique_func_names = sorted(set(matched_func_names), key=lambda x: len(x), reverse=True)
                result[lib_name] = {
                    "library_id": lib_id,
                    "matched_function_names": unique_func_names,
                    "match_count": len(unique_func_names)
                }

        return result


def get_library_string_count(library_name: str) -> Optional[int]:
    """
    查询指定库名相关的字符串数量

    Args:
        library_name: 库的名称

    Returns:
        该库相关的字符串数量，如果库不存在则返回 None
    """
    with session_generator() as session:
        # 查询指定库名的字符串数量
        result = session.query(func.count(StringToLibrary.string_id.distinct())) \
            .join(Library, StringToLibrary.library_id == Library.id) \
            .filter(Library.name == library_name) \
            .scalar()

        # 如果查询结果为 0，需要确认库是否存在
        if result == 0:
            library_exists = session.query(Library) \
                .filter(Library.name == library_name) \
                .first()
            if not library_exists:
                return None

        return result


# ============ CRUD Operations ============

def create_library(library_data: Dict[str, Any]) -> Library:
    """
    Create a new library and automatically create its initial LibraryStatus.

    Args:
        library_data: Dictionary containing library fields

    Returns:
        Created Library object

    Raises:
        IntegrityError: If unique constraint violated (name + giturl)
    """
    with session_generator() as session:
        library = Library(**library_data)
        session.add(library)
        session.flush()  # Get the ID before creating status

        # Auto-create initial LibraryStatus for the new library
        status = LibraryStatus(
            library_id=library.id,
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

        session.refresh(library)
        # logger.info(f"Created library: {library.name} (ID: {library.id}) with initial status")
        return library


def get_library_by_id(library_id: int) -> Optional[Library]:
    """
    Get library by ID.

    Args:
        library_id: Library ID

    Returns:
        Library object or None if not found
    """
    with session_generator() as session:
        library = session.query(Library).filter(Library.id == library_id).first()
        if library:
            # Detach from session to avoid lazy loading issues
            session.expunge(library)
        return library


def get_library_by_name(name: str, giturl: Optional[str] = None) -> Optional[Library]:
    """
    Get library by name and optional giturl.

    Args:
        name: Library name
        giturl: Optional Git repository URL

    Returns:
        Library object or None if not found
    """
    with session_generator() as session:
        query = session.query(Library).filter(Library.name == name)
        if giturl:
            query = query.filter(Library.giturl == giturl)
        library = query.first()
        if library:
            session.expunge(library)
        return library


def list_libraries(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    vendor: Optional[str] = None,
    order_by: str = "created_at",
    order_desc: bool = True
) -> Tuple[List[Library], int]:
    """
    List libraries with pagination and filters.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        search: Search term for name/vendor/alias
        vendor: Filter by vendor
        order_by: Field to order by
        order_desc: Descending order if True

    Returns:
        Tuple of (libraries list, total count)
    """
    with session_generator() as session:
        query = session.query(Library)

        # Apply filters
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Library.name.ilike(search_term),
                    Library.vendor.ilike(search_term),
                    Library.alias.ilike(search_term)
                )
            )

        if vendor:
            query = query.filter(Library.vendor == vendor)

        # Get total count before pagination
        total = query.count()

        # Apply ordering
        order_column = getattr(Library, order_by, Library.created_at)
        if order_desc:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        # Apply pagination
        offset = (page - 1) * page_size
        libraries = query.offset(offset).limit(page_size).all()

        # Detach from session
        for lib in libraries:
            session.expunge(lib)

        logger.debug(f"Listed {len(libraries)} libraries (page {page}, total {total})")
        return libraries, total


def update_library(library_id: int, update_data: Dict[str, Any]) -> Optional[Library]:
    """
    Update library fields.

    Args:
        library_id: Library ID
        update_data: Dictionary of fields to update

    Returns:
        Updated Library object or None if not found

    Raises:
        IntegrityError: If unique constraint violated
    """
    with session_generator() as session:
        library = session.query(Library).filter(Library.id == library_id).first()
        if not library:
            logger.warning(f"Library not found for update: ID {library_id}")
            return None

        # Update fields
        for key, value in update_data.items():
            if hasattr(library, key):
                setattr(library, key, value)

        session.flush()
        session.refresh(library)
        session.expunge(library)

        logger.info(f"Updated library: {library.name} (ID: {library_id})")
        return library


def delete_library(library_id: int, cascade: bool = False) -> bool:
    """
    Delete library and its related data according to relationship types:
    - One-to-One / One-to-Many: Delete entities (LibraryStatus, SourceCode)
    - Many-to-Many: Delete only relationship records (Binary, Vulnerability, String, FunctionName associations)

    Args:
        library_id: Library ID
        cascade: If True, delete related SourceCodes; if False, check if has related data

    Returns:
        True if deleted, False if not found

    Raises:
        ValueError: If library has related data and cascade=False
    """
    with session_generator() as session:
        library = session.query(Library).filter(Library.id == library_id).first()
        if not library:
            logger.warning(f"Library not found for deletion: ID {library_id}")
            return False

        # Check for related SourceCodes
        source_code_count = session.query(func.count(SourceCode.id))\
            .filter(SourceCode.library_id == library_id)\
            .scalar()

        if source_code_count > 0 and not cascade:
            raise ValueError(
                f"Cannot delete library: has {source_code_count} related SourceCode records. "
                f"Use cascade=True to delete them."
            )

        # 1. Delete SourceCodes and their dependencies if cascade (One-to-Many)
        if cascade and source_code_count > 0:
            # Get all source_code_ids for this library
            source_code_ids = [sc.id for sc in session.query(SourceCode.id).filter(
                SourceCode.library_id == library_id
            ).all()]

            if source_code_ids:
                # Delete SourceCode's M:N associations
                session.query(BinaryToSourceCode).filter(
                    BinaryToSourceCode.source_code_id.in_(source_code_ids)
                ).delete(synchronize_session=False)

                session.query(VulnerabilityToSourceCode).filter(
                    VulnerabilityToSourceCode.source_code_id.in_(source_code_ids)
                ).delete(synchronize_session=False)

                # Delete LicenseToSourceCode associations
                session.query(LicenseToSourceCode).filter(
                    LicenseToSourceCode.source_code_id.in_(source_code_ids)
                ).delete(synchronize_session=False)

                # Delete ProjectFeature's dependencies (ProjectFeature.id = source_code_id)
                # First delete FileMeta
                session.query(FileMeta).filter(
                    FileMeta.project_feature_id.in_(source_code_ids)
                ).delete(synchronize_session=False)

                # Delete FunctionNameToProject
                session.query(FunctionNameToProject).filter(
                    FunctionNameToProject.project_id.in_(source_code_ids)
                ).delete(synchronize_session=False)

                # Delete StringToProject
                session.query(StringToProject).filter(
                    StringToProject.project_id.in_(source_code_ids)
                ).delete(synchronize_session=False)

                # Delete ProjectFeature
                session.query(ProjectFeature).filter(
                    ProjectFeature.id.in_(source_code_ids)
                ).delete(synchronize_session=False)

                # Finally delete SourceCodes
                session.query(SourceCode).filter(SourceCode.library_id == library_id).delete()
                logger.info(f"Deleted {source_code_count} SourceCodes and their dependencies for library ID {library_id}")

        # 2. Delete LibraryStatus (One-to-One)
        status_deleted = session.query(LibraryStatus).filter(LibraryStatus.library_id == library_id).delete()
        if status_deleted:
            logger.info(f"Deleted LibraryStatus for library ID {library_id}")

        # 3. Delete Many-to-Many relationship records (keep the entities)

        # Delete BinaryToLibrary associations
        binary_assoc_deleted = session.query(BinaryToLibrary)\
            .filter(BinaryToLibrary.library_id == library_id)\
            .delete()
        if binary_assoc_deleted:
            logger.info(f"Deleted {binary_assoc_deleted} BinaryToLibrary associations for library ID {library_id}")

        # Delete VulnerabilityToLibrary associations
        vuln_assoc_deleted = session.query(VulnerabilityToLibrary)\
            .filter(VulnerabilityToLibrary.library_id == library_id)\
            .delete()
        if vuln_assoc_deleted:
            logger.info(f"Deleted {vuln_assoc_deleted} VulnerabilityToLibrary associations for library ID {library_id}")

        # Delete StringToLibrary associations
        string_assoc_deleted = session.query(StringToLibrary)\
            .filter(StringToLibrary.library_id == library_id)\
            .delete()
        if string_assoc_deleted:
            logger.info(f"Deleted {string_assoc_deleted} StringToLibrary associations for library ID {library_id}")

        # Delete FunctionNameToLibrary associations
        func_assoc_deleted = session.query(FunctionNameToLibrary)\
            .filter(FunctionNameToLibrary.library_id == library_id)\
            .delete()
        if func_assoc_deleted:
            logger.info(f"Deleted {func_assoc_deleted} FunctionNameToLibrary associations for library ID {library_id}")

        # 4. Finally delete the library itself
        session.delete(library)
        logger.info(f"Deleted library: {library.name} (ID: {library_id})")
        return True


def get_library_with_source_codes(library_id: int) -> Optional[Library]:
    """
    Get library with all its source codes eagerly loaded.

    Args:
        library_id: Library ID

    Returns:
        Library object with source_codes loaded, or None if not found
    """
    with session_generator() as session:
        library = session.query(Library)\
            .filter(Library.id == library_id)\
            .first()

        if library:
            # Access source_codes to trigger lazy loading
            _ = library.source_codes
            # Also load project_features for each source_code to check has_features
            for sc in library.source_codes:
                _ = sc.project_features
            session.expunge_all()

        return library


def get_library_statistics() -> Dict[str, Any]:
    """
    Get comprehensive library statistics including source codes, binaries, and vulnerabilities.

    Returns:
        Dict with nested structure:
        - library: Library-level statistics (total, completeness counts)
        - source_code: Source code statistics (total, averages, distribution)
        - binary: Binary statistics (total, averages, distribution)
        - vulnerability: Vulnerability statistics (total, risk levels)
    """
    with session_generator() as session:
        # 1. Library counts
        total_libraries = session.query(func.count(Library.id)).scalar() or 0

        # 2. Source code statistics
        total_source_codes = session.query(func.count(SourceCode.id)).scalar() or 0
        libraries_with_source = session.query(func.count(func.distinct(SourceCode.library_id))).scalar() or 0
        libraries_without_source = total_libraries - libraries_with_source
        avg_source_per_library = round(total_source_codes / total_libraries, 2) if total_libraries > 0 else 0

        # 3. Library status statistics (completeness)
        complete_metadata = session.query(func.count(LibraryStatus.library_id))\
            .filter(LibraryStatus.has_basic_info == True).scalar() or 0
        has_features = session.query(func.count(LibraryStatus.library_id))\
            .filter(LibraryStatus.has_features == True).scalar() or 0
        has_binaries = session.query(func.count(LibraryStatus.library_id))\
            .filter(LibraryStatus.has_binaries == True).scalar() or 0
        has_vulnerabilities = session.query(func.count(LibraryStatus.library_id))\
            .filter(LibraryStatus.has_vulnerabilities == True).scalar() or 0

        # 3.1 Detailed metadata field completeness
        has_vendor = session.query(func.count(Library.id))\
            .filter(Library.vendor.isnot(None), Library.vendor != '').scalar() or 0
        has_giturl = session.query(func.count(Library.id))\
            .filter(Library.giturl.isnot(None), Library.giturl != '').scalar() or 0
        has_homepage = session.query(func.count(Library.id))\
            .filter(Library.homepage.isnot(None), Library.homepage != '').scalar() or 0
        has_description = session.query(func.count(Library.id))\
            .filter(Library.description.isnot(None), Library.description != '').scalar() or 0
        has_purl = session.query(func.count(Library.id))\
            .filter(Library.purl.isnot(None), Library.purl != '').scalar() or 0
        has_language = session.query(func.count(Library.id))\
            .filter(Library.language.isnot(None), func.array_length(Library.language, 1) > 0).scalar() or 0

        # 4. Binary statistics
        total_binaries = session.query(func.count(BinaryToLibrary.id)).scalar() or 0
        libraries_with_binary = session.query(func.count(func.distinct(BinaryToLibrary.library_id))).scalar() or 0
        libraries_without_binary = total_libraries - libraries_with_binary
        avg_binary_per_library = round(total_binaries / total_libraries, 2) if total_libraries > 0 else 0

        # 5. Vulnerability statistics
        total_vulnerabilities = session.query(func.count(VulnerabilityToLibrary.id)).scalar() or 0
        affected_libraries = has_vulnerabilities  # Same as has_vulnerabilities from LibraryStatus
        safe_libraries = total_libraries - affected_libraries

        # High risk libraries (vulnerability_count > 5)
        high_risk_libraries = session.query(func.count(LibraryStatus.library_id))\
            .filter(LibraryStatus.vulnerability_count > 5).scalar() or 0

        statistics = {
            'library': {
                'total': total_libraries,
                'complete_metadata': complete_metadata,
                'has_features': has_features,
                'has_binaries': has_binaries,
                'has_vulnerabilities': has_vulnerabilities
            },
            'metadata_fields': {
                'has_vendor': has_vendor,
                'has_giturl': has_giturl,
                'has_homepage': has_homepage,
                'has_description': has_description,
                'has_purl': has_purl,
                'has_language': has_language,
                'has_source_code': libraries_with_source,
            },
            'source_code': {
                'total': total_source_codes,
                'avg_per_library': avg_source_per_library,
                'libraries_with_source': libraries_with_source,
                'libraries_without_source': libraries_without_source
            },
            'binary': {
                'total': total_binaries,
                'avg_per_library': avg_binary_per_library,
                'libraries_with_binary': libraries_with_binary,
                'libraries_without_binary': libraries_without_binary
            },
            'vulnerability': {
                'total': total_vulnerabilities,
                'affected_libraries': affected_libraries,
                'high_risk_libraries': high_risk_libraries,
                'safe_libraries': safe_libraries
            }
        }

        logger.debug(f"Library statistics: {statistics}")
        return statistics


def list_all_library_ids() -> List[int]:
    """
    Get all library IDs (for batch operations).

    Returns:
        List of all library IDs
    """
    with session_generator() as session:
        ids = session.query(Library.id).all()
        return [id[0] for id in ids]


# ============ Library Related Data Query ============

def get_vulnerabilities_by_library(
    library_id: int,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Get vulnerabilities associated with a library.

    Args:
        library_id: Library ID
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (vulnerabilities list, total count)
    """
    with session_generator() as session:
        # Query vulnerabilities with relationship info
        query = session.query(
            Vulnerability,
            VulnerabilityToLibrary.confirmed,
            VulnerabilityToLibrary.notes
        ).join(
            VulnerabilityToLibrary,
            VulnerabilityToLibrary.vulnerability_id == Vulnerability.id
        ).filter(
            VulnerabilityToLibrary.library_id == library_id
        )

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        results = query.order_by(Vulnerability.published_date.desc())\
            .offset(offset).limit(page_size).all()

        # Serialize results
        vulnerabilities = []
        for vuln, confirmed, notes in results:
            vulnerabilities.append({
                'id': vuln.id,
                'cve_id': vuln.cve_id,
                'source': vuln.source,
                'severity': vuln.severity,
                'description': vuln.description,
                'published_date': vuln.published_date.isoformat() if vuln.published_date else None,
                'affected_versions': vuln.affected_versions,
                'fixed_versions': vuln.fixed_versions,
                'references': vuln.references,
                'confirmed': confirmed,
                'notes': notes,
                'created_at': vuln.created_at.isoformat() if vuln.created_at else None
            })

        logger.debug(f"Found {total} vulnerabilities for library ID {library_id}")
        return vulnerabilities, total


def get_binaries_by_library(
    library_id: int,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Get binaries associated with a library.

    Args:
        library_id: Library ID
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (binaries list, total count)
    """
    with session_generator() as session:
        # Query binaries with relationship info
        query = session.query(
            Binary,
            BinaryToLibrary.confidence,
            BinaryToLibrary.detection_method
        ).join(
            BinaryToLibrary,
            BinaryToLibrary.binary_id == Binary.id
        ).filter(
            BinaryToLibrary.library_id == library_id
        )

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        results = query.order_by(Binary.created_at.desc())\
            .offset(offset).limit(page_size).all()

        # Serialize results
        binaries = []
        for binary, confidence, detection_method in results:
            binaries.append({
                'id': binary.id,
                'binary_name': binary.binary_name,
                'binary_hash': binary.binary_hash,
                'architecture': binary.architecture,
                'file_size': binary.file_size,
                'compiler_info': binary.compiler_info,
                'linked_libraries': binary.linked_libraries,
                'confidence': confidence,
                'detection_method': detection_method,
                'created_at': binary.created_at.isoformat() if binary.created_at else None
            })

        logger.debug(f"Found {total} binaries for library ID {library_id}")
        return binaries, total


def get_string_features_by_library(
    library_id: int,
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Get string features associated with a library.

    Args:
        library_id: Library ID
        page: Page number (1-indexed)
        page_size: Items per page
        search: Optional search term for string value

    Returns:
        Tuple of (string features list, total count)
    """
    with session_generator() as session:
        # Query string features with relationship info
        query = session.query(
            StringFeature,
            StringToLibrary.context
        ).join(
            StringToLibrary,
            StringToLibrary.string_id == StringFeature.id
        ).filter(
            StringToLibrary.library_id == library_id
        )

        # Apply search filter
        if search:
            query = query.filter(StringFeature.string_value.ilike(f"%{search}%"))

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        results = query.order_by(StringFeature.id.asc())\
            .offset(offset).limit(page_size).all()

        # Serialize results
        strings = []
        for string_feature, context in results:
            strings.append({
                'id': string_feature.id,
                'string_value': string_feature.string_value,
                'string_hash': string_feature.string_hash,
                'context': context
            })

        logger.debug(f"Found {total} string features for library ID {library_id}")
        return strings, total


def get_function_names_by_library(
    library_id: int,
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Get function name features associated with a library.

    Args:
        library_id: Library ID
        page: Page number (1-indexed)
        page_size: Items per page
        search: Optional search term for function name

    Returns:
        Tuple of (function name features list, total count)
    """
    with session_generator() as session:
        # Query function name features with relationship info
        query = session.query(
            FunctionNameFeature,
            FunctionNameToLibrary.context
        ).join(
            FunctionNameToLibrary,
            FunctionNameToLibrary.function_name_id == FunctionNameFeature.id
        ).filter(
            FunctionNameToLibrary.library_id == library_id
        )

        # Apply search filter
        if search:
            query = query.filter(FunctionNameFeature.function_name.ilike(f"%{search}%"))

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        results = query.order_by(FunctionNameFeature.id.asc())\
            .offset(offset).limit(page_size).all()

        # Serialize results
        function_names = []
        for fn_feature, context in results:
            function_names.append({
                'id': fn_feature.id,
                'function_name': fn_feature.function_name,
                'function_hash': fn_feature.function_hash,
                'context': context
            })

        logger.debug(f"Found {total} function names for library ID {library_id}")
        return function_names, total


def get_feature_file_paths_for_library(
    library_id: int,
    feature_names: List[str],
    feature_type: str = "function_name"
) -> Dict[str, List[str]]:
    """
    获取指定库中，给定特征名对应的文件路径列表

    Args:
        library_id: 库ID
        feature_names: 特征名列表（函数名或字符串）
        feature_type: 特征类型，"function_name" 或 "string"

    Returns:
        Dict[str, List[str]]: {特征名: [文件路径列表]}
    """
    if not feature_names:
        return {}

    with session_generator() as session:
        if feature_type == "function_name":
            # 查询函数名 → 文件路径
            # FunctionNameFeature → FunctionNameToFile → FileFeature → FileMeta → SourceCode
            from ..entities import FunctionNameToFile, FileFeature

            results = (
                session.query(
                    FunctionNameFeature.function_name,
                    FileMeta.path
                )
                .join(FunctionNameToFile, FunctionNameFeature.id == FunctionNameToFile.function_name_id)
                .join(FileFeature, FunctionNameToFile.file_id == FileFeature.id)
                .join(FileMeta, FileMeta.file_feature_id == FileFeature.id)
                .join(SourceCode, FileMeta.project_feature_id == SourceCode.id)
                .filter(
                    FunctionNameFeature.function_name.in_(feature_names),
                    SourceCode.library_id == library_id
                )
                .all()
            )
        else:  # string
            # 查询字符串 → 文件路径
            from ..entities import StringToFile, FileFeature

            results = (
                session.query(
                    StringFeature.string_value,
                    FileMeta.path
                )
                .join(StringToFile, StringFeature.id == StringToFile.string_id)
                .join(FileFeature, StringToFile.file_id == FileFeature.id)
                .join(FileMeta, FileMeta.file_feature_id == FileFeature.id)
                .join(SourceCode, FileMeta.project_feature_id == SourceCode.id)
                .filter(
                    StringFeature.string_value.in_(feature_names),
                    SourceCode.library_id == library_id
                )
                .all()
            )

        # 构建结果字典
        feature_to_paths: Dict[str, List[str]] = {}
        for feature_name, path in results:
            if feature_name not in feature_to_paths:
                feature_to_paths[feature_name] = []
            if path and path not in feature_to_paths[feature_name]:
                feature_to_paths[feature_name].append(path)

        logger.debug(f"Found file paths for {len(feature_to_paths)} features in library {library_id}")
        return feature_to_paths
