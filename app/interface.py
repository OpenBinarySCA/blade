import dataclasses
import traceback
from dataclasses import fields, dataclass, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Type, Any, Optional, List
from loguru import logger
from pydantic import BaseModel, Field

from .services.tpl_detection.models import BinaryInformation, SoftwareContext, VersionCandidate
from .config import settings


# =========================== Hypothesis Generation Models ===========================
@dataclass
class ReadableClues:
    """
    可读线索 - 预处理后的分类结果
    Readable clues - preprocessed classification results

    由 CluePreprocessor 生成，供 ClueAnalyzer (LLM) 分析使用
    """
    # 版权声明
    copyright_notices: List[str] = dataclasses.field(default_factory=list)
    # 源码路径/URL
    source_paths: List[str] = dataclasses.field(default_factory=list)
    # 版本字符串
    version_strings: List[str] = dataclasses.field(default_factory=list)
    # 函数前缀统计
    function_prefixes: List[str] = dataclasses.field(default_factory=list)
    # 日志消息
    log_messages: List[str] = dataclasses.field(default_factory=list)
    # 已知库名匹配结果 {library_name: [matched_strings]}
    component_matches: Dict[str, List[str]] = dataclasses.field(default_factory=dict)


@dataclass
class LibraryHypothesis:
    """
    库假设 - 假设生成阶段的输出
    Library hypothesis - output of hypothesis generation phase

    三种识别方法都输出此结构:
    1. feature_matching (string_feature, symbol_feature)
    2. external_search (github)
    3. clue_analysis (llm)
    """
    # 基本信息
    library_name: str  # 库名称
    library_id: int = None  # 数据库中的库ID (如果有)

    # 识别方法和来源
    method: str = ""  # "feature_matching" | "external_search" | "clue_analysis"
    source: str = ""  # "string_feature" | "symbol_feature" | "github" | "llm"

    # 置信度和证据
    confidence: float = 0.0  # 置信度 (0-1)
    evidence: List[str] = dataclasses.field(default_factory=list)  # 支持该假设的证据

    # 验证状态
    needs_verification: bool = True  # 是否需要进一步验证

    # 描述信息
    description: str = ""

    # 额外信息 (可选，来自 LLM 分析)
    component_name: str = None  # 组件名
    category: str = None  # "android_platform" | "third_party_library" | "linux_kernel" | "system_library" | "unknown_program"
    integration_type: str = None  # "Main Program" | "Static Linked" | "Dynamic Linked"
    reasoning: str = None  # LLM 推理过程


