"""
BLADE 检测工作流

三阶段流程：
1. Phase 1: 信息准备 (MaterialCollector)
   - 二进制解析 (BinaryInfoParser)
   - 特征匹配（字符串 + 符号）
2. Phase 2: LLM 一次性分析 (CompositionAnalyzer)
   - 主程序 + 动态库 + 静态库
3. Phase 3: 版本分析 (VersionAnalyzer)
"""

import os
import sys
import time
import traceback
from typing import List, Optional, Set
from loguru import logger

from ...config import settings
from ...interface import (Library, AnalysisData, AnalysisResult, AnalysisConfig,
                          TargetBinary, VersionAnalysisResult, PhaseRecord)
from ...databases.postgres.repository import library_repository
from .context_analysis import ContextAnalyzer
from .models import SoftwareContext

# 核心模块
from .binary_info_parser import BinaryInfoParser, calculate_file_sha256
from .composition_analysis import MaterialCollector, CompositionAnalyzer
from .tpl_version_identification import VersionAnalyzer
from .explanation_generator import ExplanationGenerator
from .exceptions import BladeError, WorkflowError, handle_analysis_error


class AnalysisPhase:
    """分析阶段常量（用于 phase_hook 回调）"""
    PARSING = "parsing"                      # 解析二进制
    FEATURE_MATCHING = "feature_matching"    # 特征匹配
    TPL_ANALYSIS = "tpl_analysis"            # TPL成分分析
    VERSION_ANALYSIS = "version_analysis"    # 版本识别
    GENERATING_EXPLANATION = "generating_explanation"  # 生成说明


# Logger 配置
_logger_configured = False

def configure_logger(silent: bool = False, debug_mode: bool = False):
    """
    配置日志级别

    Args:
        silent: 完全静默，只显示 WARNING 及以上
        debug_mode: 调试模式，显示 DEBUG 及以上
    """
    global _logger_configured
    logger.remove()

    if silent:
        # 静默模式：只显示警告和错误
        logger.add(sys.stdout, level="WARNING",
                   format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
                   colorize=True)
    elif debug_mode:
        # 调试模式：显示全部日志
        logger.add(sys.stdout, level="DEBUG",
                   format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
                   colorize=True)
    else:
        # 默认：显示 INFO 及以上
        logger.add(sys.stdout, level="INFO",
                   format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
                   colorize=True)

    _logger_configured = True


# 默认配置
configure_logger()


