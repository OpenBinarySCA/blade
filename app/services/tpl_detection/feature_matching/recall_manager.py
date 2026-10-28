"""
Feature Recall Manager - 特征召回管理器

职责：管理三路召回（Hint + 字符串 + 符号）并合并结果
- 输入：TargetBinary
- 输出：List[LibraryHypothesis]

架构：
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              三路召回 + 合并                                     │
│                                                                                 │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────────┐   │
│  │ 路线1: Hint 召回   │  │ 路线2: 字符串匹配  │  │ 路线3: 符号匹配            │   │
│  └─────────┬─────────┘  └─────────┬─────────┘  └─────────────┬─────────────┘   │
│            └──────────────────────┼──────────────────────────┘                 │
│                                   ↓                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  合并：Round-Robin 边轮询边合并 → 取 top_n → 补充缺失特征                  │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple

from loguru import logger

from app.interface import TargetBinary, LibraryHypothesis
from app.databases.postgres.repository import library_repository
from .name_matcher import find_hint_library_names, get_library_info
from .string_feature import StringFeatureMatcher, DEFAULT_LIBRARY_BLACKLIST, DEFAULT_MIN_MATCH_COUNT_THRESHOLD
from .symbol_feature import SymbolFeatureMatcher
from .feature_filter import filter_strings, filter_symbols


@dataclass
class MergedCandidate:
    """合并后的候选结果"""
    library_id: int
    library_name: str
    description: str = ""

    # 各路线的匹配数量
    hint_match_count: int = 0
    string_match_count: int = 0
    symbol_match_count: int = 0

    # 各路线的证据
    hint_evidence: List[str] = field(default_factory=list)
    string_evidence: List[str] = field(default_factory=list)
    symbol_evidence: List[str] = field(default_factory=list)

    # 来源标记
    from_hint: bool = False
    from_string: bool = False
    from_symbol: bool = False

    @property
    def total_match_count(self) -> int:
        """总匹配数 = 字符串匹配数 + 符号匹配数"""
        return self.string_match_count + self.symbol_match_count

    @property
    def all_evidence(self) -> List[str]:
        """所有证据"""
        return self.string_evidence + self.symbol_evidence


class FeatureRecallManager:
    """
    特征召回管理器

    三路召回：Hint + 字符串特征 + 符号特征
    """

    def __init__(self,
                 # ==================== 路线开关 ====================
                 enable_hint_recall: bool = True,
                 enable_string_recall: bool = True,
                 enable_symbol_recall: bool = True,

                 # ==================== 过滤配置 ====================
                 hint_min_match_threshold: int = 1,
                 string_min_match_threshold: int = None,
                 symbol_min_match_threshold: int = None,
                 library_blacklist: Set[str] = None,

                 # ==================== 排序和输出配置 ====================
                 hint_first: bool = False,
                 retrieval_top_n: int = None,

                 # ==================== 符号匹配配置 ====================
                 symbol_use_imported: bool = False,
                 ):
        """
        初始化特征召回管理器

        Args:
            enable_hint_recall: 是否启用 hint 路线
            enable_string_recall: 是否启用字符串匹配路线
            enable_symbol_recall: 是否启用符号匹配路线
            hint_min_match_threshold: hint 路线最小匹配数阈值
            string_min_match_threshold: 字符串匹配路线最小匹配数阈值（默认 5）
            symbol_min_match_threshold: 符号匹配路线最小匹配数阈值（默认 5）
            library_blacklist: 库黑名单
            hint_first: 排序策略
                - False (默认): round_robin 轮询交替 (H1, S1, F1, H2, S2, F2...)
                - True: Hint 优先，剩余的 string/symbol 再 round_robin
            retrieval_top_n: 最终输出数量（合并排序后取前 N 个），None 表示不限制
            symbol_use_imported: 是否使用导入符号（默认 False，只使用导出符号）
        """
        # 路线开关
        self.enable_hint_recall = enable_hint_recall
        self.enable_string_recall = enable_string_recall
        self.enable_symbol_recall = enable_symbol_recall

        # 过滤配置
        self.hint_min_match_threshold = hint_min_match_threshold
        self.string_min_match_threshold = string_min_match_threshold if string_min_match_threshold is not None else DEFAULT_MIN_MATCH_COUNT_THRESHOLD
        self.symbol_min_match_threshold = symbol_min_match_threshold if symbol_min_match_threshold is not None else DEFAULT_MIN_MATCH_COUNT_THRESHOLD
        self.library_blacklist = library_blacklist if library_blacklist is not None else DEFAULT_LIBRARY_BLACKLIST

        # 排序策略
        self.hint_first = hint_first

        # 最终输出数量
        self.retrieval_top_n = retrieval_top_n

        # 符号匹配配置
        self.symbol_use_imported = symbol_use_imported

        # 初始化子匹配器
        self._string_matcher = None
        self._symbol_matcher = None

    # ==========================================================================
    # 第一级：主入口 - 三路召回 + 合并
    # ==========================================================================

    def recall(self, target_binary: TargetBinary) -> Tuple[List[LibraryHypothesis], Dict[str, float]]:
        """
        三路召回主入口

        流程：
        0. 预处理：统一过滤 strings/symbols（只做一次）
        1. 路线1: Hint - 收集库名，转换为 LibraryHypothesis（不过滤）
        2. 路线2: 字符串特征匹配（使用预过滤数据，1次查询，top_n*2）
        3. 路线3: 函数名特征匹配（使用预过滤数据，1次查询，top_n*2）
        4. 三路合并：Round-Robin (H → S → F)，达到 top_n 截止
        5. 补充缺失特征（2次批量查询，使用预过滤的特征）
        6. 最终过滤：移除无匹配的 Hint 候选

        Args:
            target_binary: 目标二进制文件对象

        Returns:
            Tuple[List[LibraryHypothesis], Dict[str, float]]:
                - 合并后的假设列表
                - 各阶段耗时
        """
        total_start = time.perf_counter()
        durations: Dict[str, float] = {}

        logger.info(f"Feature recall for: {target_binary.binary_name}")

        # Step 0: 预处理 - 统一过滤特征（只做一次，后续复用）
        start = time.perf_counter()
        filtered_strings = filter_strings(target_binary.strings or [])

        # 收集符号
        all_symbols = []
        if target_binary.exported_symbols:
            all_symbols.extend(target_binary.exported_symbols)
        if self.symbol_use_imported and target_binary.imported_symbols:
            all_symbols.extend(target_binary.imported_symbols)
        filtered_symbols = filter_symbols(all_symbols)

        durations["preprocess"] = time.perf_counter() - start
        logger.debug(f"Preprocessed: {len(filtered_strings)} strings, {len(filtered_symbols)} symbols")

        # Step 1: Hint 路线 - 收集库名，转换为 LibraryHypothesis（不做数量过滤）
        start = time.perf_counter()
        hint_results = []
        if self.enable_hint_recall:
            hint_results = self._recall_by_hint(target_binary)
            logger.debug(f"Hint recall: {len(hint_results)} results")
        durations["hint"] = time.perf_counter() - start

        # Step 2: 字符串特征匹配（使用预过滤数据）
        start = time.perf_counter()
        string_results = []
        if self.enable_string_recall:
            string_results = self._recall_by_string(target_binary, filtered_strings)
            logger.debug(f"String recall: {len(string_results)} results")
        durations["string"] = time.perf_counter() - start

        # Step 3: 函数名特征匹配（使用预过滤数据）
        start = time.perf_counter()
        symbol_results = []
        if self.enable_symbol_recall:
            symbol_results = self._recall_by_symbol(target_binary, filtered_symbols)
            logger.debug(f"Symbol recall: {len(symbol_results)} results")
        durations["symbol"] = time.perf_counter() - start

        # Step 4: 三路合并 - Round-Robin (H → S → F)，达到 top_n 截止
        start = time.perf_counter()
        merged_results = self._merge_results(hint_results, string_results, symbol_results)
        durations["merge"] = time.perf_counter() - start
        logger.debug(f"Merged: {len(merged_results)} candidates")

        # Step 5: 补充缺失特征（2次批量查询）
        start = time.perf_counter()
        self._supplement_features(merged_results, filtered_strings, filtered_symbols)
        durations["supplement"] = time.perf_counter() - start

        # Step 6: 最终过滤 - 移除无匹配的 Hint 候选
        start = time.perf_counter()
        final_results = self._filter_empty_hints(merged_results)
        durations["filter"] = time.perf_counter() - start

        durations["total"] = time.perf_counter() - total_start

        hint_count = sum(1 for h in final_results if h.source == "hint")
        logger.info(f"Feature recall complete: {len(final_results)} candidates "
                    f"(hint={hint_count}, string={len(string_results)}, symbol={len(symbol_results)})")

        return final_results, durations

    # ==========================================================================
    # 第二级：三条召回路线
    # ==========================================================================

    def _recall_by_hint(self, target_binary: TargetBinary) -> List[LibraryHypothesis]:
        """
        路线1: Hint - 收集库名，转换为 LibraryHypothesis

        不做数量过滤（Hint 数量一般很少），不查询特征匹配（延迟到补充阶段）。
        按发现顺序排列。

        Returns:
            List[LibraryHypothesis]: Hint 候选列表
        """
        # Step 1: 提取 hint names
        hint_names = self._extract_hint_names(target_binary)
        if not hint_names:
            return []

        # Step 2: 收集有效的库信息，转换为 LibraryHypothesis
        results = []
        for hint_name in hint_names:
            lib_info = get_library_info(hint_name.lower())
            if not lib_info:
                continue
            # 黑名单过滤
            if lib_info["name"].lower() in self.library_blacklist:
                continue

            # 创建 LibraryHypothesis（暂无特征匹配数据）
            hypothesis = LibraryHypothesis(
                library_name=lib_info["name"],
                library_id=lib_info["id"],
                method="feature_matching",
                source="hint",
                evidence=[],
                description="",
                integration_type="Static Linked"
            )
            hypothesis._string_count = 0
            hypothesis._symbol_count = 0
            hypothesis._string_evidence = []
            hypothesis._symbol_evidence = []
            results.append(hypothesis)

        return results

    def _recall_by_string(self, target_binary: TargetBinary,
                           filtered_strings: List[str]) -> List[LibraryHypothesis]:
        """
        路线2: 字符串特征匹配

        使用预过滤的字符串数据，委托给 StringFeatureMatcher
        """
        if self._string_matcher is None:
            self._string_matcher = StringFeatureMatcher(
                min_match_count_threshold=self.string_min_match_threshold,
                library_blacklist=self.library_blacklist
            )

        # 直接在数据库层限制返回数量
        query_top_n = self.retrieval_top_n * 2 if self.retrieval_top_n else None
        results = self._string_matcher.match(
            target_binary, top_n=query_top_n, filtered_features=filtered_strings
        )

        return results

    def _recall_by_symbol(self, target_binary: TargetBinary,
                          filtered_symbols: List[str]) -> List[LibraryHypothesis]:
        """
        路线3: 函数名特征匹配

        使用预过滤的符号数据，委托给 SymbolFeatureMatcher
        """
        if self._symbol_matcher is None:
            self._symbol_matcher = SymbolFeatureMatcher(
                min_match_count_threshold=self.symbol_min_match_threshold,
                library_blacklist=self.library_blacklist,
                use_imported_symbols=self.symbol_use_imported
            )

        # 直接在数据库层限制返回数量
        query_top_n = self.retrieval_top_n * 2 if self.retrieval_top_n else None
        results = self._symbol_matcher.match(
            target_binary, top_n=query_top_n, filtered_features=filtered_symbols
        )

        return results

    # ==========================================================================
    # 第三级：Hint 路线的步骤细节
    # ==========================================================================

    def _extract_hint_names(self, target_binary: TargetBinary) -> Set[str]:
        """Step 1: 提取 hint names（从文件名、字符串、函数名）"""
        all_symbols = []
        if target_binary.exported_symbols:
            all_symbols.extend(target_binary.exported_symbols)
        if target_binary.imported_symbols:
            all_symbols.extend(target_binary.imported_symbols)

        hint_names = find_hint_library_names(
            binary_name=target_binary.binary_name,
            strings=target_binary.strings,
            function_names=all_symbols
        )

        if hint_names:
            logger.debug(f"Extracted {len(hint_names)} hint names: {sorted(hint_names)[:5]}...")

        return hint_names

    # ==========================================================================
    # 合并逻辑
    # ==========================================================================

    def _merge_results(self,
                       hint_results: List[LibraryHypothesis],
                       string_results: List[LibraryHypothesis],
                       symbol_results: List[LibraryHypothesis]) -> List[LibraryHypothesis]:
        """
        合并三路结果

        逻辑：
        1. 每组内按 total_match_count 降序排序
        2. Round-Robin 轮询取候选，边轮询边合并
           - 顺序：H → S → F → H → S → F → ...
           - 如果当前候选已存在于合并列表，合并特征后继续从当前列表取下一个
        3. 轮询直到合并列表达到 retrieval_top_n 或所有列表取完
        4. 对 top_n 结果补充缺失的特征匹配数据
        """
        # Step 1: 预处理 - 按 total_match_count 排序
        hint_list = self._sort_hypotheses_by_match_count(hint_results)
        string_list = self._sort_hypotheses_by_match_count(string_results)
        symbol_list = self._sort_hypotheses_by_match_count(symbol_results)

        # Step 2: Round-Robin 边轮询边合并
        if self.hint_first:
            # Hint 优先：先取完全部 Hint，然后 S → Y → S → Y → ...
            merged_candidates = self._round_robin_with_merge_hint_first(
                hint_list, string_list, symbol_list
            )
        else:
            # 默认：H → S → Y → H → S → Y → ...
            merged_candidates = self._round_robin_with_merge(
                hint_list, string_list, symbol_list
            )

        # Step 3: 转换为 LibraryHypothesis
        return self._convert_to_hypotheses(merged_candidates)

    def _sort_hypotheses_by_match_count(self, hypotheses: List[LibraryHypothesis]) -> List[LibraryHypothesis]:
        """按 total_match_count 降序排序，数量相同时按覆盖率排序"""
        def sort_key(h: LibraryHypothesis):
            string_count = getattr(h, '_string_count', 0) or 0
            symbol_count = getattr(h, '_symbol_count', 0) or 0
            if string_count == 0 and symbol_count == 0:
                total_count = len(h.evidence)
            else:
                total_count = string_count + symbol_count
            # 覆盖率作为第二排序键
            coverage = getattr(h, '_coverage', 0) or 0
            return (-total_count, -coverage)

        return sorted(hypotheses, key=sort_key)

    def _round_robin_with_merge(self,
                                 hint_list: List[LibraryHypothesis],
                                 string_list: List[LibraryHypothesis],
                                 symbol_list: List[LibraryHypothesis]) -> List[MergedCandidate]:
        """
        Round-Robin 边轮询边合并

        轮询顺序：H → F → S → H → F → S → ...（函数名优先于字符串）
        如果当前候选已存在，合并特征后继续从当前列表取下一个
        """
        merged_dict: Dict[int, MergedCandidate] = {}  # library_id -> MergedCandidate
        merged_order: List[int] = []  # 记录加入顺序（library_id）

        # 三个列表的当前索引
        indices = {'hint': 0, 'string': 0, 'symbol': 0}
        lists = {'hint': hint_list, 'string': string_list, 'symbol': symbol_list}

        # 轮询顺序：hint > symbol(function) > string
        source_order = ['hint', 'symbol', 'string']
        source_idx = 0

        while True:
            # 检查是否达到 top_n
            if self.retrieval_top_n is not None and self.retrieval_top_n > 0:
                if len(merged_order) >= self.retrieval_top_n:
                    break

            # 检查是否所有列表都取完了
            all_exhausted = all(indices[s] >= len(lists[s]) for s in source_order)
            if all_exhausted:
                break

            # 当前要取的来源
            current_source = source_order[source_idx]
            current_list = lists[current_source]
            current_idx = indices[current_source]

            # 从当前列表取候选，直到取到一个新的（或列表取完）
            added_new = False
            while current_idx < len(current_list):
                h = current_list[current_idx]
                lib_id = h.library_id
                current_idx += 1
                indices[current_source] = current_idx

                if lib_id in merged_dict:
                    # 已存在，合并特征
                    self._merge_hypothesis_into_candidate(merged_dict[lib_id], h, current_source)
                    # 继续从当前列表取下一个
                else:
                    # 新候选，加入合并列表
                    candidate = self._create_candidate_from_hypothesis(h, current_source)
                    merged_dict[lib_id] = candidate
                    merged_order.append(lib_id)
                    added_new = True
                    break

            # 切换到下一个来源
            source_idx = (source_idx + 1) % len(source_order)

        # 按加入顺序返回
        return [merged_dict[lib_id] for lib_id in merged_order]

    def _round_robin_with_merge_hint_first(self,
                                            hint_list: List[LibraryHypothesis],
                                            string_list: List[LibraryHypothesis],
                                            symbol_list: List[LibraryHypothesis]) -> List[MergedCandidate]:
        """
        Hint 优先的 Round-Robin

        先取完全部 Hint，然后 S → Y → S → Y → ...
        """
        merged_dict: Dict[int, MergedCandidate] = {}
        merged_order: List[int] = []

        # Phase 1: 先取完全部 Hint
        for h in hint_list:
            if self.retrieval_top_n is not None and self.retrieval_top_n > 0:
                if len(merged_order) >= self.retrieval_top_n:
                    break

            lib_id = h.library_id
            if lib_id in merged_dict:
                self._merge_hypothesis_into_candidate(merged_dict[lib_id], h, 'hint')
            else:
                candidate = self._create_candidate_from_hypothesis(h, 'hint')
                merged_dict[lib_id] = candidate
                merged_order.append(lib_id)

        # Phase 2: F → S → F → S → ...（函数名优先于字符串）
        indices = {'string': 0, 'symbol': 0}
        lists = {'string': string_list, 'symbol': symbol_list}
        source_order = ['symbol', 'string']
        source_idx = 0

        while True:
            if self.retrieval_top_n is not None and self.retrieval_top_n > 0:
                if len(merged_order) >= self.retrieval_top_n:
                    break

            all_exhausted = all(indices[s] >= len(lists[s]) for s in source_order)
            if all_exhausted:
                break

            current_source = source_order[source_idx]
            current_list = lists[current_source]
            current_idx = indices[current_source]

            while current_idx < len(current_list):
                h = current_list[current_idx]
                lib_id = h.library_id
                current_idx += 1
                indices[current_source] = current_idx

                if lib_id in merged_dict:
                    self._merge_hypothesis_into_candidate(merged_dict[lib_id], h, current_source)
                else:
                    candidate = self._create_candidate_from_hypothesis(h, current_source)
                    merged_dict[lib_id] = candidate
                    merged_order.append(lib_id)
                    break

            source_idx = (source_idx + 1) % len(source_order)

        return [merged_dict[lib_id] for lib_id in merged_order]

    def _create_candidate_from_hypothesis(self, h: LibraryHypothesis, source: str) -> MergedCandidate:
        """从 LibraryHypothesis 创建 MergedCandidate"""
        candidate = MergedCandidate(
            library_id=h.library_id,
            library_name=h.library_name,
            description=h.description or ""
        )

        if source == 'hint':
            candidate.from_hint = True
            candidate.hint_evidence = h.evidence
            # Hint 已经有完整的 string/symbol 数据
            if hasattr(h, '_string_count'):
                candidate.string_match_count = h._string_count
                candidate.string_evidence = getattr(h, '_string_evidence', [])
            if hasattr(h, '_symbol_count'):
                candidate.symbol_match_count = h._symbol_count
                candidate.symbol_evidence = getattr(h, '_symbol_evidence', [])
        elif source == 'string':
            candidate.from_string = True
            candidate.string_match_count = len(h.evidence)
            candidate.string_evidence = h.evidence
        elif source == 'symbol':
            candidate.from_symbol = True
            candidate.symbol_match_count = len(h.evidence)
            candidate.symbol_evidence = h.evidence

        return candidate

    def _merge_hypothesis_into_candidate(self, candidate: MergedCandidate, h: LibraryHypothesis, source: str):
        """将 LibraryHypothesis 的数据合并到 MergedCandidate"""
        if source == 'hint':
            candidate.from_hint = True
            candidate.hint_evidence = h.evidence
            if hasattr(h, '_string_count') and h._string_count > candidate.string_match_count:
                candidate.string_match_count = h._string_count
                candidate.string_evidence = getattr(h, '_string_evidence', [])
            if hasattr(h, '_symbol_count') and h._symbol_count > candidate.symbol_match_count:
                candidate.symbol_match_count = h._symbol_count
                candidate.symbol_evidence = getattr(h, '_symbol_evidence', [])
        elif source == 'string':
            candidate.from_string = True
            if len(h.evidence) > candidate.string_match_count:
                candidate.string_match_count = len(h.evidence)
                candidate.string_evidence = h.evidence
        elif source == 'symbol':
            candidate.from_symbol = True
            if len(h.evidence) > candidate.symbol_match_count:
                candidate.symbol_match_count = len(h.evidence)
                candidate.symbol_evidence = h.evidence

    def _convert_to_hypotheses(self, candidates: List[MergedCandidate]) -> List[LibraryHypothesis]:
        """转换为 LibraryHypothesis 列表"""
        results = []
        for m in candidates:
            # 确定 source
            sources = []
            if m.from_hint:
                sources.append("hint")
            if m.from_string:
                sources.append("string")
            if m.from_symbol:
                sources.append("symbol")
            source = "+".join(sources)

            hypothesis = LibraryHypothesis(
                library_name=m.library_name,
                library_id=m.library_id,
                method="feature_matching",
                source=source,
                evidence=m.all_evidence,
                description=m.description,
                integration_type="Static Linked"
            )
            # 保存分项信息
            hypothesis._string_count = m.string_match_count
            hypothesis._symbol_count = m.symbol_match_count
            hypothesis._string_evidence = m.string_evidence
            hypothesis._symbol_evidence = m.symbol_evidence

            results.append(hypothesis)

        return results

    # ==========================================================================
    # 补充缺失特征
    # ==========================================================================

    def _supplement_features(self,
                              hypotheses: List[LibraryHypothesis],
                              filtered_strings: List[str],
                              filtered_symbols: List[str]) -> int:
        """
        补充缺失特征（使用预过滤的特征）

        对于每个候选：
        - 如果只有 symbol 匹配，补充 string 数据
        - 如果只有 string 匹配，补充 symbol 数据
        - 如果是 hint（无任何匹配），补充 string + symbol 数据

        使用 2 次批量查询，特征数据使用预过滤的结果。

        Args:
            hypotheses: 合并后的候选列表
            filtered_strings: 预过滤的字符串特征
            filtered_symbols: 预过滤的符号特征

        Returns:
            int: 补充的数量
        """
        if not hypotheses:
            return 0

        # Step 1: 收集需要查询的库
        need_string_libs = []
        need_symbol_libs = []

        for h in hypotheses:
            string_count = getattr(h, '_string_count', 0) or 0
            symbol_count = getattr(h, '_symbol_count', 0) or 0

            # 需要补充 string
            if symbol_count > 0 and string_count == 0:
                need_string_libs.append(h.library_name)
            # 需要补充 symbol
            if string_count > 0 and symbol_count == 0:
                need_symbol_libs.append(h.library_name)
            # Hint 没有任何匹配数据，两者都要补充
            if string_count == 0 and symbol_count == 0:
                need_string_libs.append(h.library_name)
                need_symbol_libs.append(h.library_name)

        # Step 2: 批量查询（共 2 次）
        string_results = {}
        if need_string_libs and filtered_strings:
            string_results = library_repository.list_libraries_by_strings_batch(
                strings=filtered_strings,
                library_names=list(set(need_string_libs)),
                min_match_num=1
            )

        symbol_results = {}
        if need_symbol_libs and filtered_symbols:
            symbol_results = library_repository.list_libraries_by_function_names_batch(
                function_names=filtered_symbols,
                library_names=list(set(need_symbol_libs)),
                min_match_num=1
            )

        # Step 3: 应用结果到候选
        supplement_count = 0
        for h in hypotheses:
            updated = False

            if h.library_name in string_results:
                string_data = string_results[h.library_name]
                matched = string_data.get("matched_strings", [])
                if matched:
                    h._string_count = len(matched)
                    h._string_evidence = matched
                    h.evidence = list(h.evidence) + matched if h.evidence else matched
                    updated = True

            if h.library_name in symbol_results:
                symbol_data = symbol_results[h.library_name]
                matched = symbol_data.get("matched_function_names", [])
                if matched:
                    h._symbol_count = len(matched)
                    h._symbol_evidence = matched
                    h.evidence = list(h.evidence) + matched if h.evidence else matched
                    updated = True

            if updated:
                supplement_count += 1

        if supplement_count > 0:
            logger.debug(f"Supplemented missing features for {supplement_count} candidates")

        return supplement_count

    def _filter_empty_hints(self, hypotheses: List[LibraryHypothesis]) -> List[LibraryHypothesis]:
        """
        过滤无匹配的 Hint 候选

        移除来源为 hint（且不是多来源合并的）但 total_match_count == 0 的候选。
        多来源合并的候选（如 hint+string）保留。

        Args:
            hypotheses: 候选列表

        Returns:
            List[LibraryHypothesis]: 过滤后的列表
        """
        if not hypotheses:
            return []

        filtered = []
        removed_count = 0

        for h in hypotheses:
            string_count = getattr(h, '_string_count', 0) or 0
            symbol_count = getattr(h, '_symbol_count', 0) or 0
            total_count = string_count + symbol_count

            # 如果是纯 hint 来源且无特征匹配，移除
            if h.source == "hint" and total_count == 0:
                removed_count += 1
                continue

            filtered.append(h)

        if removed_count > 0:
            logger.debug(f"Filtered {removed_count} empty hint candidates")

        return filtered
