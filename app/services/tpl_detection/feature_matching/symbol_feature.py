"""
Symbol Feature Matcher - 符号特征匹配器

职责：基于符号/函数名特征从知识库检索匹配的库
- 输入：TargetBinary (包含符号列表)
- 输出：List[LibraryHypothesis]

架构：单路召回（仅符号特征匹配）
- hint 召回由上层 FeatureRecallManager 统一处理

支持 C++ 符号 demangle：将 _ZN5boost... 等修饰名称还原为 boost::detail::... 形式，
并提取函数名用于匹配。
"""

from typing import List, Set

from loguru import logger

from app.databases.postgres.repository import library_repository
from app.databases.postgres.entities import Library as LibraryEntity
from app.interface import TargetBinary, LibraryHypothesis
from .feature_filter import filter_symbols

# ========== 默认库黑名单（系统库，不应作为检测结果）==========
DEFAULT_LIBRARY_BLACKLIST = {
    'glibc', 'gcc', 'libstdc++', 'libgcc_s', 'libgcc',
    'musl', 'uclibc', 'newlib',  # 其他 C 库
}

# ========== 默认最小匹配数阈值 ==========
DEFAULT_MIN_MATCH_COUNT_THRESHOLD = 5


class SymbolFeatureMatcher:
    """
    符号特征匹配器

    单路召回：仅负责符号特征匹配
    hint 召回由上层 FeatureRecallManager 统一处理
    """

    def __init__(self,
                 min_symbol_length: int = 5,
                 max_symbol_length: int = 50,
                 min_match_count_threshold: int = None,
                 library_blacklist: Set[str] = None,
                 use_imported_symbols: bool = False):
        """
        初始化符号特征匹配器

        Args:
            min_symbol_length: 最小符号长度
            max_symbol_length: 最大符号长度
            min_match_count_threshold: 最小匹配数阈值，低于此数量的候选会被过滤
            library_blacklist: 库黑名单（系统库，不应作为检测结果）
            use_imported_symbols: 是否使用导入符号（默认 False，只使用导出符号）
        """
        self.min_symbol_length = min_symbol_length
        self.max_symbol_length = max_symbol_length

        # 可配置的过滤参数
        self.library_blacklist = library_blacklist if library_blacklist is not None else DEFAULT_LIBRARY_BLACKLIST
        self.min_match_count_threshold = min_match_count_threshold if min_match_count_threshold is not None else DEFAULT_MIN_MATCH_COUNT_THRESHOLD
        self.use_imported_symbols = use_imported_symbols

        self.method_name = "feature_matching"
        self.source_name = "symbol"  # 统一用简短名称

    # ==========================================================================
    # 第一级：主入口
    # ==========================================================================

    def match(self, target_binary: TargetBinary, top_n: int = None,
              filtered_features: List[str] = None) -> List[LibraryHypothesis]:
        """
        符号特征匹配主入口

        流程：特征过滤 → 数据库匹配（应用 min_match 和 top_n）→ 黑名单过滤 → 转换为假设

        Args:
            target_binary: 目标二进制文件对象
            top_n: 返回数量限制，None 表示不限制
            filtered_features: 预过滤的符号列表（如已提供则跳过过滤步骤）

        Returns:
            List[LibraryHypothesis]: 匹配的假设列表
        """
        # Step 1: 使用预过滤数据或自行过滤
        if filtered_features is not None:
            filtered_symbols = filtered_features
            logger.debug(f"Symbol feature matching for: {target_binary.binary_name} (using {len(filtered_symbols)} pre-filtered symbols)")
        else:
            # 收集符号
            all_symbols = []
            if target_binary.exported_symbols:
                all_symbols.extend(target_binary.exported_symbols)
            if self.use_imported_symbols and target_binary.imported_symbols:
                all_symbols.extend(target_binary.imported_symbols)

            if not all_symbols:
                logger.debug("No symbols provided for matching")
                return []

            logger.debug(f"Symbol feature matching for: {target_binary.binary_name} ({len(all_symbols)} symbols)")
            filtered_symbols = self._filter_features(all_symbols)

        if not filtered_symbols:
            logger.debug("No valid symbols after filtering")
            return []

        # Step 2: 数据库批量匹配（直接在数据库层应用 min_match 和 top_n）
        candidates = self._query_database(filtered_symbols, top_n=top_n)
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

        logger.debug(f"Symbol feature matching: {len(hypotheses)} results")
        return hypotheses

    # ==========================================================================
    # 第二级：主要步骤方法
    # ==========================================================================

    def _filter_features(self, symbols: List[str]) -> List[str]:
        """
        Step 1: 特征过滤

        过滤规则：
        - C++ 符号 demangle
        - 排除系统符号前缀
        - 长度限制
        - 排除通用函数名（hash 过滤）
        """
        return self._filter_symbols_impl(symbols)

    def _query_database(self, symbols: List[str], top_n: int = None) -> List[LibraryEntity]:
        """
        Step 2: 数据库批量匹配

        直接在数据库层应用 min_match_num 和 top_n，减少数据传输。
        """
        # 使用配置的 min_match_threshold，默认 5
        # top_n 为 None 时使用较大值确保召回
        effective_top_n = top_n if top_n else 100
        candidates = library_repository.list_libraries_by_function_names(
            symbols,
            min_match_num=self.min_match_count_threshold,
            top_n=effective_top_n
        )
        return candidates or []

    def _filter_blacklist(self, candidates: List[LibraryEntity]) -> List[LibraryEntity]:
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

    def _sort_by_match_count(self, candidates: List[LibraryEntity]) -> List[LibraryEntity]:
        """
        Step 4: 按匹配数量倒序排序，数量相同时按覆盖率排序
        """
        def sort_key(entity):
            match_count = len(getattr(entity, 'matched_function_names', [])) if hasattr(entity, 'matched_function_names') else 0
            # 覆盖率作为第二排序键（数据库层已计算 match_coverage）
            coverage = getattr(entity, 'match_coverage', 0) or 0
            return (-match_count, -coverage)

        return sorted(candidates, key=sort_key)

    def _convert_to_hypotheses(self, candidates: List[LibraryEntity]) -> List[LibraryHypothesis]:
        """
        Step 5: 转换为假设对象
        """
        hypotheses = []
        for entity in candidates:
            # 获取匹配的函数名
            matched_symbols = getattr(entity, 'matched_function_names', []) or []

            # 获取描述
            description = getattr(entity, 'description', "") or ""

            hypothesis = LibraryHypothesis(
                library_name=entity.name,
                library_id=entity.id,
                method=self.method_name,
                source=self.source_name,
                evidence=matched_symbols,
                description=description,
                integration_type="Static Linked"
            )
            # 设置分项统计（供合并排序使用）
            hypothesis._string_count = 0
            hypothesis._symbol_count = len(matched_symbols)
            hypothesis._string_evidence = []
            hypothesis._symbol_evidence = matched_symbols
            # 覆盖率（数据库层计算）
            hypothesis._coverage = getattr(entity, 'match_coverage', 0) or 0
            hypotheses.append(hypothesis)

        return hypotheses

    # ==========================================================================
    # 第三级：步骤细节实现
    # ==========================================================================

    def _filter_symbols_impl(self, symbols: List[str]) -> List[str]:
        """特征过滤 - 复用 feature_filter.py 的统一逻辑"""
        return filter_symbols(
            symbols,
            min_length=self.min_symbol_length,
            max_length=self.max_symbol_length
        )


# 向后兼容的别名
SymbolFeatureRetriever = SymbolFeatureMatcher