class DetectionWorkflow:
    """
    BLADE 检测工作流 / BLADE Detection Workflow

    三阶段流程 / Three-Phase Pipeline:
    Phase 1: 信息准备 (Material Collection) → Phase 2: LLM 候选验证 (Candidate Verification) → Phase 3: 版本分析 (Version Analysis)
    """

    def __init__(self,
                 # ==================== 特征召回配置 / Feature Recall Config ====================
                 retrieval_top_n: int = None,
                 # 最终输出数量（合并排序后取前 N 个），None 表示不限制
                 # Final output count (top N after merge and sort), None means no limit

                 hint_first: bool = False,
                 # 排序策略：False=Round-Robin，True=Hint优先
                 # Sorting strategy: False=Round-Robin, True=Hint first

                 library_blacklist: Set[str] = None,
                 # 库黑名单（系统库，不应作为检测结果）。None 时使用默认值：glibc, gcc, libstdc++ 等
                 # Library blacklist (system libraries that should not be reported). None uses defaults: glibc, gcc, libstdc++, etc.

                 min_match_count_threshold: int = None,
                 # 最小匹配数阈值，低于此数量的候选会被过滤。None 时使用默认值 5
                 # Minimum match count threshold, candidates below this will be filtered. None uses default value 5

                 # ==================== 召回路线开关 / Recall Route Switches ====================
                 enable_hint_recall: bool = True,
                 # 是否启用 Hint 召回路线
                 # Whether to enable hint recall route

                 enable_string_recall: bool = True,
                 # 是否启用字符串特征匹配路线
                 # Whether to enable string feature matching route

                 enable_symbol_recall: bool = True,
                 # 是否启用符号特征匹配路线
                 # Whether to enable symbol feature matching route

                 symbol_use_imported: bool = False,
                 # 符号匹配是否使用导入符号（默认 False，只使用导出符号）
                 # Whether symbol matching uses imported symbols (default False, only uses exported symbols)

                 # ==================== 核心功能开关 / Core Feature Switches ====================
                 use_agent: bool = True,
                 # 是否使用 LLM 进行候选验证。False 时仅返回特征匹配结果，不调用 LLM。
                 # Whether to use LLM for candidate verification. If False, only returns feature matching results without LLM calls.

                 enable_version_analysis: bool = True,
                 # 是否启用版本分析（Phase 3）。仅在 use_agent=True 时生效。
                 # Whether to enable version analysis (Phase 3). Only effective when use_agent=True.

                 enable_version_analysis_web_search: bool = False,
                 # 版本分析时是否启用联网搜索获取更多版本信息
                 # Whether to enable web search during version analysis to get more version information

                 enable_explanation_generation: bool = True,
                 # 是否启用说明生成（Phase 4）。仅在 use_agent=True 时生效。
                 # Whether to enable explanation generation (Phase 4). Only effective when use_agent=True.

                 # ==================== 日志配置 / Logging Config ====================
                 debug_mode: bool = False,
                 # 调试模式：输出 DEBUG 级别日志，启用 AGNO_DEBUG 环境变量
                 # Debug mode: outputs DEBUG level logs, enables AGNO_DEBUG environment variable

                 verbose: bool = False,
                 # 详细模式：输出每个阶段的详细进度信息
                 # Verbose mode: outputs detailed progress for each phase

                 silent: bool = False,
                 # 静默模式：只输出 WARNING 及以上级别日志
                 # Silent mode: only outputs WARNING level and above

                 # ==================== 回调配置 / Callback Config ====================
                 phase_hook=None,
                 # 阶段回调函数，用于外部监控进度。签名: phase_hook(phase: str, file_path: str)
                 # Phase callback function for external progress monitoring. Signature: phase_hook(phase: str, file_path: str)
                 # phase 可选值 / phase values: "parsing", "feature_matching", "tpl_analysis", "version_analysis"

                 # ==================== 验证阶段消融实验配置 / Verification Ablation Config ====================
                 ablation_all: bool = False,
                 # -All: 消融全部证据和CoT（纯LLM基线）
                 # -All: Ablate all evidence and CoT (pure LLM baseline)

                 ablation_no_s1: bool = False,
                 # -S1: 消融 Anchor Confirmation（去 Identity Markers + S1 prompt）
                 # -S1: Ablate Anchor Confirmation (remove Identity Markers + S1 prompt)

                 ablation_no_s2: bool = False,
                 # -S2: 消融 Dependency Filtering（去 Match Distribution + S2 prompt）
                 # -S2: Ablate Dependency Filtering (remove Match Distribution + S2 prompt)

                 ablation_no_s3: bool = False,
                 # -S3: 消融 Feature Attribution（去 Candidate Comparison + Library Metadata + S3 prompt + C3/C5）
                 # -S3: Ablate Feature Attribution (remove Candidate Comparison + Library Metadata + S3 prompt + C3/C5)

                 ablation_no_s4: bool = False,
                 # -S4: 消融 Evidence Quality Validation（去 S4 prompt + C4）
                 # -S4: Ablate Evidence Quality Validation (remove S4 prompt + C4 background)

                 ablation_no_cot: bool = False,
                 # -CoT: 消融全部CoT（保留全部证据，使用简化 prompt）
                 # -CoT: Ablate all CoT (keep all evidence, use simplified prompt)

                 # ==================== 验证模式配置 / Verification Mode Config ====================
                 allow_direct_discovery: bool = False,
                 # 是否允许报告候选之外的库（仅限 Identity Markers 中明确出现库名的情况）
                 # Whether to allow reporting libraries not in candidates (only when library name explicitly appears in Identity Markers)
                 #   - False (严格验证模式 / Strict Verification): 只报告候选中的库，用于论文实验
                 #     Only reports libraries in candidates, used for paper experiments
                 #   - True (允许额外发现 / Allow Direct Discovery): 允许报告 Identity Markers 明确揭示的库，用于实际使用
                 #     Allows reporting libraries explicitly revealed by Identity Markers, used for production
                 ):
        """
        初始化检测工作流 / Initialize detection workflow

        精简后的参数说明见上方注释 / See comments above for parameter descriptions
        """
        # ===== 保存配置 / Save configurations =====
        self.phase_hook = phase_hook
        self.verbose = verbose
        self.debug_mode = debug_mode
        self.use_agent = use_agent
        self.enable_version_analysis = enable_version_analysis
        self.enable_explanation_generation = enable_explanation_generation

        # 配置日志级别 / Configure log level
        configure_logger(silent=silent, debug_mode=debug_mode)

        # 注意：AGNO_DEBUG 会启用 agno 框架的 debug 输出（rich 渲染），会产生大量空行
        # 如需查看 agno debug 信息，取消下面的注释
        # if debug_mode:
        #     os.environ["AGNO_DEBUG"] = "true"

        # ===== 构建分析配置对象 / Build analysis config object =====
        self.analysis_config = AnalysisConfig(
            llm_provider=settings.LLM_PROVIDER,
            model_id=settings.LLM_MODEL_ID,
            feature_matching_return_top_n=retrieval_top_n or 0,  # 输出数量上限（0 表示无限制）
            use_agent=use_agent,
            debug_mode=debug_mode
        )

        # ===== 核心模块初始化 / Initialize core modules =====

        # 上下文环境分析器（可选）/ Context analyzer (optional)
        self.context_analyzer = ContextAnalyzer(enable_web_search=True)

        # Phase 1: 信息准备 / Material Collection
        self.binary_info_parser = BinaryInfoParser()

        self.material_collector = MaterialCollector(
            enable_feature_matching=True,
            enable_web_search=False,  # 暂不启用 / Not enabled for now
            # 过滤配置
            library_blacklist=library_blacklist,
            min_match_count_threshold=min_match_count_threshold,
            # 排序和输出配置
            hint_first=hint_first,
            retrieval_top_n=retrieval_top_n,
            # 召回路线开关
            enable_hint_recall=enable_hint_recall,
            enable_string_recall=enable_string_recall,
            enable_symbol_recall=enable_symbol_recall,
            # 符号匹配配置
            symbol_use_imported=symbol_use_imported,
        )

        # Phase 2: LLM 候选验证 / Candidate Verification
        self.composition_analyzer = CompositionAnalyzer(
            debug=debug_mode,
            ablation_all=ablation_all,
            ablation_no_s1=ablation_no_s1,
            ablation_no_s2=ablation_no_s2,
            ablation_no_s3=ablation_no_s3,
            ablation_no_s4=ablation_no_s4,
            ablation_no_cot=ablation_no_cot,
            allow_direct_discovery=allow_direct_discovery
        )

        # Phase 3: 版本分析 / Version Analysis
        if enable_version_analysis:
            self.version_analyzer = VersionAnalyzer(
                enable_web_search=enable_version_analysis_web_search
            )
        else:
            self.version_analyzer = None

        # Phase 4: 用户友好说明生成 / User-friendly explanation generation
        if enable_explanation_generation:
            self.explanation_generator = ExplanationGenerator()
        else:
            self.explanation_generator = None

        # 分析数据容器 / Analysis data container
        self.analysis_data = AnalysisData(config=self.analysis_config)

    def analyze_context(self, software_root_path: str) -> SoftwareContext:
        """分析软件上下文"""
        software_context, context_data = self.context_analyzer.analyze_software_context(software_root_path)
        return software_context

    def _notify_phase(self, phase: str, file_path: str):
        """通知阶段变化（通过 hook 回调）"""
        if self.phase_hook:
            try:
                self.phase_hook(phase, file_path)
            except Exception as e:
                logger.warning(f"Phase hook error: {e}")

    def run(self, file_path: str,
            software_context: SoftwareContext = None) -> AnalysisResult:
        """
        运行检测工作流

        三阶段流程：
        ┌─────────────────────────────────────────────────────────────────────┐
        │ Phase 1: 信息准备 (MaterialCollector)                               │
        │    - 二进制解析 → 特征匹配（字符串 + 符号）                           │
        │    → AnalysisMaterial                                               │
        └─────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
        ┌─────────────────────────────────────────────────────────────────────┐
        │ Phase 2: LLM 一次性分析 (CompositionAnalyzer)                        │
        │    → MainProgram + DynamicLibraries + StaticLibraries               │
        └─────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
        ┌─────────────────────────────────────────────────────────────────────┐
        │ Phase 3: 版本分析 (VersionAnalyzer)                                  │
        │    → 主程序版本 + 静态库版本                                         │
        └─────────────────────────────────────────────────────────────────────┘

        Args:
            file_path: 二进制文件路径
            software_context: 软件上下文（可选）

        Returns:
            AnalysisResult: 分析结果
        """
        all_start_at = time.perf_counter()
        self.analysis_data.context = software_context

        if self.verbose:
            logger.info('=== Starting Detection Workflow (3-Phase Architecture) ===')

        try:
            # ===== Phase 1: 信息准备 =====
            if self.verbose:
                logger.info(f'[+] Phase 1: Material Collection - {file_path}')
            phase1_start = time.perf_counter()
            phase1_start_time = time.strftime("%Y-%m-%d %H:%M:%S")

            # 1.1 二进制解析
            self._notify_phase(AnalysisPhase.PARSING, file_path)
            target_binary = self.binary_info_parser.parse(file_path)


            self.analysis_data.target_binary = target_binary

            # 1.2 收集分析素材（包括特征匹配）
            self._notify_phase(AnalysisPhase.FEATURE_MATCHING, file_path)
            material = self.material_collector.collect(target_binary)

            # 1.3 保存特征匹配候选到 AnalysisData（供评估器计算特征匹配效果）
            self.analysis_data.feature_match_candidates = material.feature_match_candidates

            phase1_duration = time.perf_counter() - phase1_start

            # 记录 Phase 1 详细信息
            self.analysis_data.tpl_analysis_phases["phase1_material_collection"] = PhaseRecord(
                start_time=phase1_start_time,
                duration=phase1_duration,
                llm_calls=[],  # Phase 1 无 LLM 调用
                output={
                    "feature_candidates_count": len(material.feature_match_candidates),
                    "exported_symbols_count": len(target_binary.exported_symbols) if target_binary.exported_symbols else 0,
                    "imported_symbols_count": len(target_binary.imported_symbols) if target_binary.imported_symbols else 0,
                    "strings_count": len(target_binary.strings) if target_binary.strings else 0,
                    "recall_durations": material.recall_durations,  # 召回路线耗时
                }
            )

            if self.verbose:
                logger.info(f'    Binary: {material.binary_name}')
                logger.info(f'    Copyrights: {len(material.copyright_notices)}, Versions: {len(material.version_strings)}')
                logger.info(f'    Feature candidates: {len(material.feature_match_candidates)}')
                logger.info(f'    Done. ({phase1_duration:.2f}s)')

            # ===== Phase 2: LLM 一次性分析 =====
            if self.use_agent:
                # 使用 LLM 分析
                if self.verbose:
                    logger.info('[+] Phase 2: Composition Analysis (Main + Dynamic + Static)')
                phase2_start = time.perf_counter()
                phase2_start_time = time.strftime("%Y-%m-%d %H:%M:%S")

                self._notify_phase(AnalysisPhase.TPL_ANALYSIS, file_path)
                main_program, dynamic_libs, static_libs, excluded_candidates, composition_costs = self.composition_analyzer.analyze(material)

                phase2_duration = time.perf_counter() - phase2_start

                # 记录 Phase 2 详细信息
                phase2_llm_calls = []
                if composition_costs:
                    phase2_llm_calls.append({
                        "input_tokens": composition_costs.get("input_tokens", 0),
                        "output_tokens": composition_costs.get("output_tokens", 0),
                        "total_tokens": composition_costs.get("total_tokens", 0),
                        "cache_read_tokens": composition_costs.get("cache_read_tokens", 0),
                        "reasoning_tokens": composition_costs.get("reasoning_tokens", 0),
                        "duration": composition_costs.get("duration", phase2_duration),
                    })
                self.analysis_data.tpl_analysis_phases["phase2_composition_analysis"] = PhaseRecord(
                    start_time=phase2_start_time,
                    duration=phase2_duration,
                    llm_calls=phase2_llm_calls,
                    output={
                        "main_program": main_program.name if main_program else None,
                        "static_libs_count": len(static_libs),
                        "dynamic_libs_count": len(dynamic_libs),
                    }
                )

                if self.verbose:
                    logger.info(f'    Main program: {main_program.name} ({main_program.binary_category})')
                    logger.info(f'    Dynamic libraries: {len(dynamic_libs)}')
                    logger.info(f'    Static libraries: {len(static_libs)}')
                    for lib in static_libs:
                        logger.info(f'      - {lib.name}')
                    logger.info(f'    Done. ({phase2_duration:.2f}s)')
            else:
                # 仅使用特征匹配结果，不调用 LLM
                if self.verbose:
                    logger.info('[+] Phase 2: Feature Matching Only (No LLM)')

                # 将特征匹配候选转换为检测结果
                main_program = Library(
                    name=material.binary_name,
                    component_name=None,
                    binary_category="unknown",
                )
                dynamic_libs = []
                static_libs = [
                    Library(
                        name=candidate.library_name,
                        component_name=None,
                        detection_method="feature_matching",
                        detection_sub_method=candidate.match_type,
                        component_type="static_linked",
                    )
                    for candidate in material.feature_match_candidates
                ]
                excluded_candidates = []  # 非 LLM 模式无排除候选
                if self.verbose:
                    logger.info(f'    Feature match candidates: {len(static_libs)}')
                    for i, lib in enumerate(static_libs[:10]):
                        candidate = material.feature_match_candidates[i]
                        logger.info(f'      - {lib.name} (matches={candidate.evidence_count})')
                    if len(static_libs) > 10:
                        logger.info(f'      ... and {len(static_libs) - 10} more')

            # ===== Phase 3: 版本分析 =====
            # 仅在使用 Agent 且启用版本分析时执行
            if self.use_agent and self.enable_version_analysis and self.version_analyzer:
                if self.verbose:
                    logger.info('[+] Phase 3: Version Analysis')
                phase3_start = time.perf_counter()
                phase3_start_time = time.strftime("%Y-%m-%d %H:%M:%S")

                self._notify_phase(AnalysisPhase.VERSION_ANALYSIS, file_path)
                version_results = self._analyze_versions(
                    file_path, target_binary, main_program, static_libs
                )
                self.analysis_data.version_analysis_results = version_results

                # 聚合版本分析的 LLM 成本
                phase3_llm_calls = []
                for vr in version_results:
                    if vr.llm_costs:
                        phase3_llm_calls.append({
                            "library": vr.library_name,
                            "input_tokens": vr.llm_costs.get("input_tokens", 0),
                            "output_tokens": vr.llm_costs.get("output_tokens", 0),
                            "total_tokens": vr.llm_costs.get("total_tokens", 0),
                            "cache_read_tokens": vr.llm_costs.get("cache_read_tokens", 0),
                            "reasoning_tokens": vr.llm_costs.get("reasoning_tokens", 0),
                            "duration": vr.llm_costs.get("duration", vr.analysis_duration),
                        })

                phase3_duration = time.perf_counter() - phase3_start

                # 记录 Phase 3 详细信息
                self.analysis_data.tpl_analysis_phases["phase3_version_analysis"] = PhaseRecord(
                    start_time=phase3_start_time,
                    duration=phase3_duration,
                    llm_calls=phase3_llm_calls,
                    output={
                        "analyzed_count": len(version_results),
                    }
                )

                if self.verbose:
                    logger.info(f'    Analyzed {len(version_results)} libraries')
                    for vr in version_results:
                        if vr.detected_versions:
                            versions_str = ", ".join(
                                f"{v.version}({v.confidence})" for v in vr.detected_versions[:2]
                            )
                            logger.info(f'      - {vr.library_name}: {versions_str}')
                        else:
                            logger.info(f'      - {vr.library_name}: unknown')
                    logger.info(f'    Done. ({phase3_duration:.2f}s)')

            # ===== Phase 4: 生成用户友好说明 =====
            # 仅在使用 Agent 且启用说明生成时执行
            if self.use_agent and self.enable_explanation_generation:
                if self.verbose:
                    logger.info('[+] Phase 4: Generating User Explanations')
                phase4_start = time.perf_counter()
                phase4_start_time = time.strftime("%Y-%m-%d %H:%M:%S")

                self._notify_phase(AnalysisPhase.GENERATING_EXPLANATION, file_path)
                # 收集所有需要生成说明的库
                all_libraries = [main_program] + dynamic_libs + static_libs
                explanation_costs = self.explanation_generator.generate_batch(all_libraries)

                phase4_duration = time.perf_counter() - phase4_start

                # 记录 Phase 4 详细信息
                phase4_llm_calls = []
                if explanation_costs:
                    for cost in explanation_costs:
                        phase4_llm_calls.append({
                            "library": cost.get("library", "unknown"),
                            "input_tokens": cost.get("input_tokens", 0),
                            "output_tokens": cost.get("output_tokens", 0),
                            "total_tokens": cost.get("total_tokens", 0),
                            "cache_read_tokens": cost.get("cache_read_tokens", 0),
                            "reasoning_tokens": cost.get("reasoning_tokens", 0),
                            "duration": cost.get("duration", 0),
                        })
                self.analysis_data.tpl_analysis_phases["phase4_explanation_generation"] = PhaseRecord(
                    start_time=phase4_start_time,
                    duration=phase4_duration,
                    llm_calls=phase4_llm_calls,
                    output={
                        "generated_count": len(all_libraries),
                    }
                )

                if self.verbose:
                    logger.info(f'    Generated explanations for {len(all_libraries)} libraries')
                    logger.info(f'    Done. ({phase4_duration:.2f}s)')

            # ===== 构建结果 =====
            total_duration = time.perf_counter() - all_start_at
            self.analysis_data.analysis_end_time = time.strftime("%Y-%m-%d %H:%M:%S")

            # ===== 计算汇总统计 =====
            self._calculate_summary(total_duration)

            # ===== 填充 giturl 信息 =====
            all_libs = ([main_program] if main_program else []) + static_libs + dynamic_libs
            self._enrich_libraries_with_giturl(all_libs, material.feature_match_candidates)

            # 过滤掉 null/unknown 结果
            def is_valid_library(lib: Library) -> bool:
                """检查库名是否有效（非 null/unknown）"""
                if not lib or not lib.name:
                    return False
                name_lower = lib.name.lower().strip()
                invalid_names = {'null', 'unknown', '{"null":null}', 'none', ''}
                return name_lower not in invalid_names

            # 过滤 main_program
            filtered_main_program = main_program if is_valid_library(main_program) else None

            # 过滤 static_libs
            filtered_static_libs = [lib for lib in static_libs if is_valid_library(lib)]

            result = AnalysisResult(
                binary_name=target_binary.binary_name,
                binary_sha256=target_binary.hash_sha256,
                binary_path=file_path,
                main_program=filtered_main_program,
                detected_libraries=filtered_static_libs,
                detected_dynamic_libraries=dynamic_libs,
                excluded_candidates=excluded_candidates,
                analysis_data=self.analysis_data
            )

            if self.verbose:
                logger.info('=== Detection Complete ===')
                logger.info(f'Total duration: {total_duration:.2f}s')
                logger.info(f'Main program: {main_program.name}')
                logger.info(f'Dynamic libraries: {len(dynamic_libs)}')
                logger.info(f'Static libraries: {len(static_libs)}')

            return result

        except Exception as e:
            # 统一异常处理
            error_info = handle_analysis_error("workflow", e, os.path.basename(file_path))

            # 检查是否是 Celery 超时异常（需要重新抛出）
            try:
                from celery.exceptions import SoftTimeLimitExceeded
                if isinstance(e, SoftTimeLimitExceeded):
                    logger.warning(f"Detection workflow timeout: {e}")
                    raise
            except ImportError:
                pass

            # 记录完整堆栈（仅对非 BladeError）
            if not isinstance(e, BladeError):
                logger.debug(traceback.format_exc())

            # 返回错误结果
            total_duration = time.perf_counter() - all_start_at
            self.analysis_data.analysis_end_time = time.strftime("%Y-%m-%d %H:%M:%S")
            self.analysis_data.error_message = str(e)
            self._calculate_summary(total_duration)

            return AnalysisResult(
                binary_name=os.path.basename(file_path),
                binary_sha256=calculate_file_sha256(file_path),
                binary_path=file_path,
                detected_libraries=[],
                excluded_candidates=[],
                analysis_data=self.analysis_data,
                succeed=False,
                error_message=str(e)
            )

    def _analyze_versions(self,
                          file_path: str,
                          target_binary: TargetBinary,
                          main_program: Library,
                          static_libs: List[Library]) -> List[VersionAnalysisResult]:
        """
        Phase 4: 版本分析

        使用批量分析接口，复用 Phase 1 提取的字符串

        Args:
            file_path: 二进制文件路径
            target_binary: 目标二进制对象
            main_program: 主程序
            static_libs: 静态库列表

        Returns:
            List[VersionAnalysisResult]: 版本分析结果列表
        """
        # 需要分析版本的库列表
        libraries_to_analyze = []

        # 1. 添加主程序（如果不是 unknown_program）
        if main_program and main_program.binary_category != "unknown_program":
            libraries_to_analyze.append(main_program)

        # 2. 添加静态库
        if static_libs:
            libraries_to_analyze.extend(static_libs)

        if not libraries_to_analyze:
            return []

        if self.verbose:
            lib_names = [lib.name for lib in libraries_to_analyze]
            logger.info(f"    Analyzing versions for: {lib_names}")

        # 3. 使用批量分析接口，复用 Phase 1 的字符串
        version_results = self.version_analyzer.analyze_batch(
            libraries=libraries_to_analyze,
            binary_strings=target_binary.strings,  # 复用 Phase 1 提取的字符串
            binary_name=target_binary.binary_name,
            path_hint=target_binary.relative_path
        )

        return version_results

    def _calculate_summary(self, total_duration: float):
        """
        计算汇总统计信息

        从各阶段的 PhaseRecord 中汇总：
        - 总时长
        - LLM 调用总次数
        - 输入/输出 token 总数
        - 总成本

        Args:
            total_duration: 总分析时长
        """
        total_llm_calls = 0
        total_input_tokens = 0
        total_output_tokens = 0
        total_cache_read_tokens = 0

        # 遍历所有阶段，汇总 LLM 调用信息
        for phase_name, phase_record in self.analysis_data.tpl_analysis_phases.items():
            if phase_record and phase_record.llm_calls:
                for call in phase_record.llm_calls:
                    total_llm_calls += 1
                    total_input_tokens += call.get("input_tokens", 0) or 0
                    total_output_tokens += call.get("output_tokens", 0) or 0
                    total_cache_read_tokens += call.get("cache_read_tokens", 0) or 0

        # 计算成本（基于配置中的单价）
        config = self.analysis_data.config
        input_price = config.input_token_price_per_1M if config else 0
        output_price = config.output_token_price_per_1M if config else 0
        cached_input_price = config.cached_input_token_price_per_1M if config else 0

        # 成本计算：未缓存输入 * 输入价格 + 缓存输入 * 缓存价格 + 输出 * 输出价格
        uncached_input_tokens = total_input_tokens - total_cache_read_tokens
        total_cost = (
            uncached_input_tokens * input_price / 1_000_000 +
            total_cache_read_tokens * cached_input_price / 1_000_000 +
            total_output_tokens * output_price / 1_000_000
        )

        # 保存汇总信息
        self.analysis_data.summary = {
            "total_duration": round(total_duration, 3),
            "total_llm_calls": total_llm_calls,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cache_read_tokens": total_cache_read_tokens,
            "total_cost": round(total_cost, 6),
        }

    def _enrich_libraries_with_giturl(self,
                                       libraries: List[Library],
                                       feature_match_candidates) -> None:
        """
        为检测到的库填充 giturl 信息

        通过特征匹配结果获取 library_id，然后从数据库查询 giturl

        Args:
            libraries: 需要填充 giturl 的库列表
            feature_match_candidates: 特征匹配候选结果
        """
        if not libraries or not feature_match_candidates:
            return

        # 建立名称到 library_id 的映射
        name_to_id = {}
        for candidate in feature_match_candidates:
            if candidate.library_id:
                name_lower = candidate.library_name.lower()
                name_to_id[name_lower] = candidate.library_id

        # 为每个库填充 giturl
        for lib in libraries:
            if not lib or not lib.name:
                continue

            name_lower = lib.name.lower()
            library_id = name_to_id.get(name_lower)

            if library_id:
                try:
                    db_library = library_repository.get_library_by_id(library_id)
                    if db_library:
                        lib.id = library_id
                        lib.giturl = db_library.giturl
                except Exception as e:
                    logger.debug(f"Failed to get giturl for library {lib.name}: {e}")