@dataclass
class Serializable:

    def customer_serialize(self) -> Dict[str, Any]:
        def _ser(v: Any) -> Any:
            # 基本类型与 None
            if v is None or isinstance(v, (str, int, float, bool)):
                return v

            # Pydantic BaseModel（v2: model_dump, v1: dict）
            try:
                if isinstance(v, BaseModel):
                    if hasattr(v, "model_dump"):
                        return v.model_dump()
                    if hasattr(v, "dict"):
                        return v.dict()
            except Exception:
                pass

            # 具备自定义序列化的对象（其他 Serializable 子类）
            if hasattr(v, "customer_serialize") and callable(getattr(v, "customer_serialize")):
                return v.customer_serialize()

            # 原生 dataclass
            if is_dataclass(v):
                return {f.name: _ser(getattr(v, f.name)) for f in fields(v)}

            # 映射类型
            if isinstance(v, dict):
                return {_ser(k): _ser(val) for k, val in v.items()}

            # 序列类型
            if isinstance(v, (list, tuple, set)):
                t = type(v)
                return t(_ser(item) for item in v)

            # 其它不可识别类型，原样返回（或根据需要转 str）
            return v

        # 只序列化当前 dataclass 的字段，逐个递归处理
        return {f.name: _ser(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def init_from_dict(cls: Type['Serializable'], data: Dict[str, Any]) -> 'Serializable':

        init_args = {}
        for field in fields(cls):
            try:
                field_value = data.get(field.name)
                if hasattr(field.type, 'init_from_dict') and isinstance(field_value, dict):
                    init_args[field.name] = field.type.init_from_dict(field_value)
                elif (isinstance(field_value, list) and
                      field.type.__args__ and
                      hasattr(field.type.__args__[0], 'init_from_dict') and
                      all(isinstance(i, dict) for i in field_value)):
                    init_args[field.name] = [field.type.__args__[0].init_from_dict(item) for item in field_value]
                else:
                    init_args[field.name] = field_value
            except Exception as e:
                logger.error(f"Error in {cls.__name__}, field: {field.name}, type: {field.type}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise e
        return cls(**init_args)


# =========================== Evidence Models ===========================
@dataclass
class FeatureMatchingEvidence(Serializable):
    """
    特征匹配证据 - 作为外部参考信息
    Feature matching evidence as external reference information
    """
    library_name: str
    library_id: int = None
    match_count: int = 0
    matched_strings: List[str] = dataclasses.field(default_factory=list)
    confidence_score: float = 0.0  # 匹配置信度 (0-1)
    source: str = "Feature Matching"
    description: str = ""


@dataclass
class EvidenceCollection(Serializable):
    """
    证据集合 - 包含所有内部证据和外部参考证据
    Evidence collection containing all internal and external reference evidence

    三个信息来源:
    1. 内部证据 (internal_evidence): 从二进制文件提取的信息
    2. 知识库检索 (knowledge_base): 从预构建知识库检索的匹配结果
    3. 外部搜索 (external_search): 从GitHub等外部源搜索的信息
    """
    # ===== 来源1: 内部证据 (Internal Evidence) =====
    target_binary: 'TargetBinary' = None  # 二进制文件的所有静态分析结果

    # ===== 来源2: 知识库检索 (Knowledge Base) =====
    # 字符串特征匹配结果
    string_feature_matches: List[FeatureMatchingEvidence] = dataclasses.field(default_factory=list)
    # 符号特征匹配结果
    symbol_feature_matches: List[FeatureMatchingEvidence] = dataclasses.field(default_factory=list)

    # 向后兼容: feature_matching_candidates 指向 string_feature_matches
    @property
    def feature_matching_candidates(self) -> List[FeatureMatchingEvidence]:
        return self.string_feature_matches

    # ===== 来源3: 外部搜索 (External Search) =====
    # GitHub搜索结果 (存储为字典列表，避免循环依赖)
    github_search_results: List[Dict[str, Any]] = dataclasses.field(default_factory=list)

    # ===== 上下文信息 =====
    software_context: SoftwareContext = None


@dataclass
class Serializable:

    def customer_serialize(self) -> Dict[str, Any]:
        def _ser(v: Any) -> Any:
            # 基本类型与 None
            if v is None or isinstance(v, (str, int, float, bool)):
                return v

            # Pydantic BaseModel（v2: model_dump, v1: dict）
            try:
                if isinstance(v, BaseModel):
                    if hasattr(v, "model_dump"):
                        return v.model_dump()
                    if hasattr(v, "dict"):
                        return v.dict()
            except Exception:
                pass

            # 具备自定义序列化的对象（其他 Serializable 子类）
            if hasattr(v, "customer_serialize") and callable(getattr(v, "customer_serialize")):
                return v.customer_serialize()

            # 原生 dataclass
            if is_dataclass(v):
                return {f.name: _ser(getattr(v, f.name)) for f in fields(v)}

            # 映射类型
            if isinstance(v, dict):
                return {_ser(k): _ser(val) for k, val in v.items()}

            # 序列类型
            if isinstance(v, (list, tuple, set)):
                t = type(v)
                return t(_ser(item) for item in v)

            # 其它不可识别类型，原样返回（或根据需要转 str）
            return v

        # 只序列化当前 dataclass 的字段，逐个递归处理
        return {f.name: _ser(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def init_from_dict(cls: Type['Serializable'], data: Dict[str, Any]) -> 'Serializable':

        init_args = {}
        for field in fields(cls):
            try:
                field_value = data.get(field.name)
                if hasattr(field.type, 'init_from_dict') and isinstance(field_value, dict):
                    init_args[field.name] = field.type.init_from_dict(field_value)
                elif (isinstance(field_value, list) and
                      field.type.__args__ and
                      hasattr(field.type.__args__[0], 'init_from_dict') and
                      all(isinstance(i, dict) for i in field_value)):
                    init_args[field.name] = [field.type.__args__[0].init_from_dict(item) for item in field_value]
                else:
                    init_args[field.name] = field_value
            except Exception as e:
                logger.error(f"Error in {cls.__name__}, field: {field.name}, type: {field.type}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise e
        return cls(**init_args)


@dataclass
class TargetBinary(Serializable):
    """
    目标二进制文件 - BinaryInfoParser 的输出

    职责说明：
    存储从二进制文件提取的**全部原始信息**，是后续所有分析的数据源。

    包含：
    - 基本元数据：文件名、路径、大小、哈希
    - 完整字符串列表：所有提取的字符串（用于版本分析等）
    - 分类字符串：按类型分类的字符串（版权、版本、URL等）
    - 动态库依赖：NEEDED/IMPORT 列表
    - 符号信息：导入/导出符号

    与 AnalysisMaterial 的区别：
    - TargetBinary: 全量原始数据，供多个阶段复用
    - AnalysisMaterial: LLM 分析视图，精选和格式化后的数据
    """
    # name
    binary_name: str
    hash_sha256: str = None  # SHA-256 hash of the binary file

    # path
    relative_path: str = ""
    absolute_path: str = ""

    # metadata
    file_size_kb: int = 0

    # strings
    strings: List[str] = dataclasses.field(default_factory=list)
    # 分类的字符串
    classified_strings:Dict[str, List[str]] = dataclasses.field(default_factory=dict)  # e.g., {"function": ["func1", "func2"], "variable": ["var1"]}

    # dynamic libraries
    dynamic_libraries: List[str] = dataclasses.field(default_factory=list)

    # symbols
    imported_symbols: List[str] = dataclasses.field(default_factory=list)
    exported_symbols: List[str] = dataclasses.field(default_factory=list)

    # symbol analysis
    exported_symbol_analysis:Dict[str, Any] = dataclasses.field(default_factory=dict)  # e.g., {"symbol_name": {"type": "function", "size": 64}}
    imported_symbol_analysis:Dict[str, Any] = dataclasses.field(default_factory=dict)  # e.g., {"symbol_name": {"type": "function", "size": 64}}

    # Binary Information
    information: BinaryInformation = None

    def preview(self):
        print("\n" + "="*60)
        print("📊 目标二进制文件预览")
        print("="*60)
        print(f"\tname: {self.binary_name}")
        print(f"\tpath: {self.absolute_path}")
        print(f"\tinformation: {self.information.description if self.information else 'N/A'}")
        print(f"\tSource TPL: {self.information.source_library.name + ':' + self.information.source_library.description if self.information and self.information.source_library else 'N/A'}")


@dataclass
class Library(Serializable):
    """
    Library detection result with complete analysis information
    """
    # ===== Library =====

    name: str  # Library name (e.g., "OpenSSL", "android_system_core")
    component_name: Optional[str] = None  # Component name for platform components or subcomponents (e.g., "libssl", "liblog")
    binary_category: str = ""  # "android_platform", "third_party_library", "unknown_program"
    library_integration_type: str = ""  # "Main Program", "Static Linked", "Dynamic Linked" (deprecated, use component_type)
    description: str = ""  # Library description
    final_reasoning: str = ""  # Result Refiner final reasoning (refined and polished)
    id: int = None  # Library ID from feature matching database

    # ===== 1. 成分类型 (Component Type) =====
    component_type: str = ""  # "main_program" | "dynamic_linked" | "static_linked"

    # ===== 2. 识别方法 (Detection Method) =====
    detection_method: str = ""  # "llm_analysis" | "feature_matching" | "external_search"
    detection_sub_method: str = ""  # llm: "direct_recognition" | "heuristic_association"
                                    # feature_matching: "string_feature" | "symbol_feature"
                                    # external_search: "github_search"

    # ===== 3. 验证阶段输出 (Validation Output) =====
    validation_passed: bool = True  # 验证是否通过
    validation_stage: str = ""  # 验证阶段: "existence" | "evidence" | "consistency"
    validation_reasoning: str = ""  # 验证分析说明

    # ===== Detection Type & Source (Legacy) =====
    detection_type: str = ""  # "direct_recognition" or "association" - how LLM detected this library
    detection_sources: List[str] = dataclasses.field(default_factory=list)  # ["llm_direct", "llm_association", "feature_matching"]

    # ====== Library Version =====
    versions: List[VersionCandidate] = dataclasses.field(default_factory=list)  # Detected versions
    version_reasoning: str = ""  # Version detection reasoning

    # ===== User-Friendly Explanation =====
    user_explanation: str = ""  # User-friendly explanation of detection result (generated by LLM)

    # ===== Analysis Output =====
    potential_candidates: List[str] = dataclasses.field(default_factory=list)  # 潜在候选列表（主程序识别的中间结果）
    evidences: List[str] = dataclasses.field(default_factory=list)  # Evidence strings from binary
    identify_reasoning: str = ""  # Analysis reasoning

    # ===== False Positive Filter Output =====
    filter_passed: bool = True  # Whether passed false positive filter
    filter_decision: str = ""  # "KEEP" or "REJECT"
    filter_reasoning: str = ""  # Filter reasoning
    triggered_scenarios: List[str] = dataclasses.field(default_factory=list)  # Triggered FP scenarios (e.g., ["1.1", "2.3"])

    # ===== Feature Matching Output =====
    matched_strings: List[str] = dataclasses.field(default_factory=list)  # Strings matched in feature matching

    def get_name(self):
        if self.component_name:
            return f"{self.name} [component: {self.component_name}, type: {self.library_integration_type}]"
        else:
            return f"{self.name} [type: {self.library_integration_type}]"

    def public_serialize(self) -> Dict[str, Any]:
        """
        Serialize only public fields for API response (hide internal reasoning)
        返回给前端的公开字段序列化
        """
        result = {
            "name": self.name,
            "component_name": self.component_name,
            "binary_category": self.binary_category,
            "library_integration_type": self.library_integration_type,
            "component_type": self.component_type,
            "description": self.description,
            "id": self.id,
            "user_explanation": self.user_explanation,
            "evidences": self.evidences[:20] if self.evidences else [],  # 限制数量
        }

        # Version info (public)
        if self.versions:
            result["versions"] = [
                {
                    "version": v.version,
                    "confidence": v.confidence,
                }
                for v in self.versions
            ]
        else:
            result["versions"] = []

        return result
@dataclass
class AnalysisConfig(Serializable):
    """
    分析配置 / Analysis Configuration

    记录分析时使用的配置参数，用于结果追溯和复现
    Records configuration parameters used during analysis for traceability and reproducibility
    """
    # LLM 配置 / LLM Config
    llm_provider: str = settings.LLM_PROVIDER
    model_id: str = settings.LLM_MODEL_ID
    input_token_price_per_1M: float = settings.LLM_INPUT_TOKEN_PRICE
    output_token_price_per_1M: float = settings.LLM_OUTPUT_TOKEN_PRICE
    cached_input_token_price_per_1M: float = settings.LLM_CACHED_INPUT_TOKEN_PRICE

    # 特征匹配配置 / Feature Matching Config
    feature_matching_return_top_n: int = 10  # 候选数量 / Number of candidates

    # 运行模式 / Runtime Mode
    use_agent: bool = True  # 是否使用 LLM / Whether to use LLM
    debug_mode: bool = False  # 调试模式 / Debug mode


# =========================== Version Analysis Models ===========================
# 版本候选

# LLM版本分析结果

# 版本分析结果
@dataclass
class VersionAnalysisResult(Serializable):
    file_path: str
    library_name: Optional[str] = None # 库名称

    # version result
    detected_versions: List[VersionCandidate] = dataclasses.field(default_factory=list)  # e.g., [{"version": "1.2.3", "confidence": "high", "evidences": [...]}, ...]
    reasoning:str = ""  # overall reasoning for version detection

    # efficiency
    analysis_duration: float = 0.0

    # analysis data
    llm_analysis_input: Dict[str, Any] =  dataclasses.field(default_factory=dict) # LLM分析输入的字符串
    llm_analysis_results: Optional["LLMVersionAnalysisResult"] = None  # 前面定义的 Pydantic 模型
    llm_costs: Dict[str, Any] = dataclasses.field(default_factory=dict)  # e.g., {"input_tokens": 100, "output_tokens": 50}

    def preview(self):
        print("\n" + "="*60)
        print("📊 版本分析结果预览")
        print("="*60)
        print(f"\tfile_path: {self.file_path}")
        print(f"\tlibrary_name: {self.library_name}")
        print(f"\tdetected_version: {self.detected_versions}")
        print(f"\treasoning: {self.reasoning}")
        print(f"\tanalysis_duration: {self.analysis_duration:.2f}s")

@dataclass
class DirectoryNode(Serializable):
    """目录节点 - 用于特征来源树"""
    name: str  # 目录名
    count: int = 0  # 匹配特征数量
    percentage: float = 0.0  # 占总数的百分比
    examples: List[str] = dataclasses.field(default_factory=list)  # 该目录下的特征示例
    children: Dict[str, 'DirectoryNode'] = dataclasses.field(default_factory=dict)  # 子目录


@dataclass
class FeatureMatchCandidate(Serializable):
    """特征匹配候选结果"""
    library_name: str
    library_id: int = None  # 库ID，用于查询文件路径
    match_type: str = ""  # "string_feature" | "symbol_feature" | "string+symbol"
    confidence: float = 0.0
    matched_evidence: List[str] = dataclasses.field(default_factory=list)
    evidence_count: int = 0
    # 分项匹配数量（三路召回合并后使用）
    string_match_count: int = 0  # 字符串匹配数量
    symbol_match_count: int = 0  # 符号匹配数量
    # 重叠分析字段
    unique_count: int = 0  # 该候选独有的特征数量（不与其他任何候选重叠）
    unique_examples: List[str] = dataclasses.field(default_factory=list)  # 独有特征示例
    overlap_info: Dict[str, int] = dataclasses.field(default_factory=dict)  # {其他库名: 重叠特征数}
    # 特征来源目录树
    source_tree: Dict[str, DirectoryNode] = dataclasses.field(default_factory=dict)  # {一级目录名: DirectoryNode}


@dataclass
class PhaseRecord(Serializable):
    """
    单个阶段的记录
    Record for a single analysis phase
    """
    start_time: str = None  # 阶段开始时间
    duration: float = 0.0   # 阶段总耗时（秒）
    llm_calls: List[Dict[str, Any]] = dataclasses.field(default_factory=list)  # 每次 LLM 调用的详情
    # llm_calls 示例:
    # [
    #     {"library": "zlib", "input_tokens": 500, "output_tokens": 300, "duration": 1.1},
    #     {"library": "openssl", "input_tokens": 600, "output_tokens": 400, "duration": 1.3},
    # ]
    output: Dict[str, Any] = dataclasses.field(default_factory=dict)  # 阶段输出的摘要信息


@dataclass
class AnalysisData(Serializable):
    # ===== 1. 时间信息 =====
    analysis_start_time: str = dataclasses.field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    analysis_end_time: str = None

    # ===== 2. 配置信息 =====
    config: AnalysisConfig = None

    # ===== 3. 输入信息 =====
    target_binary: TargetBinary = None
    context: SoftwareContext = None

    # ===== 4. 分析过程 =====
    # tpl_analysis_phases = {
    #     "phase1_material_collection": PhaseRecord(...),
    #     "phase2_composition_analysis": PhaseRecord(...),
    #     "phase3_version_analysis": PhaseRecord(...),
    #     "phase4_explanation_generation": PhaseRecord(...)
    # }
    tpl_analysis_phases: Dict[str, PhaseRecord] = dataclasses.field(default_factory=dict)
    feature_match_candidates: List[FeatureMatchCandidate] = dataclasses.field(default_factory=list)
    version_analysis_results: List[VersionAnalysisResult] = dataclasses.field(default_factory=list)

    # ===== 5. 汇总结果 =====
    # summary = {
    #     "total_duration": 9.24,
    #     "total_llm_calls": 7,
    #     "total_input_tokens": 5300,
    #     "total_output_tokens": 2900,
    #     "total_cost": 0.034
    # }
    summary: Dict[str, Any] = dataclasses.field(default_factory=dict)

    # ===== 6. 错误信息 =====
    error_message: str = None

    # ===== 7. 调试信息（可选） =====
    chat_history: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def preview(self):
        """Preview analysis results - New architecture version"""
        print("\n" + "=" * 80)
        print("📊 Analysis Results Preview")
        print("=" * 80)

        # ========== Performance & Cost Analysis ==========
        print("\n" + "=" * 80)
        print("⚡ Performance & Cost Analysis")
        print("=" * 80)

        # Time Cost (grouped by new architecture)
        self.preview_time_cost()

        # Token Cost
        print("\n💰 Token Cost:")
        self.preview_token_cost()

        print("\n" + "=" * 80)

        # Error information
        if self.error_message:
            print(f"\n❌ Error: {self.error_message}")
            print("=" * 80)
            return

        binary_name = self.target_binary.binary_name if self.target_binary else "Unknown"
        print(f"Target Binary: {binary_name}")
        print(f"Analysis Time: {self.analysis_datetime}")
        print("=" * 80)

        # ========== 0. Software Context ==========
        if self.context:
            print("\n🌐 Software Context Analysis")
            print("-" * 80)
            print(f"   Software Type: {self.context.software_type}")
            print(f"   Primary Purpose: {self.context.primary_purpose}")
            if self.context.technology_stack:
                print(f"   Technology Stack: {', '.join(self.context.technology_stack)}")
            print(f"   Deployment Environment: {self.context.deployment_environment}")
            print(f"   Architecture Pattern: {self.context.architecture_pattern}")
            print(f"   Confidence Level: {self.context.confidence_level}")

        # ========== 1. Target Binary Information ==========
        print("\n📁 Target Binary Information")
        print("-" * 80)
        if self.target_binary:
            self.target_binary.preview()

        # ========== PHASE 1: Evidence Collection ==========
        print("\n" + "=" * 80)
        print("📦 PHASE 1: Evidence Collection")
        print("=" * 80)

        # 1.1 Internal Evidence
        self.preview_evidencies()

        # ========== PHASE 2: Agent Analysis ==========
        print("\n" + "=" * 80)
        print("🤖 PHASE 2: Agent Analysis")
        print("=" * 80)

        # 2.1 TPL Reasoning Analysis
        print("\n🧠 Step 1: TPL Reasoning Analysis")
        print("-" * 80)
        print(f"   Identified Libraries: {len(self.tpl_analysis_results)}")
        self.preview_reasoning_result()

        # 2.2 False Positive Filter
        print("\n🛡️  Step 2: False Positive Filter")
        print("-" * 80)
        self.preview_filter_result()

        # 2.3 Result Refinement
        print("\n✨ Step 3: Result Refinement")
        print("-" * 80)
        self.preview_refine_result()

        # 2.4 Version Analysis Results
        print("\n📅 Step 4: Version Analysis Results")
        print("-" * 80)
        self.preview_version_analysis_result()

        print("=" * 80)

    def preview_version_analysis_result(self):
        if self.version_analysis_results:
            for version_result in self.version_analysis_results:
                print(f"\n   Library: {version_result.library_name}")
                if version_result.detected_versions:
                    for v in version_result.detected_versions:
                        print(f"      Detected Version: {v.version} (Confidence: {v.confidence})")
                        if v.evidences:
                            evidence_preview = ', '.join(v.evidences[:3])
                            print(f"         Evidences: {evidence_preview}")
                            if len(v.evidences) > 3:
                                print(f"                     ... and {len(v.evidences) - 3} more")
                else:
                    print("      No versions detected")
                print(f"      Reasoning: {version_result.reasoning}")
                print(f"      Analysis Duration: {version_result.analysis_duration:.2f}s")

    def preview_token_cost(self):
        if self.costs:
            total_input = 0
            total_output = 0

            for step, cost_data in self.costs.items():
                print(f"\n   {step}:")
                if isinstance(cost_data, dict):
                    for key, value in cost_data.items():
                        if key in ["input_tokens", "output_tokens", "total_tokens"]:
                            token_count = value if isinstance(value, (int, float)) else (
                                value[0] if isinstance(value, (list, tuple)) and len(value) > 0 else 0)
                            print(f"      {key}: {token_count} tokens")
                            if key == "input_tokens":
                                total_input += token_count
                            elif key == "output_tokens":
                                total_output += token_count

            if total_input > 0 or total_output > 0:
                total_tokens = total_input + total_output
                print(f"\n   Total:")
                print(f"      Input Tokens: {total_input}")
                print(f"      Output Tokens: {total_output}")
                print(f"      Total Tokens: {total_tokens}")

                # Cost estimation (assuming GPT-4 pricing)
                total_cost = total_input * 2 / 1_000_000 + total_output * 8 / 1_000_000
                print(f"      Estimated Cost: ${total_cost:.6f} (Input $2/M, Output $8/M)")
        else:
            print("   No cost data")

    def preview_time_cost(self):
        print("\n⏱️  Time Cost:")
        if self.durations:
            # Phase 1: Evidence Collection
            if "evidence_collection" in self.durations:
                print(f"\n   📦 Phase 1: Evidence Collection")
                print(f"      Total: {self.durations['evidence_collection']:.2f}s")

            # Phase 2: Agent Analysis (by steps)
            agent_steps = {
                "_tpl_analyzer": "TPL Reasoning",
                "_false_positive_filter": "False Positive Filter",
                "_result_refiner": "Result Refinement"
            }
            has_agent_steps = any(step in self.durations for step in agent_steps.keys())

            if has_agent_steps:
                print(f"\n   🤖 Phase 2: Agent Analysis")
                for step_key, step_name in agent_steps.items():
                    if step_key in self.durations:
                        print(f"      {step_name}: {self.durations[step_key]:.2f}s")

            # Other steps
            other_steps = {k: v for k, v in self.durations.items()
                           if k not in ["evidence_collection", "total"] + list(agent_steps.keys())}
            if other_steps:
                print(f"\n   🔧 Other:")
                for step, duration in other_steps.items():
                    print(f"      {step}: {duration:.2f}s")

            # Total time
            if "total" in self.durations:
                print(f"\n   ⏰ Total Time: {self.durations['total']:.2f}s")
        else:
            print("   No time cost data")

    def preview_refine_result(self):

        if self.tpl_analysis_results:
            for i, lib in enumerate(self.tpl_analysis_results, 1):
                print(f"\n   {i}. Library Name: {lib.name}")
                if lib.component_name:
                    print(f"      Component Name: {lib.component_name}")
                if lib.binary_category:
                    print(f"      Binary Category: {lib.binary_category}")
                if lib.library_integration_type:
                    print(f"      Library Integration Type: {lib.library_integration_type}")
                if lib.description:
                    desc = lib.description
                    print(f"      Description: {desc}")
                if lib.evidences:
                    print(f"      Evidence Count: {len(lib.evidences)}")
                    evidence_preview = ', '.join(lib.evidences[:3])
                    print(f"      Evidence Examples: {evidence_preview}")
                    if len(lib.evidences) > 3:
                        print(f"                         ... and {len(lib.evidences) - 3} more")
                if lib.identify_reasoning:
                    reasoning = lib.identify_reasoning
                    print(f"      Reasoning: {reasoning}")
        else:
            print("   No libraries identified by Agent")


    def preview_filter_result(self):
        if self.filter_results:
            # Now filter_results is List[Library] with filter_passed field
            kept = sum(1 for lib in self.filter_results if lib.filter_passed)
            rejected = len(self.filter_results) - kept
            print(f"   Libraries Checked: {len(self.filter_results)}")
            print(f"   ✅ Kept: {kept} | ❌ Rejected: {rejected}")

            # Show kept libraries
            if kept > 0:
                print("\n   ✅ Kept Libraries:")
                for lib in self.filter_results:
                    if lib.filter_passed:
                        print(f"      ✓ Library Name: {lib.name}")
                        if lib.component_name:
                            print(f"        Component Name: {lib.component_name}")
                        if lib.filter_reasoning:
                            reasoning = lib.filter_reasoning
                            print(f"        Reason: {reasoning}")

            # Show rejected libraries and reasons
            if rejected > 0:
                print("\n   ❌ Rejected Libraries:")
                for lib in self.filter_results:
                    if not lib.filter_passed:
                        print(f"      ✗ Library Name: {lib.name}")
                        if lib.component_name:
                            print(f"        Component Name: {lib.component_name}")
                        if lib.triggered_scenarios:
                            scenarios = ', '.join(lib.triggered_scenarios)
                            print(f"        Triggered Scenarios: {scenarios}")
                        if lib.filter_reasoning:
                            reasoning = lib.filter_reasoning
                            print(f"        Reason: {reasoning}")
        else:
            print("   False positive filter not executed")

    def preview_reasoning_result(self):
        if self.tpl_analysis_results:
            for i, lib in enumerate(self.tpl_analysis_results, 1):
                print(f"\n   {i}. Library Name: {lib.name}")
                if lib.component_name:
                    print(f"      Component Name: {lib.component_name}")
                if lib.binary_category:
                    print(f"      Binary Category: {lib.binary_category}")
                if lib.library_integration_type:
                    print(f"      Library Integration Type: {lib.library_integration_type}")
                if lib.description:
                    desc = lib.description
                    print(f"      Description: {desc}")
                if lib.evidences:
                    print(f"      Evidence Count: {len(lib.evidences)}")
                    evidence_preview = ', '.join(lib.evidences[:3])
                    print(f"      Evidence Examples: {evidence_preview}")
                    if len(lib.evidences) > 3:
                        print(f"                         ... and {len(lib.evidences) - 3} more")
                if lib.identify_reasoning:
                    reasoning = lib.identify_reasoning
                    print(f"      Reasoning: {reasoning}")
        else:
            print("   No libraries identified by Agent")

    def preview_evidencies(self):
        print("\n📂 Internal Evidence:")
        if self.target_binary:
            exported = len(self.target_binary.exported_symbols) if self.target_binary.exported_symbols else 0
            imported = len(self.target_binary.imported_symbols) if self.target_binary.imported_symbols else 0
            strings = len(self.target_binary.strings) if self.target_binary.strings else 0
            dynamic_libs = len(
                self.target_binary.dynamic_libraries) if self.target_binary.dynamic_libraries else 0

            print(f"   Exported Symbols: {exported}")
            print(f"   Imported Symbols: {imported}")
            print(f"   Total Strings: {strings}")
            print(f"   Dynamic Libraries: {dynamic_libs}")
        # 1.2 Hypothesis Results by Source
        print("\n🔍 Hypothesis Results by Source:")
        print(f"   String Feature: {len(self.string_feature_results)} candidates")
        print(f"   Symbol Feature: {len(self.symbol_feature_results)} candidates")
        print(f"   GitHub: {len(self.github_results)} candidates")
        print(f"   LLM Direct: {len(self.llm_direct_results)} candidates")
        print(f"   LLM Association: {len(self.llm_association_results)} candidates")
        print(f"   All Hypotheses (merged): {len(self.all_hypothesis_results)} candidates")

        if self.all_hypothesis_results:
            display_count = min(10, len(self.all_hypothesis_results))
            print("\n   Top candidates:")
            for i, lib in enumerate(self.all_hypothesis_results[:display_count], 1):
                match_count = len(lib.matched_strings) if lib.matched_strings else 0
                source = lib.detection_sources[0] if lib.detection_sources else "unknown"
                print(f"   {i}. {lib.name} (source: {source}) - {match_count} matched features")
            if len(self.all_hypothesis_results) > display_count:
                remaining = len(self.all_hypothesis_results) - display_count
                print(f"   ... and {remaining} more candidates")
        else:
            print("   No hypothesis candidates found")


@dataclass
class SimpleResult(Serializable):
    target_binary_name: str = None
    target_binary_size_kb:float = None
    target_binary_sha256: str = None
    target_binary_path: str = None
    detected_library_names: List[str] = dataclasses.field(default_factory=list)


@dataclass
class ExcludedCandidate(Serializable):
    """被排除的候选库"""
    name: str  # 候选库名
    fp_type: str  # 误报类型: C1, C2, C3, C4, C5
    reasoning: str = ""  # 排除理由


@dataclass
class AnalysisResult(Serializable):
    binary_name: str
    binary_sha256: str
    binary_path: str
    main_program: Library = None
    detected_libraries: List[Library] = dataclasses.field(default_factory=list)
    detected_dynamic_libraries: List[Library] = dataclasses.field(default_factory=list)
    excluded_candidates: List[ExcludedCandidate] = dataclasses.field(default_factory=list)
    analysis_data: AnalysisData = None
    succeed: bool = True  # 分析是否成功
    error_message: str = None

    def dump_to_file(self, file_path: str):
        """
        将分析结果序列化并保存到文件
        """
        import json
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.customer_serialize(), f, ensure_ascii=False, indent=4)

    @classmethod
    def init_from_file(cls, file_path: str):
        """
        从文件中加载分析结果
        """
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return cls.init_from_dict(data)

    def get_simple_result(self) -> SimpleResult:
        """
        获取简化的分析结果
        """
        return SimpleResult(
            target_binary_name=self.binary_name,
            target_binary_size_kb=self.analysis_data.target_binary.file_size_kb,
            target_binary_sha256=self.binary_sha256,
            target_binary_path=self.binary_path,
            detected_library_names=[lib.name for lib in self.detected_libraries]
        )

    def public_serialize(self) -> Dict[str, Any]:
        """
        Serialize only public fields for API response (hide internal analysis data)
        返回给前端的公开字段序列化，隐藏内部分析数据
        """
        # Build target_binary data for UI (meta, strings, symbols)
        target_binary_data = None
        if self.analysis_data and self.analysis_data.target_binary:
            tb = self.analysis_data.target_binary
            target_binary_data = {
                "binary_name": tb.binary_name,
                "hash_sha256": tb.hash_sha256,
                "relative_path": tb.relative_path,
                "file_size_kb": tb.file_size_kb,
                "strings": tb.strings or [],
                "dynamic_libraries": tb.dynamic_libraries or [],
                "imported_symbols": tb.imported_symbols or [],
                "exported_symbols": tb.exported_symbols or [],
            }

        return {
            "binary_name": self.binary_name,
            "binary_sha256": self.binary_sha256,
            "binary_path": self.binary_path,
            "succeed": self.succeed,
            "error_message": self.error_message,
            "main_program": self.main_program.public_serialize() if self.main_program else None,
            "detected_libraries": [lib.public_serialize() for lib in self.detected_libraries] if self.detected_libraries else [],
            "detected_dynamic_libraries": [lib.public_serialize() for lib in self.detected_dynamic_libraries] if self.detected_dynamic_libraries else [],
            "analysis_data": {
                "target_binary": target_binary_data
            } if target_binary_data else None,
        }

@dataclass
class BinaryContext(Serializable):
    """
    Binary file context information (预留接口)
    """
    # 项目基本信息
    project_root_path: str = ""
    project_type: str = ""  # web应用、桌面软件、库等
    project_description: str = ""  # 从README等提取的项目描述

    # 文件位置信息
    file_relative_path: str = ""  # 相对于项目根目录的路径
    directory_context: str = ""  # 所在目录的文件类型和用途

    # 项目结构信息
    key_files: List[str] = dataclasses.field(default_factory=list)  # 关键文件列表
    build_system: str = ""  # CMake, Makefile, npm等

    # 功能推断
    likely_purpose: str = ""  # 这个二进制文件可能的用途
    related_binaries: List[str] = dataclasses.field(default_factory=list)  # 相关的其他二进制文件


class TPLDetectionTaskStatus(Enum):
    """
    任务状态
    """
    PENDING = "pending"  # 任务正在等待执行

    FILE_DOWNLOADING = "file_downloading"  # 文件下载中
    UNPACKING = "unpacking"  # 文件解包中
    UNPACKING_RESULT_UPLOADING = "unpacking_result_uploading"  # 解压结果上传中
    ANALYZING = "analyzing"  # 任务正在分析中
    RESULT_UPLOADING = "result_uploading"  # 结果上传中
    SUCCESS = "success"  # 任务执行成功
    FAILED = "failed"  # 任务执行成功

    def customer_serialize(self) -> str:
        return self.value

    @classmethod
    def init_from_dict(cls, data: str) -> 'TPLDetectionTaskStatus':
        return cls(data)

@dataclass
class TPLDetectionTask(Serializable):
    task_id: str
    file_minio_path: str # minio 路径
    file_local_path: str = None  # 本地临时路径
    workspace_dir: str = None  # 任务专用工作目录路径

    start_at: str = dataclasses.field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    end_at: str = None
    
    # 各个步骤的时间
    file_download_start_at: str = None
    file_download_end_at: str = None
    unpack_start_at: str = None
    unpack_end_at: str = None
    upload_unpack_result_start_at: str = None
    upload_unpack_result_end_at: str = None
    analysis_start_at: str = None
    analysis_end_at: str = None
    result_upload_start_at: str = None
    result_upload_end_at: str = None

    # result
    result_local_path: str = None
    result_minio_path: str = None

    filelist_local_path: str = None
    filelist_minio_path: str = None

    # task info
    task_info_local_path: str = None
    task_info_minio_path: str = None

    # report
    report_minio_path: str = None  # Path to generated report ZIP in MinIO

    # 分析进度相关字段
    analysis_total_files: int = 0  # 需要分析的文件总数
    analysis_completed_files: int = 0  # 已完成分析的文件数
    current_analyzing_file: str = None  # 当前正在分析的文件名/路径
    current_analyzing_phase: str = None  # 当前分析阶段 (parsing/feature_matching/tpl_analysis/version_analysis/generating_explanation)

    status: TPLDetectionTaskStatus = TPLDetectionTaskStatus.PENDING
    error_message: str = None


# =================== Batch Refresh Task Models ===================

class BatchRefreshStatus(Enum):
    """
    批量刷新任务状态
    Batch refresh task status
    """
    PENDING = "pending"  # 任务等待执行
    RUNNING = "running"  # 任务正在执行
    SUCCESS = "success"  # 任务全部成功
    PARTIAL_SUCCESS = "partial_success"  # 部分成功
    FAILED = "failed"  # 任务失败

    def customer_serialize(self) -> str:
        return self.value

    @classmethod
    def init_from_dict(cls, data: str) -> 'BatchRefreshStatus':
        return cls(data)


@dataclass
class BatchRefreshTask(Serializable):
    """
    批量刷新 Library Status 任务
    Batch refresh library status task
    """
    task_id: str
    status: BatchRefreshStatus = BatchRefreshStatus.PENDING

    # Progress tracking
    total_libraries: int = 0
    completed_libraries: int = 0
    failed_libraries: int = 0

    # Current processing
    current_library_id: int = None
    current_library_name: str = None

    # Failed library tracking
    failed_library_details: Dict[int, str] = dataclasses.field(default_factory=dict)  # {library_id: error_message}

    # Timestamps
    start_at: str = dataclasses.field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    end_at: str = None

    # Error message
    error_message: str = None
