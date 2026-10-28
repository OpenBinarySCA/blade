"""
String Feature Matcher - 字符串特征匹配器

职责：基于字符串特征从知识库检索匹配的库
- 输入：TargetBinary (包含字符串列表) + hint_names (名称匹配的库名)
- 输出：List[LibraryHypothesis]

架构：单路召回（仅字符串特征匹配）
- hint 召回由上层 FeatureRecallManager 统一处理
"""

from typing import List, Set

from loguru import logger

from app.databases.postgres.repository import library_repository
from app.databases.postgres.entities import ProjectFeature as ProjectFeatureEntity
from app.interface import TargetBinary, LibraryHypothesis
from .feature_filter import filter_strings

# ========== 默认库黑名单（系统库，不应作为检测结果）==========
DEFAULT_LIBRARY_BLACKLIST = {
    'glibc', 'gcc', 'libstdc++', 'libgcc_s', 'libgcc',
    'musl', 'uclibc', 'newlib',  # 其他 C 库
}

# ========== 默认最小匹配数阈值 ==========
DEFAULT_MIN_MATCH_COUNT_THRESHOLD = 5


class StringFeatureMatcher:
    """
    字符串特征匹配器

    单路召回：仅负责字符串特征匹配
    hint 召回由上层 FeatureRecallManager 统一处理
    """

    def __init__(self,
                 feature_min_length: int = 5,
                 feature_max_length: int = 500,
                 min_match_count_threshold: int = None,
                 library_blacklist: Set[str] = None):
        """
        初始化字符串特征匹配器

        Args:
            feature_min_length: 最小特征长度
            feature_max_length: 最大特征长度
            min_match_count_threshold: 最小匹配数阈值，低于此数量的候选会被过滤
            library_blacklist: 库黑名单（系统库，不应作为检测结果）
        """
        self.feature_min_length = feature_min_length
        self.feature_max_length = feature_max_length
        self.min_effective_string_length = 10

        # 可配置的过滤参数
        self.library_blacklist = library_blacklist if library_blacklist is not None else DEFAULT_LIBRARY_BLACKLIST
        self.min_match_count_threshold = min_match_count_threshold if min_match_count_threshold is not None else DEFAULT_MIN_MATCH_COUNT_THRESHOLD

        self.method_name = "feature_matching"
        self.source_name = "string"  # 统一用简短名称

    # ==========================================================================
    # 第一级：主入口
    # ==========================================================================

    def match(self, target_binary: TargetBinary, top_n: int = None,
              filtered_features: List[str] = None) -> List[LibraryHypothesis]:
        """
        字符串特征匹配主入口

        流程：特征过滤 → 数据库匹配（应用 min_match 和 top_n）→ 黑名单过滤 → 转换为假设

        Args:
            target_binary: 目标二进制文件对象
            top_n: 返回数量限制，None 表示不限制
            filtered_features: 预过滤的字符串列表（如已提供则跳过过滤步骤）

        Returns:
            List[LibraryHypothesis]: 匹配的假设列表
        """
        # Step 1: 使用预过滤数据或自行过滤
        if filtered_features is not None:
            filtered_strings = filtered_features
            logger.debug(f"String feature matching for: {target_binary.binary_name} (using {len(filtered_strings)} pre-filtered strings)")
        else:
            if not target_binary.strings:
                logger.warning(f"No strings provided for binary: {target_binary.binary_name}")
                return []
            logger.debug(f"String feature matching for: {target_binary.binary_name} ({len(target_binary.strings)} strings)")
            filtered_strings = self._filter_features(target_binary)

        if not filtered_strings:
            logger.debug("No valid strings after filtering")
            return []

        # Step 2: 数据库批量匹配（直接在数据库层应用 min_match 和 top_n）
        candidates = self._query_database(filtered_strings, top_n=top_n)
        if not candidates:
            logger.debug("No candidates from database")
            return []

        # Step 3: 黑名单过滤（min_match 已在数据库层过滤）
        filtered_candidates = self._filter_blacklist(candidates)
        if not filtered_candidates:
            logger.debug("No candidates after filtering")
            return []

        # Step 4: 转换为假设
        hypotheses = self._convert_to_hypotheses(filtered_candidates)

        logger.debug(f"String feature matching: {len(hypotheses)} results")
        return hypotheses

    # ==========================================================================
    # 第二级：主要步骤方法
    # ==========================================================================

    def _filter_features(self, target_binary: TargetBinary) -> List[str]:
        """
        Step 1: 特征过滤

        过滤规则：
        - 长度限制
        - 排除 ELF section 名称
        - 排除 C/C++ 函数名格式
        - 排除通用字符串（hash 过滤）
        """
        return self._filter_strings_impl(target_binary)

    def _query_database(self, strings: List[str], top_n: int = None) -> List[ProjectFeatureEntity]:
        """
        Step 2: 数据库批量匹配

        直接在数据库层应用 min_match_num 和 top_n，减少数据传输。
        """
        # 使用配置的 min_match_threshold，默认 5
        # top_n 为 None 时使用较大值确保召回
        effective_top_n = top_n if top_n else 100
        candidates = library_repository.list_libraries_by_strings(
            strings,
            min_match_num=self.min_match_count_threshold,
            top_n=effective_top_n
        )
        return candidates or []

    def _filter_blacklist(self, candidates: List[ProjectFeatureEntity]) -> List[ProjectFeatureEntity]:
        """
        Step 3: 黑名单过滤

        min_match 过滤已在数据库层完成。
        """
        filtered = []
        for entity in candidates:
            # 黑名单过滤
            if entity.name and entity.name.lower() in self.library_blacklist:
                logger.debug(f"Filtered (blacklist): {entity.name}")
                continue

            filtered.append(entity)

        return filtered

    def _sort_by_match_count(self, candidates: List[ProjectFeatureEntity]) -> List[ProjectFeatureEntity]:
        """
        Step 4: 按匹配数量倒序排序，数量相同时按覆盖率排序
        """
        def sort_key(entity):
            # 计算有效字符串数量（长度>=10 或包含空格的）
            effective_count = 0
            for s in (entity.matched_strings or []):
                if " " in s or len(s) >= self.min_effective_string_length:
                    effective_count += 1
            total_count = len(entity.matched_strings) if entity.matched_strings else 0
            # 覆盖率作为第三排序键（数据库层已计算 match_coverage）
            coverage = getattr(entity, 'match_coverage', 0) or 0
            return (-effective_count, -total_count, -coverage)

        return sorted(candidates, key=sort_key)

    def _convert_to_hypotheses(self, candidates: List[ProjectFeatureEntity]) -> List[LibraryHypothesis]:
        """
        Step 5: 转换为假设对象
        """
        hypotheses = []
        for entity in candidates:
            # 获取库的描述信息
            description = ""
            if hasattr(entity, 'library') and entity.library:
                description = entity.library.description or ""

            matched_strings = entity.matched_strings or []
            hypothesis = LibraryHypothesis(
                library_name=entity.name,
                library_id=entity.id,
                method=self.method_name,
                source=self.source_name,
                evidence=matched_strings,
                description=description,
                integration_type="Static Linked"
            )
            # 设置分项统计（供合并排序使用）
            hypothesis._string_count = len(matched_strings)
            hypothesis._symbol_count = 0
            hypothesis._string_evidence = matched_strings
            hypothesis._symbol_evidence = []
            # 覆盖率（数据库层计算）
            hypothesis._coverage = getattr(entity, 'match_coverage', 0) or 0
            hypotheses.append(hypothesis)

        return hypotheses

    # ==========================================================================
    # 第三级：步骤细节实现
    # ==========================================================================

    def _filter_strings_impl(self, target_binary: TargetBinary) -> List[str]:
        """特征过滤 - 复用 feature_filter.py 的统一逻辑"""
        return filter_strings(
            target_binary.strings or [],
            min_length=self.feature_min_length,
            max_length=self.feature_max_length
        )


# 向后兼容的别名
FeatureMatcher = StringFeatureMatcher
StringFeatureRetriever = StringFeatureMatcher
