"""
TPL Detection Evaluator - 简化版

核心功能：
1. 运行测试用例，获取分析结果
2. 对比 Ground Truth，计算 TP/FP/FN
3. 计算评估指标：
   - 整体效果 (P/R/F1)
   - 特征匹配效果 (top_1 ~ top_5)
   - 效率 (耗时)
   - 成本 (token/费用)
"""
import copy
import os.path
import time
from typing import List, Optional

from loguru import logger

from app.interface import AnalysisResult
from app.services.tpl_detection.batch_workflow import BatchDetectionWorkflow
from app.services.tpl_detection.workflow import DetectionWorkflow
from evaluation.tpl_detection_evaluation.interface import (
    EvaluationConfig, Benchmark, EvaluationReport, AnalysisResultCheck,
    EffectivenessData, FeatureMatchingEffectiveness, EfficiencyData, CostData,
    PhaseCostData, EvaluationSummary
)


def _get_phase_attr(phase, attr, default=None):
    """
    兼容获取 PhaseRecord 属性（支持对象和字典两种形式）
    从 JSON 加载时 phase 是 dict，运行时是 PhaseRecord 对象
    """
    if phase is None:
        return default
    if isinstance(phase, dict):
        return phase.get(attr, default)
    return getattr(phase, attr, default)


