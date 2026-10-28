"""
Version Analyzer
使用LLM分析二进制文件中的第三方库版本

重构说明：
- 支持批量分析多个库的版本（一次 LLM 调用）
- 复用 Phase 1 提取的字符串，避免重复提取
"""
import os
import time
from typing import List, Any, Optional, Dict

from agno.agent import Agent
from agno.tools.duckduckgo import DuckDuckGoTools
from loguru import logger

from app.interface import VersionAnalysisResult, Library
from ..models import LLMVersionAnalysisResult, VersionCandidate, create_model
from ..exceptions import VersionAnalysisError, handle_analysis_error
from .version_analyzer_prompt import VersionAnalyzerPrompt
from .utils import filter_reference_strings
from agno.db.in_memory import InMemoryDb


class BatchVersionResult:
    """批量版本分析结果"""
    def __init__(self):
        self.library_results: Dict[str, LLMVersionAnalysisResult] = {}
        self.reasoning: str = ""


class VersionAnalyzer:
    """Version analyzer for detecting library versions in binary files"""

    def __init__(self, enable_web_search: bool = False):
        """
        初始化版本分析器

        Args:
            enable_web_search: 是否启用网络搜索功能（默认关闭以提高速度）
        """
        # 配置常量（后续会移到统一配置）
        self.analysis_string_limit_per_library = 20
        self.max_libraries_per_batch = 10

        # 工具配置
        tools = []
        if enable_web_search:
            tools.append(DuckDuckGoTools())

        self.agent = Agent(
            model=create_model(),
            tools=tools,
            output_schema=LLMVersionAnalysisResult,
            instructions=VersionAnalyzerPrompt.SystemPrompt,
            db=InMemoryDb(),
            add_history_to_context=True
        )

    def analyze_batch(
        self,
        libraries: List[Library],
        binary_strings: List[str],
        binary_name: str,
        path_hint: str = None
    ) -> List[VersionAnalysisResult]:
        """
        批量分析多个库的版本（一次 LLM 调用）

        Args:
            libraries: 需要分析版本的库列表
            binary_strings: 从二进制文件提取的字符串（来自 Phase 1）
            binary_name: 二进制文件名
            path_hint: 路径提示（相对于软件根目录）

        Returns:
            List[VersionAnalysisResult]: 版本分析结果列表
        """
        if not libraries:
            return []

        start_at = time.perf_counter()
        results = []

        # 为每个库收集相关的版本字符串
        library_strings_map = {}
        for lib in libraries:
            reference_strings = filter_reference_strings(lib.name, binary_strings)
            library_strings_map[lib.name] = reference_strings

        # 如果所有库都没有找到相关字符串
        if all(not strings for strings in library_strings_map.values()):
            logger.warning("No version-related strings found for any library")
            for lib in libraries:
                results.append(VersionAnalysisResult(
                    file_path=path_hint or binary_name,
                    library_name=lib.name,
                    detected_versions=[],
                    reasoning="No version-related strings found in binary"
                ))
            return results

        # 分批处理（如果库太多）
        batches = self._split_into_batches(libraries)

        for batch in batches:
            batch_results = self._analyze_batch_internal(
                batch, library_strings_map, binary_name, path_hint
            )
            results.extend(batch_results)

        duration = time.perf_counter() - start_at
        logger.info(f"Batch version analysis completed: {len(libraries)} libraries in {duration:.2f}s")

        return results

    def _split_into_batches(self, libraries: List[Library]) -> List[List[Library]]:
        """将库列表分成多个批次"""
        batches = []
        for i in range(0, len(libraries), self.max_libraries_per_batch):
            batches.append(libraries[i:i + self.max_libraries_per_batch])
        return batches

    def _analyze_batch_internal(
        self,
        libraries: List[Library],
        library_strings_map: Dict[str, dict],
        binary_name: str,
        path_hint: str
    ) -> List[VersionAnalysisResult]:
        """内部批量分析方法"""
        results = []

        # 构建批量分析的 prompt
        prompt = self._build_batch_prompt(
            libraries, library_strings_map, binary_name, path_hint
        )

        # 逐个库调用 LLM（因为当前 output_schema 是单库的）
        # TODO: 未来可以改为真正的批量输出 schema
        for lib in libraries:
            lib_strings = library_strings_map.get(lib.name, {})

            if not lib_strings or all(not v for v in lib_strings.values()):
                results.append(VersionAnalysisResult(
                    file_path=path_hint or binary_name,
                    library_name=lib.name,
                    detected_versions=[],
                    reasoning="No version-related strings found for this library"
                ))
                continue

            try:
                llm_result, costs = self._analyze_single_library(
                    lib.name, lib_strings, binary_name, path_hint
                )

                result = VersionAnalysisResult(
                    file_path=path_hint or binary_name,
                    library_name=lib.name,
                    detected_versions=llm_result.versions,
                    reasoning=llm_result.reasoning,
                    llm_analysis_input=lib_strings,
                    llm_analysis_results=llm_result,
                    llm_costs=costs
                )
                results.append(result)

                # 更新 Library 对象
                if llm_result.versions:
                    lib.versions = llm_result.versions
                    lib.version_reasoning = llm_result.reasoning

            except Exception as e:
                handle_analysis_error("phase4_version", e, lib.name)
                results.append(VersionAnalysisResult(
                    file_path=path_hint or binary_name,
                    library_name=lib.name,
                    detected_versions=[],
                    reasoning=f"Analysis failed: {str(e)}"
                ))

        return results

    def _analyze_single_library(
        self,
        library_name: str,
        reference_strings: dict,
        binary_name: str,
        path_hint: str
    ) -> tuple[LLMVersionAnalysisResult, Any]:
        """分析单个库的版本"""
        # 收集要分析的字符串
        all_strings = set()

        # 如果是 .so 文件，添加文件名
        if ".so." in binary_name or binary_name.endswith(".so"):
            all_strings.add(binary_name)

        # 按优先级添加字符串
        for category in ["library_specific", "standard_versions", "generic_versions",
                         "path_log_versions", "other_versions"]:
            strings = reference_strings.get(category, [])
            for s in strings:
                all_strings.add(s)
                if len(all_strings) >= self.analysis_string_limit_per_library:
                    break
            if len(all_strings) >= self.analysis_string_limit_per_library:
                break

        all_strings = list(all_strings)

        # 构建 prompt
        user_prompt = f"""**Analysis Target**: Library '{library_name}' in binary: '{binary_name}'
"""
        if path_hint:
            user_prompt += f"""Binary Path (relative to software root): {path_hint}
"""
        user_prompt += f"""
**Available Strings**: {all_strings}

Analyze the version of '{library_name}' based on the evidence above.
Follow the 3-step framework and prioritize evidence reliability.
"""

        try:
            # 记录 LLM 调用时间
            llm_start = time.perf_counter()
            response = self.agent.run(user_prompt)
            llm_duration = time.perf_counter() - llm_start

            # 提取 LLM 成本信息（包含 duration）
            costs = response.metrics.to_dict() if hasattr(response, 'metrics') and response.metrics else {}
            costs["duration"] = llm_duration
            return response.content, costs
        except Exception as e:
            handle_analysis_error("phase4_llm", e, library_name)
            return LLMVersionAnalysisResult(
                versions=[],
                reasoning=f"LLM error: {str(e)}"
            ), None

    def _build_batch_prompt(
        self,
        libraries: List[Library],
        library_strings_map: Dict[str, dict],
        binary_name: str,
        path_hint: str
    ) -> str:
        """构建批量分析的 prompt（预留，当前未使用）"""
        prompt = f"**Binary**: {binary_name}\n"
        if path_hint:
            prompt += f"**Path**: {path_hint}\n"
        prompt += "\n**Libraries to analyze**:\n"

        for lib in libraries:
            strings = library_strings_map.get(lib.name, {})
            prompt += f"\n### {lib.name}\n"
            for category, items in strings.items():
                if items:
                    prompt += f"- {category}: {items[:5]}\n"

        return prompt

    # =========== 向后兼容的单库分析接口 ===========

    def analyze(
        self,
        binary_path: str,
        library_name: str,
        path_hint: str = None,
        binary_strings: List[str] = None
    ) -> VersionAnalysisResult:
        """
        分析单个库的版本（向后兼容接口）

        Args:
            binary_path: 二进制文件路径
            library_name: 库名称
            path_hint: 路径提示
            binary_strings: 预提取的字符串（如果提供则复用，否则重新提取）

        Returns:
            VersionAnalysisResult: 版本分析结果
        """
        start_at = time.perf_counter()

        if path_hint is None:
            path_hint = binary_path

        binary_name = os.path.basename(binary_path)

        # 如果没有提供字符串，需要提取（向后兼容）
        if binary_strings is None:
            logger.warning("No pre-extracted strings provided, extracting now (less efficient)")
            from .utils import extract_binary_strings
            binary_strings = extract_binary_strings(binary_path, tool='radare2')

        # 过滤版本相关字符串
        reference_strings = filter_reference_strings(library_name, binary_strings)

        if not reference_strings or all(not v for v in reference_strings.values()):
            logger.info(f"No version strings found for {library_name}")
            return VersionAnalysisResult(
                file_path=binary_path,
                library_name=library_name,
                detected_versions=[],
                reasoning="No version-related strings found"
            )

        # 分析
        llm_result, costs = self._analyze_single_library(
            library_name, reference_strings, binary_name, path_hint
        )

        duration = time.perf_counter() - start_at

        return VersionAnalysisResult(
            file_path=binary_path,
            library_name=library_name,
            detected_versions=llm_result.versions,
            reasoning=llm_result.reasoning,
            analysis_duration=duration,
            llm_analysis_input=reference_strings,
            llm_analysis_results=llm_result,
            llm_costs=costs
        )
