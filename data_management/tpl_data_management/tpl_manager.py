"""
TPL Manager - 库管理工具（模块化版本）

主要功能：
- 一键添加库（clone → 获取版本 → 提取特征 → 入库）
- 删除库及所有相关数据
- 批量操作支持

使用模块化的 Processor 设计，便于调试和维护
"""
import json
import os
from typing import List, Optional, Dict, Any

from loguru import logger

from data_management.tpl_data_management.tpl_feature_extraction import ProjectFeatureExtractor, ProjectFeature
from data_management.tpl_data_management.tpl_processors import (
    GitProcessor,
    VersionProcessor,
    LicenseProcessor,
    MetadataProcessor,
    IngestionProcessor,
    ProcessingResult,
    FeatureData,
    FileFeatureData,
)


class TPLManager:
    """TPL 库管理器"""

    def __init__(
        self,
        # === 目录配置 ===
        source_dir: str = "tmp/source_code",
        features_dir: str = "tmp/features",

        # === 特征提取配置：基础 ===
        process_num: int = 4,                    # 并行进程数
        show_progress: bool = True,              # 是否显示进度条

        # === 特征提取配置：版本选择 ===
        max_feature_versions: int = 10,          # 最多提取特征的版本数量
        filter_prerelease: bool = True,          # 是否过滤预发布版本

        # === 特征提取配置：字符串过滤 ===
        min_str_length: int = 4,                 # 最小字符串长度
        max_str_length: int = 500,               # 最大字符串长度

        # === 特征提取配置：函数名过滤 ===
        min_function_name_length: int = 4,       # 最小函数名长度
        max_function_name_length: int = 100,     # 最大函数名长度

        # === License 配置 ===
        max_license_size: int = 100 * 1024,      # 最大 license 文件大小（字节）
        extract_license: bool = True,            # 是否提取 license
    ):
        """
        初始化 TPL 管理器

        Args:
            source_dir: 源代码存储目录
            features_dir: 特征文件存储目录
            process_num: 并行进程数
            show_progress: 是否显示进度条
            max_feature_versions: 最多提取特征的版本数量
            filter_prerelease: 是否过滤预发布版本 (alpha, beta, rc 等)
            min_str_length: 最小字符串长度
            max_str_length: 最大字符串长度
            min_function_name_length: 最小函数名长度
            max_function_name_length: 最大函数名长度
            max_license_size: 最大 license 文件大小（字节）
            extract_license: 是否提取 license
        """
        # 保存配置
        self.source_dir = source_dir
        self.features_dir = features_dir
        self.max_feature_versions = max_feature_versions
        self.filter_prerelease = filter_prerelease
        self.process_num = process_num
        self.show_progress = show_progress
        self.extract_license = extract_license

        # 初始化各 Processor
        self.git = GitProcessor(source_dir)
        self.version = VersionProcessor(max_feature_versions)
        self.license = LicenseProcessor(max_license_size)
        self.metadata = MetadataProcessor()
        self.ingestion = IngestionProcessor(
            min_str_length=min_str_length,
            max_str_length=max_str_length,
            min_function_name_length=min_function_name_length,
            max_function_name_length=max_function_name_length,
        )

    def add_library(
        self,
        name: str,
        git_url: str,
        vendor: Optional[str] = None,
        homepage: Optional[str] = None,
        description: Optional[str] = None,
        language: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        purl: Optional[str] = None,
        alias: Optional[str] = None,
        force_clone: bool = False,
        skip_existing_library: bool = True,
        auto_detect_language: bool = True,
        lib_index: int = 0,
        total_libs: int = 0,
    ) -> ProcessingResult:
        """
        一键添加库 - 完整流程

        流程：
        1. Clone 仓库
        2. 解析元数据（homepage, purl, language 自动检测）
        3. 获取所有版本（含 semantic_version_str）
        4. 创建 Library 和所有 SourceCode 记录
        5. 选择版本并提取特征
        6. 提取 License（对最新版本）
        7. 刷新 LibraryStatus

        Args:
            name: 库名称
            git_url: Git 仓库 URL
            vendor: 供应商（如果为空，从 git URL 解析）
            homepage: 主页 URL（如果为空，从 git URL 推断）
            description: 描述（预留，暂不自动提取）
            language: 编程语言列表（如果为空且 auto_detect_language=True，自动检测）
            categories: 分类列表（预留，暂不自动提取）
            purl: Package URL（如果为空，自动生成）
            alias: 库别名
            force_clone: 强制重新 clone
            skip_existing_library: 如果库已存在是否跳过
            auto_detect_language: 是否自动检测编程语言

        Returns:
            ProcessingResult
        """
        result = ProcessingResult(library_name=name)

        try:
            # ========== 阶段1: Clone 仓库 ==========
            success, repo_path_or_error, was_skipped = self.git.clone_repository(name, git_url, force=force_clone)
            if not success:
                result.add_error(f"Clone 失败: {repo_path_or_error}")
                return result
            repo_path = repo_path_or_error
            clone_status = "已存在" if was_skipped else "完成"
            logger.info(f"📦 Clone: {git_url} -> {repo_path} ({clone_status})")

            # ========== 阶段2: 解析元数据 ==========
            detected_language = language
            if not language and auto_detect_language:
                detected_language = self.metadata.detect_language_from_repo(repo_path)

            library_info = self.metadata.build_library_info(
                name=name,
                git_url=git_url,
                vendor=vendor,
                homepage=homepage,
                description=description,
                language=detected_language,
                categories=categories,
                purl=purl,
                alias=alias,
            )
            lang_str = ', '.join(library_info.language) if library_info.language else '未知'
            logger.info(f"📋 元数据: {lang_str} | {library_info.purl or '无PURL'}")

            # ========== 阶段3: 创建/获取 Library ==========
            library_id, is_new = self.ingestion.create_or_get_library(library_info)
            result.library_id = library_id
            lib_status = "新建" if is_new else "已存在"
            logger.info(f"💾 Library: ID={library_id} ({lib_status})")

            if not is_new and skip_existing_library:
                logger.warning(f"   ⏭️ 库已存在，跳过后续处理")
                result.add_warning(f"库已存在，跳过: {name}")
                result.success = True
                return result

            # ========== 阶段4: 获取版本 ==========
            versions = self.version.get_all_versions(repo_path)
            result.versions_total = len(versions)

            use_default_branch = False
            if not versions:
                versions = self.version.get_default_branch_as_version(repo_path)
                use_default_branch = True
                if not versions:
                    logger.error(f"🏷️ 版本: 0 标签, 无法获取默认分支 ❌")
                    result.add_error("没有找到版本标签，且无法获取默认分支")
                    return result
                result.versions_total = 1
                result.add_warning("没有版本标签，使用默认分支作为唯一版本")
                logger.warning(f"🏷️ 版本: 0 标签 -> 使用默认分支 {versions[0].tag} ({versions[0].commit_id[:8]})")
            else:
                logger.info(f"🏷️ 版本: {len(versions)} 个标签")

            # ========== 阶段5: 添加版本到数据库 ==========
            added_version_count, added_tag_count, version_id_map = self.ingestion.add_all_versions(library_id, versions)
            result.versions_added = added_version_count
            logger.info(f"💾 入库: {added_version_count} 版本, {added_tag_count} Tag")

            # ========== 阶段6: 特征提取 ==========
            if use_default_branch:
                selected_versions = versions
                filtered_versions = versions
            else:
                if self.filter_prerelease:
                    filtered_versions = self.version.filter_release_versions(versions)
                    if not filtered_versions:
                        filtered_versions = versions
                else:
                    filtered_versions = versions
                self.version.select_versions_for_feature_extraction(filtered_versions)
                selected_versions = self.version.get_selected_versions(filtered_versions)

            logger.info(f"🔬 特征提取: 选中 {len(selected_versions)}/{len(filtered_versions)} 个版本")

            # 提取特征
            features_count = self._extract_and_ingest_features(
                name, repo_path, library_id, selected_versions, version_id_map, result,
                total_versions_all=result.versions_total,
                lib_index=lib_index,
                total_libs=total_libs,
            )
            result.versions_with_features = features_count

            # ========== 阶段7: 提取 License ==========
            if self.extract_license:
                versions_for_license = versions if use_default_branch else filtered_versions
                latest_version = self.version.get_latest_version(versions_for_license)
                if latest_version and latest_version.tag in version_id_map:
                    self.git.checkout_version(repo_path, latest_version.tag)
                    licenses = self.license.detect_licenses(repo_path)
                    if licenses:
                        license_names = [lic.name for lic in licenses]
                        source_code_id = version_id_map[latest_version.tag]
                        result.licenses_added = self.ingestion.add_licenses_for_version(source_code_id, licenses)
                        logger.info(f"📜 License: {', '.join(license_names)}")
                    else:
                        logger.warning(f"📜 License: 未检测到 ⚠️")
                else:
                    logger.warning(f"📜 License: 无可用版本 ⚠️")
            else:
                logger.info(f"📜 License: 已禁用")

            # ========== 阶段8: 刷新状态 ==========
            self.ingestion.refresh_library_status(library_id)

            # ========== 完成汇总 ==========
            result.success = True
            warn_str = f" | 警告 {len(result.warnings)}" if result.warnings else ""
            err_str = f" | 错误 {len(result.errors)}" if result.errors else ""
            logger.info(f"{'─'*60}")
            logger.info(f"✅ 完成: 版本 {result.versions_added} | 特征 {result.versions_with_features} | License {result.licenses_added}{warn_str}{err_str}")

        except Exception as e:
            logger.error(f"❌ 添加库失败: {e}")
            result.add_error(str(e))

        return result

    def _extract_and_ingest_features(
        self,
        name: str,
        repo_path: str,
        library_id: int,
        selected_versions: List,
        version_id_map: Dict[str, int],
        extraction_result: ProcessingResult,
        total_versions_all: int = 0,
        lib_index: int = 0,
        total_libs: int = 0,
    ) -> int:
        """
        提取并入库特征

        Args:
            name: 库名称
            repo_path: 仓库路径
            library_id: Library ID
            selected_versions: 选中的版本列表
            version_id_map: {tag: source_code_id} 映射
            extraction_result: 结果对象（用于记录错误）
            total_versions_all: 总版本数（用于日志显示）
            lib_index: 当前库序号（用于日志显示）
            total_libs: 总库数（用于日志显示）

        Returns:
            成功处理的版本数
        """
        features_count = 0
        failed_count = 0
        file_feature_cache = {}  # 跨版本文件特征缓存
        total_versions = len(selected_versions)

        if total_versions == 0:
            logger.warning(f"   ⚠️ 无需提取特征")
            return 0

        # 使用内存临时目录加速
        mem_temp_dir, mem_repo = self.git.copy_to_memory(repo_path, name)
        if not mem_repo:
            extraction_result.add_error("无法复制到内存")
            logger.error(f"   ❌ 复制仓库到内存失败")
            return 0

        mem_repo_path = os.path.join(mem_temp_dir, name)

        try:
            for idx, version in enumerate(selected_versions, 1):
                tag = version.tag
                if tag not in version_id_map:
                    continue

                source_code_id = version_id_map[tag]

                # 打印版本处理日志
                lib_info = f"[{lib_index}/{total_libs}]" if lib_index > 0 else ""
                version_info = f"{idx}/{total_versions}" if total_versions_all == 0 else f"{idx}/{total_versions}/{total_versions_all}"
                logger.info(f"   🔄 {lib_info} {name} - {tag} ({version_info})")

                try:
                    # Checkout
                    if not self._checkout_with_retry(mem_repo, tag, repo_path, name, mem_temp_dir):
                        extraction_result.add_warning(f"Checkout {tag} 失败")
                        failed_count += 1
                        logger.warning(f"   [{idx}/{total_versions}] {tag}: ❌ Checkout 失败")
                        continue

                    # 重新获取路径（可能因为重试重新创建了）
                    if mem_temp_dir and os.path.exists(mem_temp_dir):
                        mem_repo_path = os.path.join(mem_temp_dir, name)

                    # 提取特征
                    extractor = ProjectFeatureExtractor(
                        project_name=name,
                        project_path=mem_repo_path,
                        file_feature_cache=file_feature_cache,
                        show_progress=self.show_progress,
                    )
                    project_feature = extractor.extract(process_num=self.process_num)

                    # 更新缓存
                    for ff in project_feature.file_features:
                        if ff.sha256 not in file_feature_cache:
                            file_feature_cache[ff.sha256] = ff

                    # 收集特征（包括文件级特征）
                    all_strings, all_function_names, file_feature_data_list = self._collect_features(project_feature)

                    # 构建 FeatureData（包含文件级特征）
                    feature_data = FeatureData(
                        tag=tag,
                        commit_id=version.commit_id,
                        strings=all_strings,
                        function_names=all_function_names,
                        project_size_mb=project_feature.project_size_mb,
                        total_src_file=project_feature.total_src_file,
                        failed_src_file=project_feature.failed_src_file,
                        function_count=project_feature.function_count,
                        distinct_string_count=project_feature.distinct_string_count,
                        extraction_succeed=project_feature.extraction_succeed,
                        extraction_log=project_feature.extraction_log,
                        file_features=file_feature_data_list,
                    )

                    # 入库
                    if self.ingestion.add_features_for_version(library_id, source_code_id, feature_data):
                        features_count += 1
                        # logger.info(f"   [{idx}/{total_versions}] {tag}: ✅ {len(all_strings)} 字符串, {len(all_function_names)} 函数名, {project_feature.total_src_file} 源文件")
                    else:
                        failed_count += 1
                        # logger.warning(f"   [{idx}/{total_versions}] {tag}: ❌ 入库失败")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"   [{idx}/{total_versions}] {tag}: ❌ 错误 - {e}")
                    extraction_result.add_error(f"{tag}: {str(e)}")

        finally:
            # 清理内存临时目录
            self.git.cleanup_memory_dir(mem_temp_dir)

        # 提取完成汇总
        if failed_count > 0:
            logger.warning(f"   📊 提取汇总: 成功 {features_count}, 失败 {failed_count} ⚠️")
        else:
            logger.info(f"   📊 提取汇总: 成功 {features_count}, 失败 {failed_count}")

        return features_count

    def _checkout_with_retry(self, mem_repo, tag, original_repo_path, name, mem_temp_dir) -> bool:
        """
        Checkout 版本，失败时重试

        Returns:
            是否成功
        """
        try:
            if tag != 'HEAD':
                try:
                    mem_repo.git.stash('save', 'before checkout')
                except:
                    pass
                mem_repo.git.checkout(tag, force=True)
            return True
        except Exception as e:
            logger.warning(f"Checkout {tag} 失败: {e}，重新复制重试...")

            # 清理并重新复制
            self.git.cleanup_memory_dir(mem_temp_dir)
            new_mem_temp_dir, new_mem_repo = self.git.copy_to_memory(original_repo_path, name)

            if new_mem_repo:
                try:
                    if tag != 'HEAD':
                        new_mem_repo.git.checkout(tag, force=True)
                    return True
                except Exception as e2:
                    logger.error(f"重试 Checkout {tag} 仍失败: {e2}")

            return False

    def _collect_features(self, project_feature: ProjectFeature) -> tuple:
        """
        从 ProjectFeature 收集所有字符串、函数名以及文件级特征

        Returns:
            (all_strings, all_function_names, file_feature_data_list)
        """
        all_strings = set()
        all_function_names = set()
        file_feature_data_list = []

        for file_feature in project_feature.file_features:
            # 收集库级别的特征（去重）
            file_strings = file_feature.get_strings()
            file_function_names = file_feature.get_function_names()

            all_strings.update(file_strings)
            all_function_names.update(file_function_names)

            # 构建文件级别的特征数据
            file_feature_data_list.append(FileFeatureData(
                path=file_feature.path,
                sha256=file_feature.sha256,
                name=file_feature.name,
                extension=file_feature.extension,
                file_size_kb=file_feature.file_size_kb,
                function_num=file_feature.function_num,
                distinct_string_num=file_feature.distinct_string_num,
                extraction_succeed=file_feature.extraction_succeed,
                extraction_log=file_feature.extraction_log,
                global_strings=file_feature.global_strings,
                function_names=file_function_names,
                strings=file_strings,
            ))

        return list(all_strings), list(all_function_names), file_feature_data_list

    def delete_library(self, name: str, delete_local_repo: bool = False) -> bool:
        """
        删除库及所有关联数据

        Args:
            name: 库名称
            delete_local_repo: 是否同时删除本地仓库

        Returns:
            是否成功
        """
        success = self.ingestion.delete_library_complete(name)

        if delete_local_repo:
            self.git.delete_repository(name)

        return success

    def delete_libraries_by_names(self, names: List[str], delete_local_repos: bool = False) -> Dict[str, List[str]]:
        """
        批量删除库

        Args:
            names: 库名称列表
            delete_local_repos: 是否同时删除本地仓库

        Returns:
            {'success': [...], 'not_found': [...], 'failed': [...]}
        """
        results = {'success': [], 'not_found': [], 'failed': []}

        for name in names:
            library = self.ingestion.get_library_by_name(name)
            if not library:
                results['not_found'].append(name)
                continue

            if self.delete_library(name, delete_local_repos):
                results['success'].append(name)
            else:
                results['failed'].append(name)

        return results

    def batch_add_libraries(
        self,
        libraries: List[tuple],
        skip_existing: bool = True,
    ) -> Dict[str, Any]:
        """
        批量添加库

        Args:
            libraries: [(name, vendor, git_url), ...] 或 [(name, git_url), ...]
            skip_existing: 是否跳过已存在的库

        Returns:
            {'success': [...], 'failed': [...], 'skipped': [...]}
        """
        results = {
            'success': [],
            'failed': [],
            'skipped': [],
        }

        total = len(libraries)
        for i, lib_tuple in enumerate(libraries, 1):
            # 解析参数
            if len(lib_tuple) == 3:
                name, vendor, git_url = lib_tuple
            elif len(lib_tuple) == 2:
                name, git_url = lib_tuple
                vendor = None
            else:
                results['failed'].append((lib_tuple, "参数格式错误"))
                continue

            print(f"\n{'='*60}")
            print(f"[{i}/{total}] 添加库: {name}")
            print(f"{'='*60}")

            # 检查是否已存在
            if skip_existing:
                existing = self.ingestion.get_library_by_name(name)
                if existing:
                    print(f"  ⏭️  库已存在，跳过: {name} (ID: {existing.id})")
                    results['skipped'].append(name)
                    continue

            try:
                result = self.add_library(
                    name=name,
                    git_url=git_url,
                    vendor=vendor,
                    skip_existing_library=skip_existing,
                    lib_index=i,
                    total_libs=total,
                )

                if result.success:
                    print(f"  ✅ 成功添加: {name}")
                    results['success'].append(name)
                else:
                    print(f"  ❌ 添加失败: {name}")
                    results['failed'].append((name, result.errors))

            except Exception as e:
                print(f"  ❌ 异常: {name} - {e}")
                results['failed'].append((name, str(e)))

        # 打印汇总
        print(f"\n{'='*60}")
        print("批量添加完成")
        print(f"{'='*60}")
        print(f"成功: {len(results['success'])} 个")
        print(f"跳过: {len(results['skipped'])} 个")
        print(f"失败: {len(results['failed'])} 个")

        if results['failed']:
            print("\n失败的库:")
            for item in results['failed']:
                if isinstance(item, tuple):
                    print(f"  - {item[0]}")
                else:
                    print(f"  - {item}")

        return results


