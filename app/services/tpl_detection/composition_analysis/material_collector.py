"""
Phase 1: 信息准备 - 素材收集器

收集所有分析素材：
1. 二进制基本信息（来自 BinaryInfoParser）
2. 特征匹配结果（来自知识库）
3. 联网搜索结果（可选）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from loguru import logger

from ....interface import TargetBinary, LibraryHypothesis, FeatureMatchCandidate, DirectoryNode
from ..exceptions import FeatureMatchingError, handle_analysis_error


@dataclass
class AnalysisMaterial:
    """
    分析素材 - Phase 1 的输出，供 LLM 分析使用

    职责边界说明：
    - TargetBinary: 原始解析结果，包含二进制文件的全部提取信息（全量数据）
    - AnalysisMaterial: LLM 分析视图，是 TargetBinary 的精选和格式化版本

    AnalysisMaterial 特点：
    1. 精选关键信息：只保留 LLM 分析需要的数据
    2. 分类整理：字符串按类型分类（版权、版本、URL等）
    3. 添加增强信息：特征匹配候选、符号前缀统计等
    4. 控制数据量：限制列表长度，避免 token 过多

    数据流：
    BinaryInfoParser → TargetBinary → MaterialCollector → AnalysisMaterial → LLM
    """
    # ===== 二进制基本信息 =====
    binary_name: str
    binary_path: str
    file_size_kb: float
    hash_sha256: str

    # ===== 动态库列表（明确的） =====
    dynamic_libraries: List[str] = field(default_factory=list)

    # ===== 符号信息 =====
    exported_symbols: List[str] = field(default_factory=list)
    imported_symbols: List[str] = field(default_factory=list)
    exported_symbol_prefixes: Dict[str, int] = field(default_factory=dict)  # prefix -> count

    # ===== 直接证据（版权、版本、URL、路径） =====
    copyright_notices: List[str] = field(default_factory=list)
    version_strings: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    source_paths: List[str] = field(default_factory=list)

    # ===== 间接证据 =====
    log_messages: List[str] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)

    # ===== 特征匹配候选（提示，需验证） =====
    feature_match_candidates: List[FeatureMatchCandidate] = field(default_factory=list)

    # ===== 联网搜索结果（可选） =====
    web_search_results: List[Dict[str, Any]] = field(default_factory=list)

    # ===== 召回路线耗时记录 =====
    recall_durations: Dict[str, float] = field(default_factory=dict)

    # ===== 原始 TargetBinary 引用 =====
    target_binary: Optional[TargetBinary] = None


class MaterialCollector:
    """
    素材收集器

    Phase 1: 收集所有分析素材
    """

    def __init__(self,
                 # ==================== 特征召回总开关 ====================
                 enable_feature_matching: bool = True,
                 enable_web_search: bool = False,

                 # ==================== 召回路线开关 ====================
                 enable_hint_recall: bool = True,
                 enable_string_recall: bool = True,
                 enable_symbol_recall: bool = True,

                 # ==================== 过滤配置 ====================
                 library_blacklist: Set[str] = None,
                 min_match_count_threshold: int = None,
                 hint_min_match_threshold: int = 1,

                 # ==================== 排序和输出配置 ====================
                 hint_first: bool = False,
                 retrieval_top_n: int = None,

                 # ==================== 符号匹配配置 ====================
                 symbol_use_imported: bool = False):
        """
        初始化素材收集器

        Args:
            enable_feature_matching: 特征匹配总开关
            enable_web_search: 是否启用联网搜索

            enable_hint_recall: 是否启用 Hint 召回路线
            enable_string_recall: 是否启用字符串特征匹配路线
            enable_symbol_recall: 是否启用符号特征匹配路线

            library_blacklist: 库黑名单（系统库，不应作为检测结果），为 None 时使用默认值
            min_match_count_threshold: 字符串/符号匹配最小匹配数阈值，为 None 时使用默认值 5
            hint_min_match_threshold: hint 路线最小匹配数阈值，默认 1

            hint_first: 排序策略
                - False (默认): round_robin 轮询交替 (H1, S1, Y1, H2, S2, Y2...)
                - True: Hint 优先，剩余的 string/symbol 再 round_robin
            retrieval_top_n: 最终输出数量（合并排序后取前 N 个），None 表示不限制
            symbol_use_imported: 是否使用导入符号（默认 False，只使用导出符号）
        """
        # 总开关
        self.enable_feature_matching = enable_feature_matching
        self.enable_web_search = enable_web_search

        # 召回路线开关
        self.enable_hint_recall = enable_hint_recall
        self.enable_string_recall = enable_string_recall
        self.enable_symbol_recall = enable_symbol_recall

        # 过滤配置
        self.library_blacklist = library_blacklist
        self.min_match_count_threshold = min_match_count_threshold
        self.hint_min_match_threshold = hint_min_match_threshold

        # 排序配置
        self.hint_first = hint_first
        self.retrieval_top_n = retrieval_top_n

        # 符号匹配配置
        self.symbol_use_imported = symbol_use_imported

        # 延迟初始化召回管理器
        self._recall_manager = None

    def collect(self, target_binary: TargetBinary) -> AnalysisMaterial:
        """
        收集分析素材

        Args:
            target_binary: 目标二进制文件对象（来自 BinaryInfoParser）

        Returns:
            AnalysisMaterial: 分析素材
        """
        logger.info("Phase 1: Collecting analysis material...")

        # 1. 提取基本信息
        material = self._extract_basic_info(target_binary)

        # 2. 提取符号信息
        self._extract_symbol_info(material, target_binary)

        # 3. 分类字符串证据
        self._classify_string_evidence(material, target_binary)

        # 4. 特征匹配（三路召回）
        if self.enable_feature_matching:
            self._run_feature_matching(material, target_binary)
            # 计算特征重叠
            self._calculate_feature_overlap(material)
            # 构建特征来源目录树
            self._build_source_trees(material)

        # 5. 联网搜索（可选）
        if self.enable_web_search:
            self._run_web_search(material, target_binary)

        # 保存原始引用
        material.target_binary = target_binary

        logger.info(f"Phase 1: Collected {len(material.copyright_notices)} copyrights, "
                    f"{len(material.version_strings)} versions, "
                    f"{len(material.feature_match_candidates)} feature candidates")

        return material

    def _extract_basic_info(self, target_binary: TargetBinary) -> AnalysisMaterial:
        """提取基本信息"""
        return AnalysisMaterial(
            binary_name=target_binary.binary_name,
            binary_path=target_binary.relative_path or target_binary.binary_name,
            file_size_kb=target_binary.file_size_kb,
            hash_sha256=target_binary.hash_sha256,
            dynamic_libraries=target_binary.dynamic_libraries or []
        )

    def _extract_symbol_info(self, material: AnalysisMaterial, target_binary: TargetBinary):
        """提取符号信息"""
        material.exported_symbols = target_binary.exported_symbols or []
        material.imported_symbols = target_binary.imported_symbols or []

        # 统计导出符号前缀
        prefix_count = {}
        for symbol in material.exported_symbols:
            parts = symbol.split('_')
            if len(parts) >= 2 and len(parts[0]) >= 2:
                prefix = parts[0]
                prefix_count[prefix] = prefix_count.get(prefix, 0) + 1

        # 只保留出现次数 >= 3 的前缀，按数量排序
        material.exported_symbol_prefixes = {
            k: v for k, v in sorted(prefix_count.items(), key=lambda x: x[1], reverse=True)
            if v >= 3
        }

    def _classify_string_evidence(self, material: AnalysisMaterial, target_binary: TargetBinary):
        """分类字符串证据"""
        # 1. 优先使用预分类的字符串
        if hasattr(target_binary, 'classified_strings') and target_binary.classified_strings:
            classified = target_binary.classified_strings

            material.copyright_notices = classified.get('copyright', [])
            material.version_strings = classified.get('version', [])
            material.urls = classified.get('url', [])
            material.source_paths = classified.get('path', [])

            # 日志和错误消息作为间接证据
            material.log_messages = classified.get('log', [])
            material.error_messages = classified.get('error', [])

        # 2. 如果预分类为空，从原始字符串中提取
        if not material.copyright_notices and not material.version_strings:
            self._extract_string_evidence(material, target_binary.strings or [])

    def _extract_string_evidence(self, material: AnalysisMaterial, strings: List[str]):
        """从原始字符串中提取证据"""
        import re

        # Copyright 模式
        copyright_pattern = re.compile(
            r'(?:copyright|©|\(c\)).*(?:\d{4})',
            re.IGNORECASE
        )

        # Version 模式 (包含库名的版本字符串)
        version_pattern = re.compile(
            r'(?:version|v\.?|ver\.?)\s*\d+\.\d+(?:\.\d+)?|'
            r'\b(?:openssl|zlib|libpng|curl|expat|sqlite)\s+\d+\.\d+(?:\.\d+)?|'
            r'(?:inflate|deflate)\s+\d+\.\d+(?:\.\d+)?',
            re.IGNORECASE
        )

        # URL 模式
        url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

        # Source path 模式
        path_pattern = re.compile(r'/(?:home|build|src|usr|opt)/[^\s:]+\.[ch](?:pp)?')

        copyrights = []
        versions = []
        urls = []
        paths = []

        for s in strings:
            if len(s) > 200:  # 跳过过长字符串
                continue

            if copyright_pattern.search(s):
                copyrights.append(s)
            if version_pattern.search(s):
                versions.append(s)
            if url_pattern.search(s):
                urls.append(s)
            if path_pattern.search(s):
                paths.append(s)

        # 去重并限制数量（强证据适当放宽限制）
        material.copyright_notices = list(set(copyrights))[:20]
        material.version_strings = list(set(versions))[:20]
        material.urls = list(set(urls))[:20]
        material.source_paths = list(set(paths))[:20]

    def _run_feature_matching(self, material: AnalysisMaterial, target_binary: TargetBinary):
        """
        运行特征匹配（三路召回）

        使用 FeatureRecallManager 统一管理：
        - 路线1: Hint 召回
        - 路线2: 字符串特征匹配
        - 路线3: 符号特征匹配
        """
        try:
            # 延迟初始化召回管理器
            if self._recall_manager is None:
                from ..feature_matching import FeatureRecallManager
                self._recall_manager = FeatureRecallManager(
                    # 路线开关
                    enable_hint_recall=self.enable_hint_recall,
                    enable_string_recall=self.enable_string_recall,
                    enable_symbol_recall=self.enable_symbol_recall,
                    # 过滤配置
                    hint_min_match_threshold=self.hint_min_match_threshold,
                    string_min_match_threshold=self.min_match_count_threshold,
                    symbol_min_match_threshold=self.min_match_count_threshold,
                    library_blacklist=self.library_blacklist,
                    # 排序和输出配置
                    hint_first=self.hint_first,
                    retrieval_top_n=self.retrieval_top_n,
                    # 符号匹配配置
                    symbol_use_imported=self.symbol_use_imported,
                )

            # 执行三路召回
            hypotheses, recall_durations = self._recall_manager.recall(target_binary)
            material.recall_durations = recall_durations

            # 转换为 FeatureMatchCandidate
            for h in hypotheses:
                # 确定 match_type
                if "string" in h.source and "symbol" in h.source:
                    match_type = "string+symbol"
                elif "symbol" in h.source:
                    match_type = "symbol_feature"
                else:
                    match_type = "string_feature"

                # 获取分项证据（各取最多10个例子）
                string_evidence = getattr(h, '_string_evidence', [])
                symbol_evidence = getattr(h, '_symbol_evidence', [])

                candidate = FeatureMatchCandidate(
                    library_name=h.library_name,
                    library_id=h.library_id,
                    match_type=match_type,
                    matched_evidence=string_evidence[:10] + symbol_evidence[:10],
                    evidence_count=len(string_evidence) + len(symbol_evidence),
                    # 保存分项数据
                    string_match_count=len(string_evidence),
                    symbol_match_count=len(symbol_evidence),
                )
                material.feature_match_candidates.append(candidate)

            logger.debug(f"Feature matching: {len(hypotheses)} candidates")

        except Exception as e:
            handle_analysis_error("phase1_feature_matching", e, target_binary.binary_name)

    def _run_web_search(self, material: AnalysisMaterial, target_binary: TargetBinary):
        """运行联网搜索（TODO）"""
        # 暂不实现
        pass

    def _calculate_feature_overlap(self, material: AnalysisMaterial):
        """
        计算特征匹配候选之间的重叠情况

        为每个候选计算：
        1. unique_count: 该候选独有的特征数量（不与其他任何候选重叠）
        2. overlap_info: 与其他候选的重叠情况 {库名: 重叠数量}

        注意：所有候选一起计算 overlap，不管 match_type。
        因为同一个特征可能在不同候选中以不同方式被匹配（string/symbol），
        但它们本质上是同一个特征，应该计入重叠。
        """
        if not material.feature_match_candidates:
            return

        candidates = material.feature_match_candidates

        if len(candidates) < 2:
            # 只有一个候选，所有特征都是独有的
            for c in candidates:
                c.unique_count = c.evidence_count
                sorted_unique = sorted(c.matched_evidence, key=lambda x: len(x), reverse=True)
                c.unique_examples = sorted_unique[:5]
            return

        # 构建每个候选的特征集合（所有候选一起，不分 match_type）
        feature_sets: Dict[str, set] = {}
        for c in candidates:
            feature_sets[c.library_name] = set(c.matched_evidence)

        # 计算所有特征的出现次数，用于计算独有特征
        all_features_count: Dict[str, int] = {}  # feature -> 出现在多少个候选中
        for lib_name, features in feature_sets.items():
            for f in features:
                all_features_count[f] = all_features_count.get(f, 0) + 1

        # 为每个候选计算重叠信息
        for c in candidates:
            my_features = feature_sets[c.library_name]

            # 计算独有特征数量（只出现在当前候选中的特征）
            unique_features = [f for f in my_features if all_features_count.get(f, 0) == 1]
            c.unique_count = len(unique_features)

            # 保存独有特征示例（按长度排序，优先选择较长的、更具辨识度的）
            sorted_unique = sorted(unique_features, key=lambda x: len(x), reverse=True)
            c.unique_examples = sorted_unique[:5]  # 最多保存5个示例

            # 计算与其他候选的重叠
            c.overlap_info = {}
            for other in candidates:
                if other.library_name == c.library_name:
                    continue
                other_features = feature_sets[other.library_name]
                overlap = my_features & other_features
                if overlap:
                    c.overlap_info[other.library_name] = len(overlap)

        logger.debug(f"Calculated feature overlap for {len(material.feature_match_candidates)} candidates")

    def _build_source_trees(self, material: AnalysisMaterial):
        """
        为每个特征匹配候选构建来源目录树

        查询数据库获取每个匹配特征的文件路径，然后构建两级目录树结构
        """
        from app.databases.postgres.repository import library_repository

        for candidate in material.feature_match_candidates:
            if not candidate.library_id or not candidate.matched_evidence:
                continue

            # 确定特征类型
            feature_type = "function_name" if "symbol" in candidate.match_type else "string"

            try:
                # 查询特征对应的文件路径
                feature_to_paths = library_repository.get_feature_file_paths_for_library(
                    library_id=candidate.library_id,
                    feature_names=candidate.matched_evidence,
                    feature_type=feature_type
                )

                if not feature_to_paths:
                    continue

                # 构建目录树
                candidate.source_tree = self._build_directory_tree(
                    feature_to_paths,
                    total_features=candidate.evidence_count
                )

            except Exception as e:
                logger.warning(f"Failed to build source tree for {candidate.library_name}: {e}")
                continue

        logger.debug(f"Built source trees for {len(material.feature_match_candidates)} candidates")

    def _build_directory_tree(
        self,
        feature_to_paths: Dict[str, List[str]],
        total_features: int
    ) -> Dict[str, DirectoryNode]:
        """
        根据特征-路径映射构建两级目录树

        Args:
            feature_to_paths: {特征名: [文件路径列表]}
            total_features: 总特征数（用于计算百分比）

        Returns:
            Dict[str, DirectoryNode]: {一级目录名: DirectoryNode}
        """
        # 统计每个目录的特征
        # 结构: {level1_dir: {level2_dir: {features: set, paths: set}}}
        dir_stats: Dict[str, Dict[str, Dict[str, set]]] = {}

        for feature, paths in feature_to_paths.items():
            for path in paths:
                # 解析路径，提取前两级目录（只要目录，不要文件）
                parts = path.strip('/').split('/')
                if not parts:
                    continue

                level1 = parts[0] if parts else "(root)"

                # 判断第二部分是目录还是文件
                # 如果路径有3+部分，说明 parts[1] 是目录
                # 如果只有2部分，parts[1] 是文件名，不作为二级目录
                level2 = None
                if len(parts) >= 3:
                    level2 = parts[1]

                # 初始化数据结构
                if level1 not in dir_stats:
                    dir_stats[level1] = {}

                if level2:
                    if level2 not in dir_stats[level1]:
                        dir_stats[level1][level2] = {"features": set(), "paths": set()}
                    dir_stats[level1][level2]["features"].add(feature)
                    dir_stats[level1][level2]["paths"].add(path)
                else:
                    # 没有二级目录（文件直接在一级目录下），放在特殊的 None key
                    if None not in dir_stats[level1]:
                        dir_stats[level1][None] = {"features": set(), "paths": set()}
                    dir_stats[level1][None]["features"].add(feature)
                    dir_stats[level1][None]["paths"].add(path)

        # 构建树形结构
        tree: Dict[str, DirectoryNode] = {}
        total = max(total_features, 1)  # 避免除零

        for level1, level2_dict in dir_stats.items():
            # 计算一级目录的总特征数（所有子目录的并集）
            all_features_in_level1: set = set()
            for level2_data in level2_dict.values():
                all_features_in_level1.update(level2_data["features"])

            level1_count = len(all_features_in_level1)
            level1_node = DirectoryNode(
                name=level1,
                count=level1_count,
                percentage=round(level1_count / total * 100, 1),
                examples=list(all_features_in_level1)[:3]  # 取前3个作为示例
            )

            # 构建二级目录
            for level2, level2_data in level2_dict.items():
                if level2 is None:
                    continue  # 跳过没有二级目录的情况

                level2_count = len(level2_data["features"])
                level2_node = DirectoryNode(
                    name=level2,
                    count=level2_count,
                    percentage=round(level2_count / total * 100, 1),
                    examples=list(level2_data["features"])[:3]
                )
                level1_node.children[level2] = level2_node

            tree[level1] = level1_node

        return tree
