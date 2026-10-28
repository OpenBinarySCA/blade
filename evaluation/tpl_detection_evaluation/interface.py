"""
TPL Detection Evaluation - 数据结构定义

简化版架构：只保留核心评估需要的数据结构
- 测试用例、基准数据集相关结构
- 评估结果检查结构
- 特征匹配效果结构
- 评估报告结构
"""
import dataclasses
import json
import os
import traceback
from dataclasses import asdict, fields, dataclass
from datetime import datetime
from typing import Dict, Type, Any, Optional, get_origin, get_args, Union, List, Set, TYPE_CHECKING
from loguru import logger

from app.config import settings

from app.services.tpl_detection.binary_info_parser.parser import calculate_file_sha256

if TYPE_CHECKING:
    from app.interface import AnalysisResult


# ========== 基础序列化类 ==========

@dataclass
class Serializable:
    def customer_serialize(self) -> Dict[str, Any]:
        serialized_data = asdict(self)
        for field in fields(self):
            value = getattr(self, field.name)
            if hasattr(value, 'customer_serialize'):
                serialized_data[field.name] = value.customer_serialize()
            elif isinstance(value, list) and value and hasattr(value[0], 'customer_serialize'):
                serialized_data[field.name] = [item.customer_serialize() for item in value]
            elif isinstance(value, dict):
                serialized_dict = {}
                for key, val in value.items():
                    if hasattr(val, 'customer_serialize'):
                        serialized_dict[key] = val.customer_serialize()
                    elif isinstance(val, list) and val and hasattr(val[0], 'customer_serialize'):
                        serialized_dict[key] = [item.customer_serialize() for item in val]
                    else:
                        serialized_dict[key] = val
                serialized_data[field.name] = serialized_dict
        return serialized_data

    @classmethod
    def init_from_dict(cls: Type['Serializable'], data: Dict[str, Any]) -> 'Serializable':
        init_args = {}
        for field in fields(cls):
            try:
                field_value = data.get(field.name)
                if field_value is None:
                    init_args[field.name] = field_value
                    continue

                field_type = field.type
                origin_type = get_origin(field_type)
                type_args = get_args(field_type)

                if hasattr(field_type, 'init_from_dict') and isinstance(field_value, dict):
                    init_args[field.name] = field_type.init_from_dict(field_value)
                elif (origin_type is list and isinstance(field_value, list) and type_args and
                      hasattr(type_args[0], 'init_from_dict') and
                      all(isinstance(i, dict) for i in field_value if i is not None)):
                    init_args[field.name] = [type_args[0].init_from_dict(item) for item in field_value if item is not None]
                elif origin_type is dict and isinstance(field_value, dict) and len(type_args) >= 2:
                    value_type = type_args[1]
                    value_origin = get_origin(value_type)
                    value_args = get_args(value_type)

                    if value_origin is list and value_args and hasattr(value_args[0], 'init_from_dict'):
                        processed_dict = {}
                        for key, value_list in field_value.items():
                            if isinstance(value_list, list):
                                processed_dict[key] = [value_args[0].init_from_dict(item) for item in value_list if isinstance(item, dict)]
                            else:
                                processed_dict[key] = value_list
                        init_args[field.name] = processed_dict
                    elif hasattr(value_type, 'init_from_dict'):
                        processed_dict = {}
                        for key, value_item in field_value.items():
                            if isinstance(value_item, dict):
                                processed_dict[key] = value_type.init_from_dict(value_item)
                            else:
                                processed_dict[key] = value_item
                        init_args[field.name] = processed_dict
                    else:
                        init_args[field.name] = field_value
                elif origin_type is Union:
                    initialized = False
                    for union_type in type_args:
                        if union_type is type(None):
                            continue
                        try:
                            if hasattr(union_type, 'init_from_dict') and isinstance(field_value, dict):
                                init_args[field.name] = union_type.init_from_dict(field_value)
                                initialized = True
                                break
                        except:
                            continue
                    if not initialized:
                        init_args[field.name] = field_value
                else:
                    init_args[field.name] = field_value
            except Exception as e:
                logger.error(f"Error in {cls.__name__}, field: {field.name}, type: {field.type}")
                logger.error(f"Field value: {field_value}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise e
        return cls(**init_args)


# ========== Benchmark 相关结构 ==========

@dataclass
class CompileConfig(Serializable):
    conan_version: str
    profile: str


@dataclass
class TestBinary(Serializable):
    original_name: str
    relative_path: str
    file_size_kb: float
    sha256: str = None
    notes: str = None
    compile_config: Optional[CompileConfig] = None


@dataclass
class ReusedLibrary(Serializable):
    name: str
    vendor: str = None
    repository: str = None
    other_names: List[str] = dataclasses.field(default_factory=list)
    version: str = None
    description: str = None
    type: str = None
    notes: str = None


@dataclass
class TestCase(Serializable):
    test_binary: TestBinary
    reused_libraries: List[ReusedLibrary]


@dataclass
class BenchmarkMeta(Serializable):
    name: str
    test_case_num: int
    covered_library_num: int
    version: str


@dataclass
class BenchmarkNote(Serializable):
    message: str
    update_at: str = dataclasses.field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class BenchmarkSummary(Serializable):
    test_case_num: int
    covered_library_num: int


@dataclass
class Benchmark(Serializable):
    name: str
    version: str
    summary: BenchmarkSummary = None
    notes: List[BenchmarkNote] = dataclasses.field(default_factory=list)
    test_cases: List[TestCase] = dataclasses.field(default_factory=list)

    @classmethod
    def load_from_json_file(cls, json_path: str) -> 'Benchmark':
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.init_from_dict(data)

    def dump_to_json_file(self, json_path: str):
        data = self.customer_serialize()
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return json_path

    def get_meta(self):
        test_case_num = len(self.test_cases)
        covered_library_set = set()
        for tc in self.test_cases:
            for reused_lib in tc.reused_libraries:
                covered_library_set.add(reused_lib.name)

        return BenchmarkMeta(
            name=self.name,
            test_case_num=test_case_num,
            covered_library_num=len(covered_library_set),
            version=self.version,
        )

    def update_sha256(self, new_test_case_dir_path: str):
        for tc in self.test_cases:
            tc_path = os.path.join(new_test_case_dir_path, tc.test_binary.relative_path)
            tc.test_binary.sha256 = calculate_file_sha256(tc_path)

    def __repr__(self):
        return self.get_meta().__repr__()


# ========== 评估配置 ==========

@dataclass
class EvaluationConfig(Serializable):
    benchmark_file: str
    test_case_dir: str

    # LLM 配置
    llm_provider: str = settings.LLM_PROVIDER
    llm_model_id: str = settings.LLM_MODEL_ID
    input_token_price_per_1M: float = settings.LLM_INPUT_TOKEN_PRICE
    output_token_price_per_1M: float = settings.LLM_OUTPUT_TOKEN_PRICE
    cached_input_token_price_per_1M: float = settings.LLM_CACHED_INPUT_TOKEN_PRICE

    # 工作流设置
    use_agent: bool = True
    silent: bool = False  # 静默模式：关闭所有日志，只显示警告和错误

    symbol_use_imported: bool = False  # 符号匹配是否使用导入符号（默认只使用导出符号）

    # 召回路线开关（默认全开）
    enable_hint_recall: bool = True       # 是否启用 Hint 召回路线
    enable_string_recall: bool = True     # 是否启用字符串特征匹配路线
    enable_symbol_recall: bool = True     # 是否启用符号特征匹配路线

    # 特征召回配置
    retrieval_top_n: int = 10             # 最终输出数量（合并排序后取前 N 个）
    hint_first: bool = False              # 排序策略：False=Round-Robin，True=Hint优先

    # 并发
    concurrency: int = 3

    # 切片
    slice_start: int = 0
    slice_end: int = -1

    # 验证阶段消融实验配置（6个实验）
    ablation_all: bool = False            # -All: 消融全部证据和CoT（纯LLM基线）
    ablation_no_s1: bool = False          # -S1: 消融 Anchor Confirmation（去 Identity Markers + S1 prompt）
    ablation_no_s2: bool = False          # -S2: 消融 Dependency Filtering（去 Match Distribution + S2 prompt + C2）
    ablation_no_s3: bool = False          # -S3: 消融 Feature Attribution（去 Candidate Comparison + Library Metadata + S3 prompt + C3/C5）
    ablation_no_s4: bool = False          # -S4: 消融 Evidence Quality Validation（去 S4 prompt + C4）
    ablation_no_cot: bool = False         # -CoT: 消融全部CoT（保留全部证据，使用简化 prompt）

    # 特征匹配过滤配置
    library_blacklist: Set[str] = None    # 库黑名单（系统库），None 使用默认值：glibc, gcc 等
    min_match_count_threshold: int = None # 最小匹配数阈值，None 使用默认值 5

    # 版本分析和说明生成开关（论文实验可关闭以节省成本）
    enable_version_analysis: bool = False      # 是否启用版本分析（Phase 3）
    enable_explanation_generation: bool = False  # 是否启用说明生成（Phase 4）

    def customer_serialize(self) -> Dict[str, Any]:
        """重写序列化方法，处理 Set 类型"""
        data = super().customer_serialize()
        # 将 Set 转换为 sorted List，便于 JSON 序列化
        if data.get('library_blacklist') is not None:
            data['library_blacklist'] = sorted(data['library_blacklist'])
        return data


# ========== 核心评估数据结构 ==========

@dataclass
class EffectivenessData(Serializable):
    """效果数据：TP/FP/FN + P/R/F1"""
    tp_count: int = 0
    fp_count: int = 0
    fn_count: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0


@dataclass
class FeatureMatchingEffectiveness(Serializable):
    """特征匹配效果：top_1 ~ top_5 的 P/R/F1"""
    top_1: EffectivenessData = None
    top_2: EffectivenessData = None
    top_3: EffectivenessData = None
    top_4: EffectivenessData = None
    top_5: EffectivenessData = None


@dataclass
class EfficiencyData(Serializable):
    """效率数据"""
    # 基本信息
    test_case_count: int = 0
    concurrency: int = 1

    # 文件大小
    total_file_size_kb: float = 0.0
    average_file_size_kb: float = 0.0

    # 时间效率
    total_duration: float = 0.0              # 总耗时（挂钟时间）
    average_duration: float = 0.0            # 平均耗时 = 总耗时 / case 数
    actual_average_duration: float = 0.0     # 单个 case 平均实际耗时
    throughput: float = 0.0                  # 吞吐量 (cases/s)

    # 阶段耗时分解
    duration_breakdown: dict = dataclasses.field(default_factory=dict)

    # 召回路线耗时分解 (hint/string/symbol/merge/supplement/total)
    recall_duration_breakdown: dict = dataclasses.field(default_factory=dict)


@dataclass
class PhaseCostData(Serializable):
    """单阶段成本数据"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    percentage: float = 0.0  # 占总成本的百分比


@dataclass
class CostData(Serializable):
    """成本数据"""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    average_cost: float = 0.0

    # 按阶段分解
    phase_breakdown: Dict[str, PhaseCostData] = dataclasses.field(default_factory=dict)


# ========== 单个测试用例的检查结果 ==========

@dataclass
class AnalysisResultCheck(Serializable):
    """单个测试用例的检查结果"""
    # 输入信息
    binary_name: str = None
    binary_path: str = None
    binary_size_kb: float = None
    binary_hash: str = None

    # 状态
    succeed: bool = True
    err_msg: str = None

    # Ground Truth
    ground_truth: List[str] = dataclasses.field(default_factory=list)

    # 特征匹配候选
    feature_match_candidates: List[str] = dataclasses.field(default_factory=list)

    # 最终结果
    final_result_libs: List[str] = dataclasses.field(default_factory=list)

    # 评估结果
    tp_libs: List[str] = dataclasses.field(default_factory=list)
    fp_libs: List[str] = dataclasses.field(default_factory=list)
    fn_libs: List[str] = dataclasses.field(default_factory=list)

    # 统计
    tp_count: int = 0
    fp_count: int = 0
    fn_count: int = 0

    # 状态标记
    perfect: bool = False  # TP>0 且 FP=0 且 FN=0
    has_fp: bool = False
    has_fn: bool = False


# ========== TPL Level Effectiveness（去重后的库级别效果）==========

@dataclass
class TPLLevelEffectiveness(Serializable):
    """TPL级别效果：去重后的整体效果"""
    effectiveness: EffectivenessData = None
    tp_libs: List[str] = dataclasses.field(default_factory=list)
    fp_libs: List[str] = dataclasses.field(default_factory=list)
    fn_libs: List[str] = dataclasses.field(default_factory=list)


# ========== 评估摘要 ==========

@dataclass
class EvaluationSummary(Serializable):
    """评估摘要：核心指标"""
    # 整体效果
    effectiveness: EffectivenessData = None

    # 特征匹配效果
    feature_matching: FeatureMatchingEffectiveness = None

    # 效率
    efficiency: EfficiencyData = None

    # 成本
    cost: CostData = None


# ========== 评估报告 ==========

@dataclass
class EvaluationReport(Serializable):
    """评估报告：主报告文件"""
    # 时间信息
    start_at: str = None
    finished_at: str = None
    evaluation_duration: float = 0.0

    # 配置
    evaluation_config: EvaluationConfig = None

    # 基准数据集信息
    benchmark_meta: BenchmarkMeta = None

    # 成功/失败统计
    succeed_count: int = 0
    failed_count: int = 0

    # 评估摘要
    summary: EvaluationSummary = None

    # 每个测试用例的检查结果
    results_check: List[AnalysisResultCheck] = dataclasses.field(default_factory=list)

    # 内部使用（不序列化到报告文件）
    _evaluation_results: List["AnalysisResult"] = dataclasses.field(default_factory=list)
    _benchmark: Benchmark = None

    def dump(self, output_dir: str):
        """
        保存评估报告到指定目录

        生成3个文件：
        1. evaluation_report.json - 主报告
        2. tpl_level_effectiveness.json - 库级别效果
        3. raw_results.json - 原始分析结果
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 1. 主报告
        report_data = {
            "start_at": self.start_at,
            "finished_at": self.finished_at,
            "evaluation_duration": self.evaluation_duration,
            "evaluation_config": self.evaluation_config.customer_serialize() if self.evaluation_config else None,
            "benchmark_meta": self.benchmark_meta.customer_serialize() if self.benchmark_meta else None,
            "succeed_count": self.succeed_count,
            "failed_count": self.failed_count,
            "summary": self.summary.customer_serialize() if self.summary else None,
            "results_check": [r.customer_serialize() for r in self.results_check],
        }
        report_path = os.path.join(output_dir, "evaluation_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        logger.info(f"主报告已保存: {report_path}")

        # 2. TPL 级别效果（从 summary 中提取，如果需要单独文件）
        # 这里我们计算去重后的整体效果
        tpl_effectiveness = self._calculate_tpl_level_effectiveness()
        tpl_path = os.path.join(output_dir, "tpl_level_effectiveness.json")
        with open(tpl_path, 'w', encoding='utf-8') as f:
            json.dump(tpl_effectiveness.customer_serialize(), f, indent=2, ensure_ascii=False)
        logger.info(f"TPL级别效果已保存: {tpl_path}")

        # 3. 原始结果
        raw_results = [r.customer_serialize() for r in self._evaluation_results] if self._evaluation_results else []
        raw_path = os.path.join(output_dir, "raw_results.json")
        with open(raw_path, 'w', encoding='utf-8') as f:
            json.dump(raw_results, f, indent=2, ensure_ascii=False)
        logger.info(f"原始结果已保存: {raw_path}")

    def _calculate_tpl_level_effectiveness(self) -> TPLLevelEffectiveness:
        """计算 TPL 级别效果（从 results_check 汇总）"""
        all_tp = set()
        all_fp = set()
        all_fn = set()

        for check in self.results_check:
            for lib in check.tp_libs:
                all_tp.add(lib.lower())
            for lib in check.fp_libs:
                all_fp.add(lib.lower())
            for lib in check.fn_libs:
                all_fn.add(lib.lower())

        tp = len(all_tp)
        fp = len(all_fp)
        fn = len(all_fn)

        precision = round(tp / (tp + fp) * 100, 2) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn) * 100, 2) if (tp + fn) > 0 else 0.0
        f1 = round(2 * precision * recall / (precision + recall), 2) if (precision + recall) > 0 else 0.0

        return TPLLevelEffectiveness(
            effectiveness=EffectivenessData(
                tp_count=tp, fp_count=fp, fn_count=fn,
                precision=precision, recall=recall, f1_score=f1
            ),
            tp_libs=sorted(all_tp),
            fp_libs=sorted(all_fp),
            fn_libs=sorted(all_fn),
        )

    @classmethod
    def load_from_file(cls, file_path: str) -> 'EvaluationReport':
        """从文件加载评估报告"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.init_from_dict(data)