# ============ 便捷函数（保持向后兼容）============

def add_library_from_git(
    library_name: str,
    git_url: str,
    source_dir: str = "tmp/source_code",
    features_dir: str = "tmp/features",
    max_versions: int = 10,
    process_num: int = 4,
    show_progress: bool = True,
    vendor: Optional[str] = None,
) -> Dict:
    """一键添加库（兼容旧接口）"""
    manager = TPLManager(
        source_dir=source_dir,
        features_dir=features_dir,
        max_feature_versions=max_versions,
        process_num=process_num,
        show_progress=show_progress,
    )
    result = manager.add_library(
        name=library_name,
        git_url=git_url,
        vendor=vendor,
    )
    return result.to_dict()


def delete_libraries_by_names(library_names: List[str]) -> dict:
    """批量删除库（兼容旧接口）"""
    manager = TPLManager()
    return manager.delete_libraries_by_names(library_names)


# ============ 测试入口 ============

if __name__ == '__main__':
    # 示例：添加单个库
    manager = TPLManager(
        # === 目录配置 ===
        source_dir="tmp/source_code",
        features_dir="tmp/features",

        # === 特征提取配置：基础 ===
        process_num=4,  # 并行进程数
        show_progress=True,  # 是否显示进度条

        # === 特征提取配置：版本选择 ===
        max_feature_versions=10,  # 最多提取特征的版本数量
        filter_prerelease=True,  # 是否过滤预发布版本

        # === 特征提取配置：字符串过滤 ===
        min_str_length=4,  # 最小字符串长度
        max_str_length=500,  # 最大字符串长度

        # === 特征提取配置：函数名过滤 ===
        min_function_name_length=4,  # 最小函数名长度
        max_function_name_length=100,  # 最大函数名长度

        # === License 配置 ===
        max_license_size=100 * 1024,  # 最大 license 文件大小（字节）
        extract_license=True,  # 是否提取 license
    )

    # 批量删除 - 17个未召回的库，重新提取特征
    LIBS_TO_DELETE = [
        'boost-asio',
    ]

    manager.delete_libraries_by_names(LIBS_TO_DELETE,
                                      delete_local_repos=True)

    # 批量添加: name, vendor, git_url
    # LIBS_TO_ADD = [
    #     ('ohPipeline', 'openhome', 'https://github.com/openhome/ohPipeline'),
    #     ('ohNet', 'openhome', 'https://github.com/openhome/ohNet')
    # ]
    #
    # libraries = LIBS_TO_ADD
    # results = manager.batch_add_libraries(libraries)