class Evaluator:
    """
    TPL 检测评估器（简化版）

    使用方式:
        evaluator = Evaluator(config)

        # 方式1: 运行测试用例 + 评估
        evaluator.run_test_cases()
        evaluator.evaluate()
        evaluator.report.dump("output_dir")

        # 方式2: 从已保存的检测结果计算指标
        evaluator.load_results("report.json")
        evaluator.evaluate()
        evaluator.report.dump("output_dir")
    """

    def __init__(self, config: EvaluationConfig):
        self.config = config
        self.benchmark = Benchmark.load_from_json_file(config.benchmark_file)

        # 检测工作流
        self.workflow = DetectionWorkflow(
            # 特征召回配置
            retrieval_top_n=config.retrieval_top_n,
            hint_first=config.hint_first,
            # 召回路线开关
            enable_hint_recall=config.enable_hint_recall,
            enable_string_recall=config.enable_string_recall,
            enable_symbol_recall=config.enable_symbol_recall,
            symbol_use_imported=config.symbol_use_imported,
            # 过滤配置
            library_blacklist=config.library_blacklist,
            min_match_count_threshold=config.min_match_count_threshold,
            # 其他配置
            use_agent=config.use_agent,
            silent=config.silent,
            # 版本分析和说明生成开关
            enable_version_analysis=config.enable_version_analysis,
            enable_explanation_generation=config.enable_explanation_generation,
            # 验证阶段消融实验配置（6 个）
            ablation_all=config.ablation_all,
            ablation_no_s1=config.ablation_no_s1,
            ablation_no_s2=config.ablation_no_s2,
            ablation_no_s3=config.ablation_no_s3,
            ablation_no_s4=config.ablation_no_s4,
            ablation_no_cot=config.ablation_no_cot,
        )
        self.batch_workflow = BatchDetectionWorkflow(
            concurrency=config.concurrency,
            # 特征召回配置
            retrieval_top_n=config.retrieval_top_n,
            hint_first=config.hint_first,
            # 召回路线开关
            enable_hint_recall=config.enable_hint_recall,
            enable_string_recall=config.enable_string_recall,
            enable_symbol_recall=config.enable_symbol_recall,
            symbol_use_imported=config.symbol_use_imported,
            # 过滤配置
            library_blacklist=config.library_blacklist,
            min_match_count_threshold=config.min_match_count_threshold,
            # 其他配置
            use_agent=config.use_agent,
            silent=config.silent,
            # 版本分析和说明生成开关
            enable_version_analysis=config.enable_version_analysis,
            enable_explanation_generation=config.enable_explanation_generation,
            # 验证阶段消融实验配置（6 个）
            ablation_all=config.ablation_all,
            ablation_no_s1=config.ablation_no_s1,
            ablation_no_s2=config.ablation_no_s2,
            ablation_no_s3=config.ablation_no_s3,
            ablation_no_s4=config.ablation_no_s4,
            ablation_no_cot=config.ablation_no_cot,
        )

        # 评估报告
        self.report = EvaluationReport(
            evaluation_config=config,
            _benchmark=self.benchmark,
            benchmark_meta=self.benchmark.get_meta(),
        )

    # ========== 核心流程 ==========

    def _print_config(self, test_case_count: int, actual_count: int, not_exist_count: int):
        """打印评估配置信息"""
        print("\n" + "=" * 60)
        print("TPL Detection Evaluation")
        print("=" * 60)

        # Benchmark 信息
        print(f"\n【Benchmark】")
        print(f"  名称: {self.benchmark.name}")
        print(f"  版本: {self.benchmark.version}")
        print(f"  总测试用例数: {len(self.benchmark.test_cases)}")
        print(f"  覆盖库数量: {self.report.benchmark_meta.covered_library_num}")

        # 测试用例
        print(f"\n【测试用例】")
        print(f"  切片范围: [{self.config.slice_start}:{self.config.slice_end if self.config.slice_end != -1 else 'end'}]")
        print(f"  选中数量: {test_case_count}")
        print(f"  实际运行: {actual_count}")
        if not_exist_count > 0:
            print(f"  不存在: {not_exist_count}")

        # LLM 配置
        print(f"\n【LLM 配置】")
        print(f"  Provider: {self.config.llm_provider}")
        print(f"  Model: {self.config.llm_model_id}")
        print(f"  Input Price: ${self.config.input_token_price_per_1M}/1M tokens")
        print(f"  Cached Input Price: ${self.config.cached_input_token_price_per_1M}/1M tokens")
        print(f"  Output Price: ${self.config.output_token_price_per_1M}/1M tokens")

        # 召回配置
        print(f"\n【召回配置】")
        print(f"  召回 Top-N: {self.config.retrieval_top_n}")
        print(f"  Hint 优先: {self.config.hint_first}")
        print(f"  启用 Hint 路线: {self.config.enable_hint_recall}")
        print(f"  启用 String 路线: {self.config.enable_string_recall}")
        print(f"  启用 Symbol 路线: {self.config.enable_symbol_recall}")
        print(f"  Symbol 使用导入符号: {self.config.symbol_use_imported}")
        print(f"  最小匹配数阈值: {self.config.min_match_count_threshold if self.config.min_match_count_threshold else '默认(5)'}")
        if self.config.library_blacklist:
            print(f"  库黑名单: {self.config.library_blacklist}")

        # 运行配置
        print(f"\n【运行配置】")
        print(f"  并发数: {self.config.concurrency}")
        print(f"  使用 Agent: {self.config.use_agent}")
        print(f"  静默模式: {self.config.silent}")

        # 消融实验配置（如果有启用）
        ablation_flags = []
        if self.config.ablation_all:
            ablation_flags.append("-All")
        if self.config.ablation_no_s1:
            ablation_flags.append("-S1")
        if self.config.ablation_no_s2:
            ablation_flags.append("-S2")
        if self.config.ablation_no_s3:
            ablation_flags.append("-S3")
        if self.config.ablation_no_s4:
            ablation_flags.append("-S4")
        if self.config.ablation_no_cot:
            ablation_flags.append("-CoT")

        if ablation_flags:
            print(f"\n【消融实验】")
            print(f"  启用消融: {', '.join(ablation_flags)}")

        print("\n" + "=" * 60)
        print("开始评估...")
        print("=" * 60 + "\n")

    def run_test_cases(self, analyze_context: bool = False, specific_paths: List[str] = None):
        """运行测试用例，获取分析结果

        Args:
            analyze_context: 是否分析软件上下文
            specific_paths: 可选，指定要运行的测试用例路径列表（绝对路径）
                           如果提供，则忽略 slice_start/slice_end 配置
        """
        if specific_paths:
            # 使用指定的路径
            all_absolute_paths = specific_paths
            relative_paths = specific_paths  # 用于打印信息
        else:
            # 使用原有的切片逻辑
            slice_end = self.config.slice_end if self.config.slice_end != -1 else None
            relative_paths = [tc.test_binary.relative_path for tc in self.benchmark.test_cases][
                             self.config.slice_start:slice_end]
            all_absolute_paths = [os.path.join(self.config.test_case_dir, path) for path in relative_paths]

        absolute_paths = [path for path in all_absolute_paths if os.path.exists(path)]
        not_exist_paths = [path for path in all_absolute_paths if not os.path.exists(path)]

        # 打印配置信息
        self._print_config(
            test_case_count=len(relative_paths),
            actual_count=len(absolute_paths),
            not_exist_count=len(not_exist_paths)
        )

        if not_exist_paths:
            print(f"警告: 以下测试用例文件不存在: {not_exist_paths}")

        # 运行
        start_time = time.perf_counter()
        start_wall_time = time.time()  # 使用 time.time() 获取实际的 Unix 时间戳
        self.report.start_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_wall_time))

        context = None
        if analyze_context:
            logger.info("分析软件上下文...")
            context = self.workflow.analyze_context(self.config.test_case_dir)

        logger.info("开始运行测试用例")
        # absolute_paths = [p for p in absolute_paths if "zipcloak" in p]
        results = self.batch_workflow.run_batch(absolute_paths, software_context=context)

        total_time = time.perf_counter() - start_time
        self.report.finished_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        self.report._evaluation_results = results
        self.report.evaluation_duration = total_time

        logger.info(f"测试用例运行完成, 耗时: {total_time:.2f} seconds")

    def load_results(self, report_path: str):
        """从已有报告加载结果"""
        logger.info(f"从文件加载结果: {report_path}")

        # 加载原始结果文件
        import json
        # 检查是目录还是文件
        if os.path.isdir(report_path):
            raw_results_path = os.path.join(report_path, "raw_results.json")
        else:
            # 假设是旧格式的报告文件
            raw_results_path = report_path

        with open(raw_results_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 如果是旧格式，尝试从 evaluation_results 字段获取
        if isinstance(data, dict) and 'evaluation_results' in data:
            results_data = data['evaluation_results']
            self.report.start_at = data.get('start_at')
            self.report.finished_at = data.get('finished_at')
            self.report.evaluation_duration = data.get('evaluation_duration', 0.0)
        else:
            results_data = data

        # 反序列化
        self.report._evaluation_results = [AnalysisResult.init_from_dict(r) for r in results_data]

        logger.info(f"加载完成，共 {len(self.report._evaluation_results)} 条结果")

    def evaluate(self, ignore_failed_cases: bool = False):
        """
        评估结果

        流程:
        1. 对比 ground truth → TP/FP/FN
        2. 计算指标：效果、特征匹配效果、效率、成本
        """
        if not self.report._evaluation_results:
            raise ValueError("没有可评估的结果，请先运行 run_test_cases() 或 load_results()")

        logger.info("开始评估...")

        # 获取 benchmark 中的测试用例 sha256 集合
        benchmark_sha256_set = {tc.test_binary.sha256 for tc in self.benchmark.test_cases}

        # 过滤出在 benchmark 中的结果
        evaluation_results = [r for r in self.report._evaluation_results if r.binary_sha256 in benchmark_sha256_set]
        skipped_count = len(self.report._evaluation_results) - len(evaluation_results)
        if skipped_count > 0:
            logger.info(f"跳过了 {skipped_count} 个不在当前 benchmark 中的结果")

        if ignore_failed_cases:
            evaluation_results = [r for r in evaluation_results if r.error_message is None]

        # 1. 对比 ground truth
        logger.info("对比 ground truth...")
        results_check = self._compare_with_ground_truth(evaluation_results)

        # 2. 计算指标
        logger.info("计算指标...")

        # 2.1 整体效果
        effectiveness = self._cal_effectiveness(results_check)

        # 2.2 特征匹配效果
        feature_matching = self._cal_feature_matching_effectiveness(evaluation_results)

        # 2.3 效率
        efficiency = self._cal_efficiency(evaluation_results, self.report.evaluation_duration)

        # 2.4 成本
        cost = self._cal_cost(evaluation_results)

        # 3. 构建摘要
        summary = EvaluationSummary(
            effectiveness=effectiveness,
            feature_matching=feature_matching,
            efficiency=efficiency,
            cost=cost,
        )

        # 4. 保存到报告
        self.report.results_check = results_check
        self.report.summary = summary
        self.report.succeed_count = sum(1 for r in evaluation_results if r.error_message is None)
        self.report.failed_count = sum(1 for r in evaluation_results if r.error_message is not None)

        logger.info("评估完成")

        # 预览结果
        self._preview_results(summary, results_check)

    # ========== 对比 Ground Truth ==========

    def _compare_with_ground_truth(self, evaluation_results: List[AnalysisResult]) -> List[AnalysisResultCheck]:
        """对比检测结果与 Ground Truth，计算 TP/FP/FN

        注意：失败的测试用例（error_message 不为 None）会被跳过，不参与 P/R 计算
        """
        ground_truth_dict = {
            tc.test_binary.sha256: tc.reused_libraries
            for tc in self.benchmark.test_cases
        }
        file_size_dict = {
            tc.test_binary.sha256: tc.test_binary.file_size_kb
            for tc in self.benchmark.test_cases
        }

        results_check = []
        skipped_count = 0
        failed_count = 0
        for result in evaluation_results:
            # 跳过不在当前 benchmark 中的结果
            if result.binary_sha256 not in ground_truth_dict:
                skipped_count += 1
                continue

            # 跳过失败的测试用例，不参与 P/R 计算
            if result.error_message is not None:
                failed_count += 1
                continue

            gt_libs = ground_truth_dict.get(result.binary_sha256, [])
            check = self._check_single_result(result, gt_libs, file_size_dict)
            results_check.append(check)

        if skipped_count > 0:
            logger.info(f"跳过了 {skipped_count} 个不在当前 benchmark 中的结果")
        if failed_count > 0:
            logger.info(f"跳过了 {failed_count} 个失败的测试用例（不参与 P/R 计算）")

        return results_check

    def _check_single_result(self, result: AnalysisResult, gt_libs, file_size_dict) -> AnalysisResultCheck:
        """检查单个结果"""
        # 收集待对比的库：main_program + detected_libraries（不包括动态库）
        detected_libs_to_check = []
        if result.main_program:
            detected_libs_to_check.append(result.main_program)
        if result.detected_libraries:
            detected_libs_to_check.extend(result.detected_libraries)

        # 使用统一的匹配逻辑
        tp_libs, fp_libs, fn_libs = self._match_all(detected_libs_to_check, gt_libs)

        # 提取特征匹配候选
        feature_match_candidates = []
        if result.analysis_data and result.analysis_data.feature_match_candidates:
            feature_match_candidates = [c.library_name for c in result.analysis_data.feature_match_candidates]

        # 最终结果的库名称
        final_result_libs = []
        for lib in detected_libs_to_check:
            final_result_libs.append(lib.name or lib.component_name or 'unknown')

        return AnalysisResultCheck(
            binary_name=result.binary_name,
            binary_path=result.binary_path,
            binary_hash=result.binary_sha256,
            binary_size_kb=file_size_dict.get(result.binary_sha256, 0),
            succeed=result.error_message is None,
            err_msg=result.error_message,
            ground_truth=[lib.name for lib in gt_libs],
            feature_match_candidates=feature_match_candidates,
            final_result_libs=final_result_libs,
            tp_libs=tp_libs,
            fp_libs=fp_libs,
            fn_libs=fn_libs,
            tp_count=len(tp_libs),
            fp_count=len(fp_libs),
            fn_count=len(fn_libs),
            perfect=len(tp_libs) > 0 and len(fp_libs) == 0 and len(fn_libs) == 0,
            has_fp=len(fp_libs) > 0,
            has_fn=len(fn_libs) > 0,
        )

    # ========== 匹配逻辑 ==========

    def _normalize_lib_name(self, name: str) -> str:
        """标准化库名"""
        return name.lower().strip().replace('-', '_').replace('.', '_')

    # iptables项目的模块前缀
    IPTABLES_MODULE_PREFIXES = ['xt_', 'libxt_', 'ipt_', 'libipt_', 'ip6t_', 'libip6t_',
                                'ebt_', 'libebt_', 'arpt_', 'libarpt_', 'libip4tc', 'libip6tc', 'libiptc']

    def _is_same_library(self, detected_name: str, gt_lib) -> bool:
        """判断一个检测到的名称是否与 GT 库是同一个库"""
        if not detected_name:
            return False

        detected_normalized = self._normalize_lib_name(detected_name)
        gt_normalized = self._normalize_lib_name(gt_lib.name)

        # 直接匹配
        if detected_normalized == gt_normalized:
            return True

        # lib 前缀匹配
        if detected_normalized == self._normalize_lib_name('lib' + gt_lib.name):
            return True
        if self._normalize_lib_name('lib' + detected_name) == gt_normalized:
            return True

        # 别名匹配
        for other_name in gt_lib.other_names:
            if detected_normalized == self._normalize_lib_name(other_name):
                return True

        # 特殊规则：iptables模块前缀匹配
        if gt_lib.name == 'iptables':
            for prefix in self.IPTABLES_MODULE_PREFIXES:
                if detected_normalized.startswith(self._normalize_lib_name(prefix)):
                    return True

        return False

    def _match_detected_library(self, detected_lib, gt_lib) -> bool:
        """检测结果的 name 或 component_name 任一匹配即可"""
        if detected_lib.name and self._is_same_library(detected_lib.name, gt_lib):
            return True
        if detected_lib.component_name and self._is_same_library(detected_lib.component_name, gt_lib):
            return True
        return False

    def _is_invalid_lib_name(self, name: str) -> bool:
        """检查库名是否无效（null/unknown/unknown_program 等）"""
        if not name:
            return True
        name_lower = name.lower().strip()
        # unknown_program 表示 LLM 无法识别，不应算作 FP
        invalid_names = {'null', 'unknown', 'unknown_program', '{"null":null}', 'none', ''}
        return name_lower in invalid_names

    def _match_all(self, detected_libs: List, gt_libs: List):
        """
        遍历检测结果与 GT 列表进行匹配
        返回: (tp_libs, fp_libs, fn_libs) - 都是名称列表
        """
        matched_gt_indices = set()
        tp_libs, fp_libs = [], []

        for detected_lib in detected_libs:
            lib_name = detected_lib.name or ''

            # 跳过无效的库名（null/unknown 等）
            if self._is_invalid_lib_name(lib_name):
                continue

            display_name = detected_lib.name or detected_lib.component_name or 'unknown'

            matched = False
            for i, gt_lib in enumerate(gt_libs):
                if self._match_detected_library(detected_lib, gt_lib):
                    if i not in matched_gt_indices:
                        tp_libs.append(display_name)
                        matched_gt_indices.add(i)
                    matched = True
                    break

            if not matched:
                fp_libs.append(display_name)

        # FN: 未被匹配的 GT
        fn_libs = [gt_libs[i].name for i in range(len(gt_libs)) if i not in matched_gt_indices]

        return tp_libs, fp_libs, fn_libs

    # ========== 编译配置解析 ==========

    def _parse_compile_config(self, notes: str) -> str:
        """从 notes 中解析 compile_config"""
        import re
        if not notes:
            return "unknown"
        match = re.search(r'compile_config:\s*(\S+)', notes)
        if match:
            return match.group(1)
        return "unknown"

    def _normalize_config(self, config: str) -> str:
        """将 compile_config 标准化为 compiler+arch 格式"""
        if 'clang' in config:
            compiler = 'clang'
        elif 'gcc' in config:
            compiler = 'gcc'
        else:
            compiler = 'unknown'

        if 'arm' in config:
            arch = 'arm'
        elif 'x86_64' in config:
            arch = 'x86_64'
        else:
            arch = 'unknown'

        return f"{compiler}+{arch}"

    def _get_config_by_hash(self) -> dict:
        """构建 sha256 -> 编译配置 的映射"""
        sha256_to_config = {}
        for tc in self.benchmark.test_cases:
            sha256 = tc.test_binary.sha256
            notes = tc.test_binary.notes or ""
            raw_config = self._parse_compile_config(notes)
            normalized_config = self._normalize_config(raw_config)
            sha256_to_config[sha256] = normalized_config
        return sha256_to_config

    # ========== 结果预览 ==========

    def _preview_results(self, summary: EvaluationSummary, results_check: List[AnalysisResultCheck]):
        """预览评估结果"""
        eff = summary.effectiveness
        cost = summary.cost
        efficiency = summary.efficiency
        fm = summary.feature_matching

        print("\n" + "=" * 60)
        print("评估结果预览")
        print("=" * 60)

        # 基本统计
        total_count = self.report.succeed_count + self.report.failed_count
        success_rate = round(self.report.succeed_count / total_count * 100, 1) if total_count > 0 else 0
        print(f"\n【基本统计】")
        print(f"  测试用例: {total_count} 个")
        print(f"    - 成功: {self.report.succeed_count} 个 ({success_rate}%)")
        print(f"    - 失败: {self.report.failed_count} 个 ({round(100 - success_rate, 1)}%)")

        # 效果
        print(f"\n【检测效果】(基于 {self.report.succeed_count} 个成功用例)")
        print(f"  TP: {eff.tp_count}, FP: {eff.fp_count}, FN: {eff.fn_count}")
        print(f"  Precision: {eff.precision}%")
        print(f"  Recall:    {eff.recall}%")
        print(f"  F1-Score:  {eff.f1_score}%")

        # 特征匹配效果 - 打印 top 1-10, 20, 30, ..., 100
        print(f"\n【特征匹配效果】")
        # top 1-10
        for n in range(1, 11):
            data = self._cal_top_n_effectiveness(n)
            print(f"  top_{n}: P={data.precision}%, R={data.recall}%, F1={data.f1_score}%")
        # top 20, 30, ..., 100
        for n in range(20, 101, 10):
            data = self._cal_top_n_effectiveness(n)
            print(f"  top_{n}: P={data.precision}%, R={data.recall}%, F1={data.f1_score}%")

        # 效率
        print(f"\n【效率】")
        print(f"  测试用例数: {efficiency.test_case_count}")
        print(f"  并发数: {efficiency.concurrency}")
        print(f"  总耗时（挂钟时间）: {efficiency.total_duration:.2f}s")
        print(f"  平均耗时: {efficiency.average_duration:.2f}s/case")
        print(f"  单个 case 平均实际耗时: {efficiency.actual_average_duration:.2f}s/case")
        print(f"  吞吐量: {efficiency.throughput:.3f} cases/s ({efficiency.throughput * 60:.2f} cases/min)")

        # 成本
        print(f"\n【成本】")
        print(f"  输入 Token: {cost.total_input_tokens:,} (缓存: {cost.total_cache_read_tokens:,})")
        print(f"  输出 Token: {cost.total_output_tokens:,}")
        print(f"  总 Token: {cost.total_tokens:,}")
        print(f"  总成本: ${cost.total_cost:.4f}")
        print(f"  平均成本: ${cost.average_cost:.4f}/case")

        # 拆解分析（合并 token、成本、时间）
        if cost.phase_breakdown or efficiency.duration_breakdown:
            print(f"\n【拆解分析】")

            # 阶段名称映射
            phase_names = {
                "phase1_material_collection": "证据收集",
                "phase2_composition_analysis": "TPL 分析",
                "phase3_version_analysis": "版本分析",
                "phase4_explanation_generation": "说明生成",
            }

            # 计算总时间用于百分比
            total_duration = sum(efficiency.duration_breakdown.values()) if efficiency.duration_breakdown else 0

            # 表头
            print(f"  {'阶段':<12} {'Token':>12} {'占比':>8} {'成本':>10} {'占比':>8} {'时间':>10} {'占比':>8}")
            print(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*10} {'-'*8} {'-'*10} {'-'*8}")

            # 按顺序输出各阶段
            phase_order = [
                "phase1_material_collection",
                "phase2_composition_analysis",
                "phase3_version_analysis",
                "phase4_explanation_generation",
            ]

            for phase_key in phase_order:
                display_name = phase_names.get(phase_key, phase_key)

                # Token 和成本数据
                if phase_key in cost.phase_breakdown:
                    phase_cost = cost.phase_breakdown[phase_key]
                    tokens = phase_cost.total_tokens
                    token_pct = (tokens / cost.total_tokens * 100) if cost.total_tokens > 0 else 0
                    cost_val = phase_cost.cost
                    cost_pct = phase_cost.percentage
                else:
                    tokens = 0
                    token_pct = 0
                    cost_val = 0
                    cost_pct = 0

                # 时间数据
                duration = efficiency.duration_breakdown.get(phase_key, 0)
                duration_pct = (duration / total_duration * 100) if total_duration > 0 else 0

                print(f"  {display_name:<12} {tokens:>12,} {token_pct:>7.1f}% ${cost_val:>9.4f} {cost_pct:>7.1f}% {duration:>9.1f}s {duration_pct:>7.1f}%")

            # 合计行
            print(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*10} {'-'*8} {'-'*10} {'-'*8}")
            print(f"  {'合计':<12} {cost.total_tokens:>12,} {'100.0':>7}% ${cost.total_cost:>9.4f} {'100.0':>7}% {total_duration:>9.1f}s {'100.0':>7}%")

        # 召回路线耗时分解
        if efficiency.recall_duration_breakdown:
            print(f"\n【召回路线耗时】")
            recall_names = {
                "hint": "Hint 收集",
                "string": "String 召回",
                "symbol": "Symbol 召回",
                "merge": "结果合并",
                "supplement": "特征补充",
                "total": "召回总计",
            }
            recall_order = ["hint", "string", "symbol", "merge", "supplement", "total"]
            recall_total = efficiency.recall_duration_breakdown.get("total", 0)

            print(f"  {'路线':<12} {'总耗时':>10} {'平均':>10} {'占比':>8}")
            print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*8}")

            for key in recall_order:
                if key not in efficiency.recall_duration_breakdown:
                    continue
                duration = efficiency.recall_duration_breakdown[key]
                avg_duration = duration / efficiency.test_case_count if efficiency.test_case_count > 0 else 0
                pct = (duration / recall_total * 100) if recall_total > 0 and key != "total" else 100.0 if key == "total" else 0
                display_name = recall_names.get(key, key)
                print(f"  {display_name:<12} {duration:>9.2f}s {avg_duration:>9.3f}s {pct:>7.1f}%")

        # 按编译配置分组效果
        self._preview_by_config(results_check)

        print("\n" + "=" * 60)

    def _preview_by_config(self, results_check: List[AnalysisResultCheck]):
        """按编译配置分组输出效果（RQ1 表格数据）"""
        # 获取配置映射
        sha256_to_config = self._get_config_by_hash()

        # 按配置分组统计
        config_stats = {}  # config -> {'tp': 0, 'fp': 0, 'fn': 0, 'count': 0}

        for check in results_check:
            if not check.succeed:
                continue

            binary_hash = check.binary_hash
            config = sha256_to_config.get(binary_hash, "unknown")

            if config not in config_stats:
                config_stats[config] = {'tp': 0, 'fp': 0, 'fn': 0, 'count': 0}

            config_stats[config]['tp'] += check.tp_count
            config_stats[config]['fp'] += check.fp_count
            config_stats[config]['fn'] += check.fn_count
            config_stats[config]['count'] += 1

        # 如果只有一种配置或没有配置信息，跳过分组输出
        valid_configs = [c for c in config_stats.keys() if c != "unknown"]
        if len(valid_configs) <= 1:
            return

        # 计算各配置的 P/R/F1
        def calc_metrics(stats: dict) -> dict:
            tp, fp, fn = stats['tp'], stats['fp'], stats['fn']
            precision = round(tp / (tp + fp) * 100, 2) if (tp + fp) > 0 else 0.0
            recall = round(tp / (tp + fn) * 100, 2) if (tp + fn) > 0 else 0.0
            f1 = round(2 * precision * recall / (precision + recall), 2) if (precision + recall) > 0 else 0.0
            return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': precision, 'recall': recall, 'f1': f1, 'count': stats['count']}

        print(f"\n【按编译配置分组效果】")
        print(f"  {'配置':<20} {'Cases':<8} {'TP':<6} {'FP':<6} {'FN':<6} {'R':<8} {'P':<8} {'F1':<8}")
        print(f"  {'-'*20} {'-'*8} {'-'*6} {'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*8}")

        # 按指定顺序输出
        config_order = ['gcc+x86_64', 'clang+x86_64', 'gcc+arm']
        for config in config_order:
            if config in config_stats:
                m = calc_metrics(config_stats[config])
                print(f"  {config:<20} {m['count']:<8} {m['tp']:<6} {m['fp']:<6} {m['fn']:<6} {m['recall']:<8.2f} {m['precision']:<8.2f} {m['f1']:<8.2f}")

        # 输出未在列表中的配置
        for config in config_stats.keys():
            if config not in config_order and config != "unknown":
                m = calc_metrics(config_stats[config])
                print(f"  {config:<20} {m['count']:<8} {m['tp']:<6} {m['fp']:<6} {m['fn']:<6} {m['recall']:<8.2f} {m['precision']:<8.2f} {m['f1']:<8.2f}")

    # ========== 计算指标 ==========

    def _cal_effectiveness(self, results_check: List[AnalysisResultCheck]) -> EffectivenessData:
        """计算整体效果 (P/R/F1)"""
        tp = sum(c.tp_count for c in results_check)
        fp = sum(c.fp_count for c in results_check)
        fn = sum(c.fn_count for c in results_check)

        precision = round(tp / (tp + fp) * 100, 2) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn) * 100, 2) if (tp + fn) > 0 else 0.0
        f1 = round(2 * precision * recall / (precision + recall), 2) if (precision + recall) > 0 else 0.0

        return EffectivenessData(
            tp_count=tp, fp_count=fp, fn_count=fn,
            precision=precision, recall=recall, f1_score=f1
        )

    def _cal_top_n_effectiveness(self, n: int) -> EffectivenessData:
        """
        计算 top_n 的特征匹配效果

        注意：top_n 指的是从合并后的候选列表中取前 n 个
        合并列表已经按 Round-Robin 方式轮询 Hint/String/Symbol 三路召回结果
        """
        # 获取每个测试用例的 GT
        gt_libs_by_sha256 = {}
        for tc in self.benchmark.test_cases:
            gt_libs_by_sha256[tc.test_binary.sha256] = tc.reused_libraries

        total_tp, total_fp, total_fn = 0, 0, 0

        for r in self.report._evaluation_results:
            # 跳过不在当前 benchmark 中的结果
            if r.binary_sha256 not in gt_libs_by_sha256:
                continue
            gt_libs = gt_libs_by_sha256[r.binary_sha256]

            # 获取特征匹配候选：从合并后的列表中取前 n 个
            candidates = []
            if r.analysis_data and r.analysis_data.feature_match_candidates:
                candidates = r.analysis_data.feature_match_candidates[:n]

            # 计算 TP/FP/FN
            matched_gt_indices = set()
            tp, fp = 0, 0

            for candidate in candidates:
                candidate_name = candidate.library_name
                if not candidate_name or candidate_name.startswith('gcc'):
                    continue

                matched = False
                for i, gt_lib in enumerate(gt_libs):
                    if self._is_same_library(candidate_name, gt_lib):
                        if i not in matched_gt_indices:
                            tp += 1
                            matched_gt_indices.add(i)
                        matched = True
                        break

                if not matched:
                    fp += 1

            fn = len(gt_libs) - len(matched_gt_indices)

            total_tp += tp
            total_fp += fp
            total_fn += fn

        precision = round(total_tp / (total_tp + total_fp) * 100, 2) if (total_tp + total_fp) > 0 else 0.0
        recall = round(total_tp / (total_tp + total_fn) * 100, 2) if (total_tp + total_fn) > 0 else 0.0
        f1 = round(2 * precision * recall / (precision + recall), 2) if (precision + recall) > 0 else 0.0

        return EffectivenessData(
            tp_count=total_tp, fp_count=total_fp, fn_count=total_fn,
            precision=precision, recall=recall, f1_score=f1
        )

    def _cal_feature_matching_effectiveness(self, evaluation_results: List[AnalysisResult]) -> FeatureMatchingEffectiveness:
        """
        计算特征匹配效果 (top_1 ~ top_5)

        逻辑：
        - 只使用特征匹配候选（不经过LLM）作为检测结果
        - 分别计算 top_1, top_2, ..., top_5 的效果
        - top_n 指的是从合并后的候选列表中取前 n 个
        - 合并列表已经按 Round-Robin 方式轮询 Hint/String/Symbol 三路召回结果
        """
        # 获取每个测试用例的 GT
        gt_libs_by_sha256 = {}
        for tc in self.benchmark.test_cases:
            gt_libs_by_sha256[tc.test_binary.sha256] = tc.reused_libraries

        def cal_effectiveness_for_top_n(n: int) -> EffectivenessData:
            """计算 top_n 的效果（从合并列表取前 n 个）"""
            total_tp, total_fp, total_fn = 0, 0, 0

            for r in evaluation_results:
                # 跳过不在当前 benchmark 中的结果
                if r.binary_sha256 not in gt_libs_by_sha256:
                    continue
                gt_libs = gt_libs_by_sha256[r.binary_sha256]

                # 获取特征匹配候选：从合并后的列表中取前 n 个
                candidates = []
                if r.analysis_data and r.analysis_data.feature_match_candidates:
                    candidates = r.analysis_data.feature_match_candidates[:n]

                # 计算 TP/FP/FN
                matched_gt_indices = set()
                tp, fp = 0, 0

                for candidate in candidates:
                    candidate_name = candidate.library_name
                    if not candidate_name or candidate_name.startswith('gcc'):
                        continue

                    matched = False
                    for i, gt_lib in enumerate(gt_libs):
                        if self._is_same_library(candidate_name, gt_lib):
                            if i not in matched_gt_indices:
                                tp += 1
                                matched_gt_indices.add(i)
                            matched = True
                            break

                    if not matched:
                        fp += 1

                fn = len(gt_libs) - len(matched_gt_indices)

                total_tp += tp
                total_fp += fp
                total_fn += fn

            precision = round(total_tp / (total_tp + total_fp) * 100, 2) if (total_tp + total_fp) > 0 else 0.0
            recall = round(total_tp / (total_tp + total_fn) * 100, 2) if (total_tp + total_fn) > 0 else 0.0
            f1 = round(2 * precision * recall / (precision + recall), 2) if (precision + recall) > 0 else 0.0

            return EffectivenessData(
                tp_count=total_tp, fp_count=total_fp, fn_count=total_fn,
                precision=precision, recall=recall, f1_score=f1
            )

        return FeatureMatchingEffectiveness(
            top_1=cal_effectiveness_for_top_n(1),
            top_2=cal_effectiveness_for_top_n(2),
            top_3=cal_effectiveness_for_top_n(3),
            top_4=cal_effectiveness_for_top_n(4),
            top_5=cal_effectiveness_for_top_n(5),
        )

    def _cal_efficiency(self, evaluation_results: List[AnalysisResult], evaluation_duration: float) -> EfficiencyData:
        """效率分析"""
        valid_results = [r for r in evaluation_results if r.analysis_data]
        test_case_count = len(evaluation_results)

        # 文件大小
        total_size = sum(r.analysis_data.target_binary.file_size_kb for r in valid_results if r.analysis_data.target_binary)
        avg_size = total_size / len(valid_results) if valid_results else 0.0

        # 平均耗时 = 总耗时 / case 数
        avg_duration = evaluation_duration / test_case_count if test_case_count else 0.0

        # 计算单个 case 平均实际耗时（从每个 case 的 phases 累加）
        case_durations = []
        for r in valid_results:
            if r.analysis_data.tpl_analysis_phases:
                case_duration = sum(_get_phase_attr(phase, 'duration', 0.0) for phase in r.analysis_data.tpl_analysis_phases.values())
                case_durations.append(case_duration)
        actual_avg_duration = sum(case_durations) / len(case_durations) if case_durations else 0.0

        # 吞吐量 (cases/s)
        throughput = test_case_count / evaluation_duration if evaluation_duration > 0 else 0.0

        # 从 tpl_analysis_phases 计算步骤时间分解
        duration_breakdown = {}
        for r in valid_results:
            if not r.analysis_data.tpl_analysis_phases:
                continue
            for phase_name, phase_record in r.analysis_data.tpl_analysis_phases.items():
                duration_breakdown[phase_name] = duration_breakdown.get(phase_name, 0.0) + _get_phase_attr(phase_record, 'duration', 0.0)

        # 从 phase1 的 output 中提取召回路线耗时
        recall_duration_breakdown = {}
        for r in valid_results:
            if not r.analysis_data.tpl_analysis_phases:
                continue
            phase1 = r.analysis_data.tpl_analysis_phases.get("phase1_material_collection")
            phase1_output = _get_phase_attr(phase1, 'output', {})
            if phase1 and phase1_output and "recall_durations" in phase1_output:
                recall_durations = phase1_output["recall_durations"]
                for key, value in recall_durations.items():
                    recall_duration_breakdown[key] = recall_duration_breakdown.get(key, 0.0) + value

        return EfficiencyData(
            test_case_count=test_case_count,
            concurrency=self.config.concurrency,
            total_file_size_kb=total_size,
            average_file_size_kb=avg_size,
            total_duration=evaluation_duration,
            average_duration=avg_duration,
            actual_average_duration=actual_avg_duration,
            throughput=throughput,
            duration_breakdown=duration_breakdown,
            recall_duration_breakdown=recall_duration_breakdown,
        )

    def _cal_cost(self, evaluation_results: List[AnalysisResult]) -> CostData:
        """成本分析"""
        input_price = self.config.input_token_price_per_1M
        cached_price = self.config.cached_input_token_price_per_1M
        output_price = self.config.output_token_price_per_1M

        # 按阶段统计
        phase_stats = {}  # phase_name -> {input, output, cached}

        valid_results = [r for r in evaluation_results if r.analysis_data and r.analysis_data.tpl_analysis_phases]

        for r in valid_results:
            for phase_name, phase_record in r.analysis_data.tpl_analysis_phases.items():
                if phase_name not in phase_stats:
                    phase_stats[phase_name] = {"input": 0, "output": 0, "cached": 0}
                llm_calls = _get_phase_attr(phase_record, 'llm_calls', [])
                for llm_call in llm_calls:
                    phase_stats[phase_name]["input"] += llm_call.get('input_tokens', 0) or 0
                    phase_stats[phase_name]["output"] += llm_call.get('output_tokens', 0) or 0
                    phase_stats[phase_name]["cached"] += llm_call.get('cache_read_tokens', 0) or 0

        # 计算总量
        total_input = sum(s["input"] for s in phase_stats.values())
        total_output = sum(s["output"] for s in phase_stats.values())
        total_cached = sum(s["cached"] for s in phase_stats.values())

        # 计算总成本
        uncached_input = total_input - total_cached
        total_cost = (
            uncached_input / 1_000_000 * input_price +
            total_cached / 1_000_000 * cached_price +
            total_output / 1_000_000 * output_price
        )
        avg_cost = total_cost / len(evaluation_results) if evaluation_results else 0.0

        # 计算每个阶段的成本和占比
        phase_breakdown = {}
        for phase_name, stats in phase_stats.items():
            phase_uncached = stats["input"] - stats["cached"]
            phase_cost = (
                phase_uncached / 1_000_000 * input_price +
                stats["cached"] / 1_000_000 * cached_price +
                stats["output"] / 1_000_000 * output_price
            )
            percentage = (phase_cost / total_cost * 100) if total_cost > 0 else 0.0

            phase_breakdown[phase_name] = PhaseCostData(
                input_tokens=stats["input"],
                output_tokens=stats["output"],
                cache_read_tokens=stats["cached"],
                total_tokens=stats["input"] + stats["output"],
                cost=round(phase_cost, 6),
                percentage=round(percentage, 2),
            )

        return CostData(
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cache_read_tokens=total_cached,
            total_tokens=total_input + total_output,
            total_cost=round(total_cost, 6),
            average_cost=round(avg_cost, 6),
            phase_breakdown=phase_breakdown,
        )
