"""
Ingestion Processor - 数据库入库处理

处理库、版本、特征、License 的入库操作
"""
from typing import List, Optional, Tuple, Dict, Any

from loguru import logger

from app.databases.postgres.repository.library_repository import (
    get_library_by_name, create_library, delete_library as repo_delete_library
)
from app.databases.postgres.repository.source_code_repository import (
    create_source_code, get_source_code_by_commit
)
from app.databases.postgres.repository.feature_repository import (
    bulk_get_or_create_strings, bulk_get_or_create_function_names,
    create_project_feature,
    add_strings_to_library, add_function_names_to_library,
    add_strings_to_project, add_function_names_to_project,
    add_strings_to_file, add_function_names_to_file,
    bulk_get_or_create_file_features, bulk_create_file_metas,
)
from app.databases.postgres.repository.library_status_repository import (
    refresh_library_status
)
from app.databases.postgres.repository.license_repository import (
    get_or_create_license, add_license_to_source_code
)

from .interface import LibraryInfo, VersionInfo, LicenseInfo, FeatureData


class IngestionProcessor:
    """入库处理器"""

    def __init__(
        self,
        min_str_length: int = 4,
        max_str_length: int = 500,
        min_function_name_length: int = 4,
        max_function_name_length: int = 100,
    ):
        """
        初始化入库处理器

        Args:
            min_str_length: 最小字符串长度
            max_str_length: 最大字符串长度
            min_function_name_length: 最小函数名长度
            max_function_name_length: 最大函数名长度
        """
        self.min_str_length = min_str_length
        self.max_str_length = max_str_length
        self.min_function_name_length = min_function_name_length
        self.max_function_name_length = max_function_name_length

    def create_or_get_library(self, library_info: LibraryInfo) -> Tuple[int, bool]:
        """
        创建或获取 Library

        Args:
            library_info: 库信息

        Returns:
            (library_id, is_new)
        """
        existing = get_library_by_name(library_info.name)
        if existing:
            return existing.id, False

        library_data = library_info.to_dict()
        library = create_library(library_data)
        return library.id, True

    def add_all_versions(
        self,
        library_id: int,
        versions: List[VersionInfo],
    ) -> Tuple[int, int, Dict[str, int]]:
        """
        添加所有版本到数据库（只创建 SourceCode 记录，不提取特征）

        相同 commit_id 的多个 tag 会合并到同一个 SourceCode 的 original_version_strs 中

        Args:
            library_id: Library ID
            versions: 版本列表

        Returns:
            (添加的版本数, 添加的tag数, {tag: source_code_id} 映射)
        """
        added_version_count = 0
        added_tag_count = 0
        version_id_map = {}

        for version in versions:
            try:
                # 检查是否已存在（按 commit_id）
                existing = get_source_code_by_commit(library_id, version.commit_id)
                if existing:
                    # 已存在，检查是否需要添加新 tag
                    existing_tags = existing.original_version_strs or []
                    if version.tag not in existing_tags:
                        # 追加新 tag 到 original_version_strs
                        new_tags = existing_tags + [version.tag]
                        self._update_source_code_tags(existing.id, new_tags)
                        added_tag_count += 1
                        logger.debug(f"追加 tag: {version.tag} -> 版本 {existing_tags[0]} (ID: {existing.id})")
                    version_id_map[version.tag] = existing.id
                    continue

                # 创建新 SourceCode
                source_code_data = version.to_source_code_dict(library_id)
                source_code = create_source_code(source_code_data)

                version_id_map[version.tag] = source_code.id
                added_version_count += 1
                added_tag_count += 1
                # logger.debug(f"添加版本: {version.tag} (ID: {source_code.id})")

            except Exception as e:
                logger.error(f"添加版本 {version.tag} 失败: {e}")
                continue

        return added_version_count, added_tag_count, version_id_map

    def _update_source_code_tags(self, source_code_id: int, tags: List[str]):
        """更新 SourceCode 的 original_version_strs"""
        from app.databases.postgres.repository.source_code_repository import update_source_code
        update_source_code(source_code_id, {'original_version_strs': tags})

    def add_features_for_version(
        self,
        library_id: int,
        source_code_id: int,
        feature_data: FeatureData
    ) -> bool:
        """
        为特定版本添加特征

        Args:
            library_id: Library ID
            source_code_id: SourceCode ID
            feature_data: 特征数据

        Returns:
            是否成功
        """
        try:
            # 创建 ProjectFeature
            project_data = {
                'name': feature_data.tag,
                'project_size_mb': feature_data.project_size_mb,
                'total_src_file': feature_data.total_src_file,
                'failed_src_file': feature_data.failed_src_file,
                'exception_src_file': 0,
                'function_count': feature_data.function_count,
                'distinct_string_count': feature_data.distinct_string_count,
                'extraction_succeed': feature_data.extraction_succeed,
                'extraction_log': feature_data.extraction_log,
            }
            create_project_feature(source_code_id, project_data)

            # 过滤特征
            strings = self._filter_strings(feature_data.strings)
            function_names = self._filter_function_names(feature_data.function_names)
            file_count = len(feature_data.file_features) if feature_data.file_features else 0

            # 批量入库 - Library 和 Project 级别
            string_id_map = {}
            function_name_id_map = {}

            # 字符串入库
            if strings:
                string_id_map = bulk_get_or_create_strings(strings)
                string_ids = list(string_id_map.values())
                add_strings_to_library(string_ids, library_id)
                add_strings_to_project(string_ids, source_code_id)

            # 函数名入库
            if function_names:
                function_name_id_map = bulk_get_or_create_function_names(function_names)
                function_name_ids = list(function_name_id_map.values())
                add_function_names_to_library(function_name_ids, library_id)
                add_function_names_to_project(function_name_ids, source_code_id)

            # 文件级别入库
            if feature_data.file_features:
                self._add_file_level_features(
                    source_code_id=source_code_id,
                    file_features=feature_data.file_features,
                    string_id_map=string_id_map,
                    function_name_id_map=function_name_id_map,
                )

            # 打印入库日志（一行）
            str_info = f"字符串 {len(strings)}" if strings else "字符串 0 ⚠️"
            func_info = f"函数名 {len(function_names)}" if function_names else "函数名 0 ⚠️"
            file_info = f"文件 {file_count}" if file_count > 0 else "文件 0 ⚠️"
            has_warning = not strings or not function_names or file_count == 0
            if has_warning:
                logger.warning(f"      📥 入库: {str_info} | {func_info} | {file_info}")
            else:
                logger.info(f"      📥 入库: {str_info} | {func_info} | {file_info}")
            return True

        except Exception as e:
            logger.error(f"添加特征 {feature_data.tag} 失败: {e}")
            return False

    def _add_file_level_features(
        self,
        source_code_id: int,
        file_features: list,
        string_id_map: dict,
        function_name_id_map: dict,
    ):
        """
        添加文件级别的特征关联

        Args:
            source_code_id: SourceCode ID (= project_id)
            file_features: FileFeatureData 列表
            string_id_map: {string_value: string_id} 映射
            function_name_id_map: {function_name: function_name_id} 映射
        """
        from .interface import FileFeatureData

        # 1. 准备文件特征数据
        file_data_list = []
        for ff in file_features:
            if isinstance(ff, FileFeatureData):
                file_data_list.append({
                    'sha256': ff.sha256,
                    'name': ff.name,
                    'extension': ff.extension,
                    'file_size_kb': ff.file_size_kb,
                    'function_num': ff.function_num,
                    'distinct_string_num': ff.distinct_string_num,
                    'global_strings': ff.global_strings,
                    'extraction_succeed': ff.extraction_succeed,
                    'extraction_log': ff.extraction_log,
                })
            elif isinstance(ff, dict):
                file_data_list.append(ff)

        # 2. 批量创建/获取 FileFeature
        sha256_to_file_id = bulk_get_or_create_file_features(file_data_list)

        # 3. 创建 FileMeta（关联 project → file）
        file_metas_data = []
        for ff in file_features:
            if isinstance(ff, FileFeatureData):
                sha256 = ff.sha256
                path = ff.path
            else:
                sha256 = ff.get('sha256')
                path = ff.get('path')

            if sha256 in sha256_to_file_id:
                file_metas_data.append({
                    'file_feature_id': sha256_to_file_id[sha256],
                    'path': path,
                    'file_sha256': sha256,
                })

        bulk_create_file_metas(source_code_id, file_metas_data)

        # 4. 创建文件级别的特征关联（function_name → file, string → file）
        for ff in file_features:
            if isinstance(ff, FileFeatureData):
                sha256 = ff.sha256
                fn_names = ff.function_names
                str_values = ff.strings
            else:
                sha256 = ff.get('sha256')
                fn_names = ff.get('function_names', [])
                str_values = ff.get('strings', [])

            file_id = sha256_to_file_id.get(sha256)
            if not file_id:
                continue

            # 关联函数名到文件
            if fn_names:
                fn_ids = [
                    function_name_id_map[fn]
                    for fn in fn_names
                    if fn in function_name_id_map
                ]
                if fn_ids:
                    add_function_names_to_file(fn_ids, file_id)

            # 关联字符串到文件
            if str_values:
                str_ids = [
                    string_id_map[s]
                    for s in str_values
                    if s in string_id_map
                ]
                if str_ids:
                    add_strings_to_file(str_ids, file_id)

    def add_licenses_for_version(
        self,
        source_code_id: int,
        licenses: List[LicenseInfo]
    ) -> int:
        """
        为版本添加 license

        Args:
            source_code_id: SourceCode ID
            licenses: License 列表

        Returns:
            添加的 license 数量
        """
        added_count = 0

        for license_info in licenses:
            try:
                # 获取或创建 License（基于 content_hash 去重）
                license_obj, created = get_or_create_license(
                    name=license_info.name,
                    content=license_info.content
                )

                # 创建关联
                add_license_to_source_code(
                    source_code_id=source_code_id,
                    license_id=license_obj.id,
                    file_path=license_info.file_path
                )

                added_count += 1

            except Exception as e:
                logger.error(f"添加 License 失败: {e}")
                continue

        return added_count

    def refresh_library_status(self, library_id: int):
        """刷新库状态"""
        try:
            refresh_library_status(library_id)
        except Exception as e:
            logger.error(f"刷新 LibraryStatus 失败: {e}")

    def delete_library_complete(self, library_name: str) -> bool:
        """
        完整删除库及所有相关数据

        Args:
            library_name: 库名称

        Returns:
            是否成功
        """
        library = get_library_by_name(library_name)
        if not library:
            logger.warning(f"库不存在: {library_name}")
            return False

        try:
            repo_delete_library(library.id, cascade=True)
            logger.info(f"已删除库: {library_name}")
            return True
        except Exception as e:
            logger.error(f"删除库失败 {library_name}: {e}")
            return False

    def _filter_strings(self, strings: List[str]) -> List[str]:
        """过滤字符串"""
        return [
            s for s in strings
            if self.min_str_length <= len(s) <= self.max_str_length
        ]

    def _filter_function_names(self, function_names: List[str]) -> List[str]:
        """过滤函数名"""
        return [
            fn for fn in function_names
            if self.min_function_name_length <= len(fn) <= self.max_function_name_length
        ]

    def get_library_by_name(self, name: str):
        """根据名称获取库"""
        return get_library_by_name(name)

    def get_source_code_by_commit(self, library_id: int, commit_id: str):
        """根据 commit_id 获取 SourceCode"""
        return get_source_code_by_commit(library_id, commit_id)
