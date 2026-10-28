"""
Composition Analyzer - 成分分析器

一次性分析：主程序 + 动态库 + 静态库
"""

import time
from typing import List, Tuple, Dict, Any, Optional
from loguru import logger

from agno.agent import Agent

from ....interface import Library, ExcludedCandidate as ExcludedCandidateResult
from ..models import create_model
from ..exceptions import handle_analysis_error
from .material_collector import AnalysisMaterial
from .response_models import TPLAnalysisResult, LibraryResult, ExcludedCandidate, SimpleAnalysisResult
from .prompts import TPLAnalyzerPrompt  # Old prompt (for reference)
from .new_prompt import TPLAnalyzerPromptV2  # New modular prompt
from .knowledge_base.lib_bin_mapping import lookup_library_by_binary


class CompositionAnalyzer:
    """
    成分分析器 - 一次性分析

    输入：AnalysisMaterial（二进制信息 + 特征匹配候选）
    输出：主程序 + 动态库 + 静态库
    """

    def __init__(self,
                 debug: bool = False,
                 # Prompt 显示限制参数
                 max_display_copyright: int = 10,
                 max_display_paths: int = 10,
                 max_display_function_prefixes: int = 10,
                 max_display_logs: int = 10,
                 max_display_versions: int = 5,
                 max_display_feature_candidates: int = 10,
                 max_matches_per_candidate: int = 5,
                 # 特征来源树配置
                 # Example 1: 详细模式 (depth=2, level1=8, level2=5, show_zero=True)
                 #   ├── ssl/           [320, 46%]  `SSL_CTX_new`, `SSL_connect`
                 #   │   ├── tls13/     [120, 17%]  `tls13_client_hello`
                 #   │   └── record/    [95, 14%]   `ssl_record_read`
                 #   ├── crypto/        [250, 36%]  `EVP_DigestInit`, `AES_encrypt`
                 #   └── apps/          [0, 0%]
                 #
                 # Example 2: 精简模式 (depth=1, level1=5, show_zero=False)
                 #   ├── ssl/           [320, 46%]  `SSL_CTX_new`, `SSL_connect`
                 #   ├── crypto/        [250, 36%]  `EVP_DigestInit`
                 #   └── include/       [122, 18%]  `OPENSSL_VERSION`
                 feature_source_max_depth: int = 2,
                 feature_source_max_level1_dirs: int = 8,
                 feature_source_max_level2_dirs: int = 5,
                 feature_source_show_zero_level1: bool = True,
                 feature_source_max_examples: int = 2,
                 # 验证阶段消融实验配置（6 个实验）
                 ablation_all: bool = False,       # -All: 消融全部证据和CoT（纯LLM基线）
                 ablation_no_s1: bool = False,     # -S1: 消融 Anchor Confirmation
                 ablation_no_s2: bool = False,     # -S2: 消融 Dependency Filtering
                 ablation_no_s3: bool = False,     # -S3: 消融 Feature Attribution
                 ablation_no_s4: bool = False,     # -S4: 消融 Evidence Quality Validation
                 ablation_no_cot: bool = False,    # -CoT: 消融全部CoT（保留证据）
                 # 额外发现配置
                 allow_direct_discovery: bool = False,
                 # Prompt 版本控制
                 use_v2_prompt: bool = True):       # 使用 V2 prompt（新结构）
        """
        初始化成分分析器

        Args:
            debug: 是否开启调试模式
            feature_source_max_depth: 目录树显示深度（1或2）
            feature_source_max_level1_dirs: 一级目录最多显示数量
            feature_source_max_level2_dirs: 每个一级目录下最多显示的二级目录数量
            feature_source_show_zero_level1: 一级目录是否显示0匹配的
            feature_source_max_examples: 每个目录显示的特征示例数量

            消融实验配置（用于论文）:
            - ablation_all: -All 消融 - 消融全部证据和CoT（纯LLM基线）
            - ablation_no_s1: -S1 消融 - 消融 Anchor Confirmation（去 Identity Markers + S1 prompt）
            - ablation_no_s2: -S2 消融 - 消融 Dependency Filtering（去 Match Distribution + S2 prompt + C2 背景）
            - ablation_no_s3: -S3 消融 - 消融 Feature Attribution（去 Candidate Comparison + Library Metadata + S3 prompt + C3/C5 背景）
            - ablation_no_s4: -S4 消融 - 消融 Evidence Quality Validation（去 S4 prompt + C4 背景）
            - ablation_no_cot: -CoT 消融 - 消融全部CoT（保留全部证据，使用简化 prompt）

            allow_direct_discovery: 是否允许报告候选之外的库（仅限 Identity Markers 明确出现库名的情况）
                                    论文实验: False（严格验证模式）
                                    实际使用: True（允许额外发现）
            use_v2_prompt: 使用 V2 prompt（新结构，支持 S4）
        """
        self.debug = debug
        self.max_display_copyright = max_display_copyright
        self.max_display_paths = max_display_paths
        self.max_display_function_prefixes = max_display_function_prefixes
        self.max_display_logs = max_display_logs
        self.max_display_versions = max_display_versions
        self.max_display_feature_candidates = max_display_feature_candidates
        self.max_matches_per_candidate = max_matches_per_candidate

        # 特征来源树配置
        self.feature_source_max_depth = feature_source_max_depth
        self.feature_source_max_level1_dirs = feature_source_max_level1_dirs
        self.feature_source_max_level2_dirs = feature_source_max_level2_dirs
        self.feature_source_show_zero_level1 = feature_source_show_zero_level1
        self.feature_source_max_examples = feature_source_max_examples

        # 消融实验配置
        self.ablation_all = ablation_all
        self.ablation_no_s1 = ablation_no_s1
        self.ablation_no_s2 = ablation_no_s2
        self.ablation_no_s3 = ablation_no_s3
        self.ablation_no_s4 = ablation_no_s4
        self.ablation_no_cot = ablation_no_cot
        self.allow_direct_discovery = allow_direct_discovery
        self.use_v2_prompt = use_v2_prompt

        # 根据消融模式选择 prompt 和 agent
        self.use_simple_mode = self.ablation_all or self.ablation_no_cot

        if self.use_simple_mode:
            # -All 或 -CoT：使用 SimplePrompt + SimpleAnalysisResult
            system_prompt = TPLAnalyzerPromptV2.SimplePrompt
            self.agent = Agent(
                model=create_model(),
                instructions=system_prompt,
                output_schema=SimpleAnalysisResult
            )
        else:
            # 完整模式
            if use_v2_prompt:
                # V2 prompt: 支持 S1-S4 消融
                include_s1 = not self.ablation_no_s1
                include_s2 = not self.ablation_no_s2
                include_s3 = not self.ablation_no_s3
                include_s4 = not self.ablation_no_s4
                system_prompt = TPLAnalyzerPromptV2.build_system_prompt(
                    include_s1=include_s1,
                    include_s2=include_s2,
                    include_s3=include_s3,
                    include_s4=include_s4,
                    allow_direct_discovery=allow_direct_discovery
                )
            else:
                # V1 prompt (fallback): 只支持 S1-S3 消融
                include_s1 = not self.ablation_no_s1
                include_s2 = not self.ablation_no_s2
                include_s3 = not self.ablation_no_s3
                system_prompt = TPLAnalyzerPrompt.build_system_prompt(
                    include_s1=include_s1,
                    include_s2=include_s2,
                    include_s3=include_s3,
                    allow_direct_discovery=allow_direct_discovery
                )

            self.agent = Agent(
                model=create_model(),
                instructions=system_prompt,
                output_schema=TPLAnalysisResult
            )

        # Debug: 打印 System Prompt
        if self.debug:
            logger.debug(f"System prompt (simple_mode={self.use_simple_mode}):\n{system_prompt}")

    def analyze(self, material: AnalysisMaterial) -> Tuple[Library, List[Library], List[Library], List[ExcludedCandidateResult], Optional[Dict[str, Any]]]:
        """
        一次性分析：主程序 + 动态库 + 静态库

        Args:
            material: 分析素材（来自 MaterialCollector）

        Returns:
            Tuple[Library, List[Library], List[Library], List[ExcludedCandidateResult], Optional[Dict]]:
                (主程序, 动态库列表, 静态库列表, 排除的候选列表, LLM成本)
        """
        logger.info("Composition Analysis: Identifying main program, dynamic and static libraries...")

        # 构建 prompt（参考旧版 build_task_input_prompt）
        prompt = self._build_prompt(material)

        if self.debug:
            logger.debug(f"Analysis prompt:\n{prompt}")

        try:
            # 记录 LLM 调用时间
            llm_start = time.perf_counter()
            response = self.agent.run(prompt)
            llm_duration = time.perf_counter() - llm_start

            # 提取 LLM 成本信息（包含 duration）
            llm_costs = response.metrics.to_dict() if hasattr(response, 'metrics') and response.metrics else {}
            llm_costs["duration"] = llm_duration

            # 根据模式处理结果
            if self.use_simple_mode:
                # 消融模式：简单判定结果转换
                main_program, dynamic_libs, static_libs, excluded = self._convert_simple_result(
                    response.content, material
                )
            else:
                # 完整模式：TPLAnalysisResult
                result: TPLAnalysisResult = response.content
                main_program = self._convert_library(result.main_program, "Main Program")
                dynamic_libs = [self._convert_library(lib, "Dynamic Linked") for lib in result.dynamic_dependencies]
                static_libs = [self._convert_library(lib, "Static Linked") for lib in result.static_dependencies]
                excluded = [
                    ExcludedCandidateResult(name=ec.name, fp_type=ec.fp_type, reasoning=ec.reasoning)
                    for ec in result.excluded_candidates
                ]

            logger.info(f"Analysis complete: main={main_program.name}, "
                        f"dynamic={len(dynamic_libs)}, static={len(static_libs)}, excluded={len(excluded)}")

            return main_program, dynamic_libs, static_libs, excluded, llm_costs

        except Exception as e:
            handle_analysis_error("composition_analysis", e, material.binary_name)
            # 重新抛出异常，让上层正确处理并记录为失败
            raise

    def _convert_simple_result(self, result, material: AnalysisMaterial) -> Tuple[Library, List[Library], List[Library], List[ExcludedCandidateResult]]:
        """
        将简单分析结果转换为标准格式（消融实验用）

        Args:
            result: SimpleAnalysisResult
            material: 分析素材

        Returns:
            (主程序, 动态库列表, 静态库列表, 排除的候选列表)
        """
        from .response_models import SimpleAnalysisResult

        simple_result: SimpleAnalysisResult = result

        # 去重：按名称保留第一个判定结果
        seen_names = set()
        deduplicated_results = []
        for r in simple_result.results:
            if r.name not in seen_names:
                seen_names.add(r.name)
                deduplicated_results.append(r)

        # 分离 true positives 和 false positives
        true_positives = [r for r in deduplicated_results if r.is_true_positive]
        false_positives = [r for r in deduplicated_results if not r.is_true_positive]

        # 构建候选名称到匹配数的映射
        candidate_match_counts = {
            c.library_name: c.evidence_count
            for c in material.feature_match_candidates
        }

        # 选择主程序：优先选择与二进制名称相似的，否则选匹配数最高的
        main_program = None
        static_libs = []
        added_lib_names = set()  # 用于去重

        if true_positives:
            # 尝试找与二进制名称匹配的
            binary_name_lower = material.binary_name.lower().replace('.so', '').replace('.a', '').replace('lib', '')
            # 移除版本号（如 .5.3）
            import re
            binary_name_lower = re.sub(r'\.\d+(\.\d+)*$', '', binary_name_lower)

            best_main = None
            best_match_count = 0

            for tp in true_positives:
                lib_name_lower = tp.name.lower().replace('-', '').replace('_', '')
                match_count = candidate_match_counts.get(tp.name, 0)

                # 优先选择名称匹配的
                if binary_name_lower in lib_name_lower or lib_name_lower in binary_name_lower:
                    if main_program is None or match_count > candidate_match_counts.get(main_program.name, 0):
                        main_program = Library(
                            name=tp.name,
                            binary_category="third_party_library",
                            library_integration_type="Main Program",
                            component_type="main_program",
                            detection_method="llm_analysis",
                            detection_sub_method="simple_judgment",
                            identify_reasoning=tp.reasoning,
                        )

                # 跟踪最高匹配数
                if match_count > best_match_count:
                    best_match_count = match_count
                    best_main = tp

            # 如果没有名称匹配的，选匹配数最高的
            if main_program is None and best_main:
                main_program = Library(
                    name=best_main.name,
                    binary_category="third_party_library",
                    library_integration_type="Main Program",
                    component_type="main_program",
                    detection_method="llm_analysis",
                    detection_sub_method="simple_judgment",
                    identify_reasoning=best_main.reasoning,
                )

            if main_program:
                added_lib_names.add(main_program.name)

            # 其余 true positives 作为静态依赖（去重）
            for tp in true_positives:
                if tp.name in added_lib_names:
                    continue
                added_lib_names.add(tp.name)
                static_libs.append(Library(
                    name=tp.name,
                    binary_category="third_party_library",
                    library_integration_type="Static Linked",
                    component_type="static_linked",
                    detection_method="llm_analysis",
                    detection_sub_method="simple_judgment",
                    identify_reasoning=tp.reasoning,
                ))

        # 如果没有 true positives，使用 unknown_program
        if main_program is None:
            main_program = Library(
                name="unknown_program",
                binary_category="unknown_program",
                library_integration_type="Main Program",
                component_type="main_program",
                detection_method="llm_analysis",
                detection_sub_method="simple_judgment",
                identify_reasoning="No candidates judged as true positive",
            )

        # 转换 false positives 为 excluded candidates（使用 LLM 返回的理由，去重）
        excluded = []
        excluded_names = set()
        for fp in false_positives:
            if fp.name not in excluded_names:
                excluded_names.add(fp.name)
                excluded.append(ExcludedCandidateResult(
                    name=fp.name,
                    fp_type="simple_rejection",
                    reasoning=fp.reasoning if fp.reasoning else "Judged as false positive"
                ))

        # 动态库保持为空（简单模式不分析动态库）
        dynamic_libs = []

        return main_program, dynamic_libs, static_libs, excluded

    def _build_prompt(self, material: AnalysisMaterial) -> str:
        """
        构建分析 prompt (User Prompt) - 按论文结构组织四种证据

        Evidence Type 1: Identity Markers (from binary) - S1 使用
        Evidence Type 2: Library Metadata (from knowledge base) - S3 使用
        Evidence Type 3: Match Distribution (per candidate) - S2 使用
        Evidence Type 4: Candidate Comparison (overlap analysis) - S3 使用

        消融配置（影响 User Prompt 中的证据）：
        - ablation_all: 去掉全部证据（纯 LLM 基线）
        - ablation_no_s1: 去掉 Evidence Type 1 (Identity Markers)
        - ablation_no_s2: 去掉 Evidence Type 3 (Match Distribution)
        - ablation_no_s3: 去掉 Evidence Type 2 + 4 (Library Metadata + Candidate Comparison)
        - ablation_no_s4: 不影响证据（S4 只在 System Prompt 中定义分析步骤）
        - ablation_no_cot: 不影响证据（CoT 只在 System Prompt 中定义）
        """
        # 计算哪些证据需要包含
        include_evidence_1 = not self.ablation_all and not self.ablation_no_s1  # Identity Markers
        include_evidence_2 = not self.ablation_all and not self.ablation_no_s3  # Library Metadata
        include_evidence_3 = not self.ablation_all and not self.ablation_no_s2  # Match Distribution
        include_evidence_4 = not self.ablation_all and not self.ablation_no_s3  # Candidate Comparison

        prompt = "# Verification Input\n\n"

        # === Target Binary Info ===
        prompt += "## Target Binary\n\n"
        if not self.ablation_all:
            prompt += f"- **Name**: `{material.binary_name}`\n"
            prompt += f"- **Path**: `{material.binary_path}`\n"
        prompt += f"- **Size**: {material.file_size_kb} KB\n"
        if material.dynamic_libraries:
            prompt += f"- **Dynamic Libraries**: {', '.join(material.dynamic_libraries)}\n"
        prompt += "\n"

        # === Evidence Type 1: Identity Markers (from binary) ===
        if include_evidence_1:
            prompt += "## Evidence Type 1: Identity Markers\n\n"
            prompt += "*Human-readable text from the binary that may reveal library identity.*\n\n"

            has_markers = False

            # Copyright/License (Explicit Markers)
            if material.copyright_notices:
                has_markers = True
                items = material.copyright_notices
                prompt += f"**Copyright/License** ({len(items)} items):\n"
                for item in items[:self.max_display_copyright]:
                    prompt += f"- {item}\n"
                if len(items) > self.max_display_copyright:
                    prompt += f"- *...and {len(items) - self.max_display_copyright} more*\n"
                prompt += "\n"

            # Version Strings (Explicit Markers)
            if material.version_strings:
                has_markers = True
                items = material.version_strings
                prompt += f"**Version Strings** ({len(items)} items):\n"
                for version in items[:self.max_display_versions]:
                    prompt += f"- {version}\n"
                if len(items) > self.max_display_versions:
                    prompt += f"- *...and {len(items) - self.max_display_versions} more*\n"
                prompt += "\n"

            # Paths/URLs (Explicit Markers)
            paths_urls = (material.urls or []) + (material.source_paths or [])
            if paths_urls:
                has_markers = True
                prompt += f"**Paths/URLs** ({len(paths_urls)} items):\n"
                for item in paths_urls[:self.max_display_paths]:
                    prompt += f"- {item}\n"
                if len(paths_urls) > self.max_display_paths:
                    prompt += f"- *...and {len(paths_urls) - self.max_display_paths} more*\n"
                prompt += "\n"

            # Symbol Patterns (Implicit Markers)
            if material.exported_symbol_prefixes:
                has_markers = True
                prompt += f"**Exported Symbol Patterns** ({len(material.exported_symbols)} total):\n"
                for prefix, count in list(material.exported_symbol_prefixes.items())[:self.max_display_function_prefixes]:
                    examples = [s for s in material.exported_symbols if s.startswith(prefix + "_")][:3]
                    examples_str = ", ".join(examples) if examples else ""
                    prompt += f"- `{prefix}_*`: {count} symbols"
                    if examples_str:
                        prompt += f" (e.g., {examples_str})"
                    prompt += "\n"
                prompt += "\n"

            # Imported Symbol Patterns (for context)
            if material.imported_symbols:
                import_prefix_count = {}
                for symbol in material.imported_symbols:
                    parts = symbol.split('_')
                    if len(parts) >= 2 and len(parts[0]) >= 2:
                        prefix = parts[0]
                        import_prefix_count[prefix] = import_prefix_count.get(prefix, 0) + 1
                significant_prefixes = {k: v for k, v in import_prefix_count.items() if v >= 3}
                if significant_prefixes:
                    has_markers = True
                    prompt += f"**Imported Symbol Patterns** ({len(material.imported_symbols)} total):\n"
                    for prefix, count in sorted(significant_prefixes.items(), key=lambda x: x[1], reverse=True)[:5]:
                        examples = [s for s in material.imported_symbols if s.startswith(prefix + "_")][:3]
                        examples_str = ", ".join(examples) if examples else ""
                        prompt += f"- `{prefix}_*`: {count} symbols"
                        if examples_str:
                            prompt += f" (e.g., {examples_str})"
                        prompt += "\n"
                    prompt += "\n"

            # Log/Error Messages
            log_messages = (material.log_messages or []) + (material.error_messages or [])
            if log_messages:
                has_markers = True
                prompt += f"**Log/Error Messages** ({len(log_messages)} items):\n"
                for msg in log_messages[:self.max_display_logs]:
                    prompt += f"- {msg}\n"
                if len(log_messages) > self.max_display_logs:
                    prompt += f"- *...and {len(log_messages) - self.max_display_logs} more*\n"
                prompt += "\n"

            if not has_markers:
                prompt += "*No identity markers found in the binary.*\n\n"

        # === Evidence Type 2: Library Metadata (from knowledge base) ===
        if include_evidence_2:
            library_names = lookup_library_by_binary(material.binary_name)
            if library_names:
                prompt += "## Evidence Type 2: Library Metadata\n\n"
                prompt += "*Pre-collected information from our knowledge base.*\n\n"

                if len(library_names) == 1:
                    lib_name = library_names[0]
                    prompt += f"**Binary-Library Hint**: The binary name `{material.binary_name}` "
                    prompt += f"is commonly associated with the `{lib_name}` project.\n\n"
                else:
                    libs_str = ", ".join([f"`{name}`" for name in library_names])
                    prompt += f"**Binary-Library Hint**: The binary name `{material.binary_name}` "
                    prompt += f"could be associated with: {libs_str}.\n\n"

                prompt += "*Note: This is a hint. Verify with other evidence.*\n\n"

        # === Evidence Type 3 & 4: Candidates with Match Distribution and Comparison ===
        if material.feature_match_candidates:
            prompt += "## Candidates from Feature Matching\n\n"
            prompt += "*Libraries matched via string/symbol features. Verify each candidate using the evidence.*\n\n"

            # 按证据数量排序
            sorted_candidates = sorted(
                material.feature_match_candidates,
                key=lambda x: x.evidence_count,
                reverse=True
            )

            for idx, candidate in enumerate(sorted_candidates[:self.max_display_feature_candidates], 1):
                prompt += f"### Candidate {idx}: {candidate.library_name}\n\n"

                # 消融模式（ablation_all）：根据 match_type 分开显示
                if self.ablation_all:
                    if candidate.match_type == "string_feature":
                        # 纯字符串匹配
                        prompt += f"- **String Matches**: {candidate.evidence_count}"
                        if candidate.matched_evidence:
                            examples = candidate.matched_evidence[:3]
                            prompt += f" (e.g., {', '.join(f'`{s}`' for s in examples)})"
                        prompt += "\n"
                    elif candidate.match_type == "symbol_feature":
                        # 纯符号匹配
                        prompt += f"- **Symbol Matches**: {candidate.evidence_count}"
                        if candidate.matched_evidence:
                            examples = candidate.matched_evidence[:3]
                            prompt += f" (e.g., {', '.join(f'`{s}`' for s in examples)})"
                        prompt += "\n"
                    else:
                        # string+symbol 混合：字符串在前（最多10个），符号在后（最多10个）
                        str_count_in_evidence = min(10, candidate.string_match_count)
                        if candidate.string_match_count > 0:
                            prompt += f"- **String Matches**: {candidate.string_match_count}"
                            str_examples = candidate.matched_evidence[:3]
                            if str_examples:
                                prompt += f" (e.g., {', '.join(f'`{s}`' for s in str_examples)})"
                            prompt += "\n"
                        if candidate.symbol_match_count > 0:
                            prompt += f"- **Symbol Matches**: {candidate.symbol_match_count}"
                            sym_examples = candidate.matched_evidence[str_count_in_evidence:str_count_in_evidence + 3]
                            if sym_examples:
                                prompt += f" (e.g., {', '.join(f'`{s}`' for s in sym_examples)})"
                            prompt += "\n"
                else:
                    # 完整模式：显示更多信息
                    prompt += f"- **Match Type**: {candidate.match_type}\n"
                    prompt += f"- **Total Matches**: {candidate.evidence_count}\n"
                    # Unique Matches 属于 Candidate Comparison (Evidence Type 4)，仅在 include_evidence_4 时显示
                    if include_evidence_4:
                        prompt += f"- **Unique Matches**: {candidate.unique_count} ({round(candidate.unique_count / max(candidate.evidence_count, 1) * 100)}%)\n"

                    # Evidence Type 3: Match Distribution (S2 使用)
                    if include_evidence_3:
                        if candidate.source_tree:
                            prompt += "\n**Match Distribution** (Evidence Type 3):\n"
                            prompt += "```\n"
                            prompt += self._build_source_tree_display(candidate.source_tree)
                            prompt += "```\n"
                        elif candidate.matched_evidence:
                            sample_size = min(self.max_matches_per_candidate, len(candidate.matched_evidence))
                            samples = candidate.matched_evidence[:sample_size]
                            prompt += f"\n**Example Matches**: {', '.join(f'`{s}`' for s in samples)}\n"

                    # Evidence Type 4: Overlap Info (inline) (S3 使用)
                    if include_evidence_4 and candidate.overlap_info:
                        sorted_overlaps = sorted(candidate.overlap_info.items(), key=lambda x: x[1], reverse=True)
                        overlap_str = ", ".join(f"{lib}({count})" for lib, count in sorted_overlaps[:5])
                        prompt += f"\n**Overlaps With**: {overlap_str}\n"

                    # Unique Examples (S3 使用)
                    if include_evidence_4 and candidate.unique_examples:
                        unique_str = ", ".join(f"`{e}`" for e in candidate.unique_examples[:3])
                        prompt += f"**Unique Features**: {unique_str}\n"

                prompt += "\n"

            if len(sorted_candidates) > self.max_display_feature_candidates:
                prompt += f"*...and {len(sorted_candidates) - self.max_display_feature_candidates} more candidates*\n\n"

            # === Evidence Type 4: Candidate Comparison Summary (S3 使用) ===
            if include_evidence_4:
                prompt += self._build_overlap_matrix(sorted_candidates[:self.max_display_feature_candidates])

        return prompt

    def _build_source_tree_display(self, source_tree: dict) -> str:
        """
        构建特征来源目录树的显示字符串

        Args:
            source_tree: {目录名: DirectoryNode} 字典

        Returns:
            格式化的树形字符串
        """
        if not source_tree:
            return ""

        result = ""

        # 按匹配数量排序一级目录
        sorted_level1 = sorted(
            source_tree.items(),
            key=lambda x: x[1].count,
            reverse=True
        )

        # 根据配置决定是否显示0匹配的目录
        if not self.feature_source_show_zero_level1:
            sorted_level1 = [(name, node) for name, node in sorted_level1 if node.count > 0]

        # 限制一级目录数量
        display_level1 = sorted_level1[:self.feature_source_max_level1_dirs]
        remaining_level1 = len(sorted_level1) - len(display_level1)

        for i, (dir_name, node) in enumerate(display_level1):
            is_last_level1 = (i == len(display_level1) - 1) and remaining_level1 == 0

            # 一级目录前缀
            prefix = "└── " if is_last_level1 else "├── "

            # 构建示例字符串
            examples_str = ""
            if node.examples and self.feature_source_max_examples > 0:
                examples = node.examples[:self.feature_source_max_examples]
                examples_str = "  " + ", ".join(f"`{e}`" for e in examples)

            result += f"  {prefix}{dir_name}/ [{node.count}, {node.percentage}%]{examples_str}\n"

            # 二级目录（如果配置深度 >= 2 且有子目录）
            if self.feature_source_max_depth >= 2 and node.children:
                # 判断是否需要展开二级目录：至少有一个子目录有匹配
                has_any_match = any(child.count > 0 for child in node.children.values())

                if has_any_match:
                    # 按匹配数量排序二级目录
                    sorted_level2 = sorted(
                        node.children.items(),
                        key=lambda x: x[1].count,
                        reverse=True
                    )[:self.feature_source_max_level2_dirs]

                    for j, (child_name, child_node) in enumerate(sorted_level2):
                        is_last_level2 = (j == len(sorted_level2) - 1)

                        # 二级目录前缀（考虑一级目录的连接线）
                        level1_connector = "    " if is_last_level1 else "│   "
                        level2_prefix = "└── " if is_last_level2 else "├── "

                        # 构建示例字符串
                        child_examples_str = ""
                        if child_node.examples and self.feature_source_max_examples > 0:
                            child_examples = child_node.examples[:self.feature_source_max_examples]
                            child_examples_str = "  " + ", ".join(f"`{e}`" for e in child_examples)

                        result += f"  {level1_connector}{level2_prefix}{child_name}/ [{child_node.count}, {child_node.percentage}%]{child_examples_str}\n"

        if remaining_level1 > 0:
            result += f"  (*{remaining_level1} more directories*)\n"

        return result

    def _build_overlap_matrix(self, candidates: list) -> str:
        """
        构建特征重叠矩阵，帮助 LLM 理解候选库之间的特征共享情况

        Args:
            candidates: 排序后的候选列表

        Returns:
            格式化的重叠矩阵字符串
        """
        if len(candidates) < 2:
            return ""

        # 按 match_type 分组
        by_type = {}
        for c in candidates:
            if c.match_type not in by_type:
                by_type[c.match_type] = []
            by_type[c.match_type].append(c)

        result = "### Feature Overlap Analysis\n\n"
        result += "**Important:** Libraries with high overlap but few unique features may be false positives.\n"
        result += "A library with many matches but 0 unique features likely shares generic features with the true library.\n\n"

        for match_type, type_candidates in by_type.items():
            if len(type_candidates) < 2:
                continue

            result += f"**{match_type} Overlap:**\n\n"
            result += "| Library | Total | Unique | Unique% | Unique Examples | Overlaps With |\n"
            result += "|---------|-------|--------|---------|-----------------|---------------|\n"

            for c in type_candidates:
                # 计算 Unique%
                unique_pct = round(c.unique_count / c.evidence_count * 100) if c.evidence_count > 0 else 0

                # 构建独有特征示例
                if c.unique_examples:
                    unique_examples_str = ", ".join(f"`{e}`" for e in c.unique_examples[:3])
                    if len(c.unique_examples) > 3:
                        unique_examples_str += " ..."
                else:
                    unique_examples_str = "-"

                # 构建重叠描述（显示全部，不省略）
                if c.overlap_info:
                    # 按重叠数量排序
                    sorted_overlaps = sorted(c.overlap_info.items(), key=lambda x: x[1], reverse=True)
                    overlap_desc = ", ".join(f"{lib}({count})" for lib, count in sorted_overlaps)
                else:
                    overlap_desc = "none"

                result += f"| {c.library_name} | {c.evidence_count} | {c.unique_count} | {unique_pct}% | {unique_examples_str} | {overlap_desc} |\n"

            result += "\n"

        return result

    def _convert_library(self, result: LibraryResult, integration_type: str) -> Library:
        """将 LibraryResult 转换为 Library"""
        return Library(
            name=result.name,
            component_name=result.component_name,
            binary_category=result.category,
            library_integration_type=integration_type,
            description=result.description,
            evidences=result.evidences,
            detection_type="direct_recognition" if result.evidences else "association",
            identify_reasoning=result.reasoning,
            detection_sources=["composition_analysis"],
            # 规范化字段
            component_type=self._get_component_type(integration_type),
            detection_method="llm_analysis",
            detection_sub_method="direct_recognition" if result.evidences else "heuristic_association",
            validation_stage=""
        )

    def _get_component_type(self, integration_type: str) -> str:
        """获取组件类型"""
        mapping = {
            "Main Program": "main_program",
            "Dynamic Linked": "dynamic_linked",
            "Static Linked": "static_linked"
        }
        return mapping.get(integration_type, "unknown")

    def _create_unknown_main_program(self, material: AnalysisMaterial) -> Library:
        """创建未知主程序结果"""
        return Library(
            name=material.binary_name,
            binary_category="unknown_program",
            library_integration_type="Main Program",
            description="Failed to identify main program",
            evidences=[],
            detection_type="association",
            identify_reasoning="Analysis failed",
            detection_sources=["composition_analysis"],
            component_type="main_program",
            detection_method="llm_analysis",
            detection_sub_method="heuristic_association",
            validation_stage=""
        )
