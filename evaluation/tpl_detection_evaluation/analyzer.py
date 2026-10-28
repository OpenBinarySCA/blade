"""
评估结果分析器

提供四个核心分析功能：

1. analyze_topn_metrics()
   - 分析不同 Top-N 参数下检索阶段的 P/R/F1
   - 生成 Top-N vs P/R/F1 折线图
   - 用于确定最佳 Top-N 参数

2. analyze_retrieval_contribution()
   - 检索阶段消融分析：对比 String-only / Symbol-only / Combined 的效果
   - 用于分析两种特征类型的贡献度

3. analyze_failure_cases()
   - 分析最终检测结果的 FN（漏报）和 FP（误报）
   - FN 分类：检索失败 vs 验证误排除
   - 输出失败案例列表和测试用例路径

4. analyze_by_config()
   - 按编译配置分组统计 P/R/F1
   - 支持 gcc+x86_64, clang+x86_64, gcc+arm 三种配置
   - 生成论文 RQ1 表格所需数据
"""
import json
import os
from typing import Dict, List, Optional, Any

from loguru import logger


# =============================================================================
# 1. Top-N 指标分析
# =============================================================================

def analyze_topn_metrics(
    raw_results_path: str,
    benchmark_path: str,
    max_top_n: int = 0,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    分析不同 Top-N 参数下检索阶段的 P/R/F1

    【背景】
    检测系统分为两个阶段：
    1. 检索阶段：通过特征匹配（string + symbol）召回候选库，取 Top-N
    2. 验证阶段：LLM 对候选库进行验证

    本函数分析【检索阶段】在不同 Top-N 下的效果。

    【功能】
    1. 计算 Top-1 到 Top-N 的 Precision/Recall/F1
    2. 生成 Top-N vs P/R/F1 折线图（用于论文）
    3. 分析哪些 GT 库完全无法被召回

    【用途】
    - 确定最佳 Top-N 参数（平衡召回率和候选数量）
    - 生成论文图表

    Args:
        raw_results_path: raw_results.json 文件路径
        benchmark_path: benchmark JSON 文件路径（包含 GT 信息）
        max_top_n: 最大 Top-N（0 表示使用所有候选）
        output_dir: 输出目录（保存图片和报告）

    Returns:
        Dict 包含各 Top-N 的指标和未召回库列表
    """
    from app.interface import AnalysisResult
    from evaluation.tpl_detection_evaluation.interface import Benchmark

    # ========== 1. 加载数据 ==========
    logger.info(f"加载原始结果: {raw_results_path}")
    with open(raw_results_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    results = [AnalysisResult.init_from_dict(r) for r in raw_data]
    logger.info(f"加载了 {len(results)} 条结果")

    logger.info(f"加载 Benchmark: {benchmark_path}")
    benchmark = Benchmark.load_from_json_file(benchmark_path)
    tc_by_sha256 = {tc.test_binary.sha256: tc for tc in benchmark.test_cases}

    # ========== 2. 辅助函数 ==========
    def normalize_name(name: str) -> str:
        return name.lower().strip().replace('-', '_').replace('.', '_')

    def is_lib_match(lib_name: str, candidate_name: str) -> bool:
        if not lib_name or not candidate_name:
            return False
        n1, n2 = normalize_name(lib_name), normalize_name(candidate_name)
        if n1 == n2:
            return True
        if normalize_name('lib' + lib_name) == n2 or n1 == normalize_name('lib' + candidate_name):
            return True
        return False

    # ========== 3. 预处理 ==========
    processed_results = []
    actual_max_candidates = 0

    for result in results:
        sha256 = result.binary_sha256
        if sha256 not in tc_by_sha256:
            continue

        tc = tc_by_sha256[sha256]

        # 直接使用合并排序后的候选列表（保持原有顺序）
        all_candidates = []
        if result.analysis_data and result.analysis_data.feature_match_candidates:
            for c in result.analysis_data.feature_match_candidates:
                if c.library_name:
                    all_candidates.append(c.library_name)

        actual_max_candidates = max(actual_max_candidates, len(all_candidates))

        gt_libs = [{
            'name': gt_lib.name,
            'vendor': gt_lib.vendor,
            'repository': gt_lib.repository,
            'other_names': gt_lib.other_names or [],
        } for gt_lib in tc.reused_libraries]

        processed_results.append({
            'binary_name': result.binary_name,
            'binary_sha256': sha256,
            'candidates': all_candidates,  # 合并后的候选列表
            'gt_libs': gt_libs,
        })

    effective_max_top_n = actual_max_candidates if max_top_n <= 0 else min(max_top_n, actual_max_candidates)
    logger.info(f"实际最大候选数: {actual_max_candidates}, 有效 max_top_n: {effective_max_top_n}")

    # ========== 4. 计算各 Top-N 的指标 ==========
    def calc_metrics_for_top_n(n: int) -> Dict[str, float]:
        total_tp, total_fp, total_fn = 0, 0, 0
        for pr in processed_results:
            # 直接取合并排序后的前 N 个候选
            candidates_n = pr['candidates'][:n]
            gt_libs = pr['gt_libs']
            matched_gt_indices = set()
            tp, fp = 0, 0

            for candidate_name in candidates_n:
                if not candidate_name or candidate_name.lower() in ('null', 'unknown', 'none'):
                    continue
                if candidate_name.lower().startswith('gcc'):
                    continue

                matched = False
                for i, gt_lib in enumerate(gt_libs):
                    if is_lib_match(gt_lib['name'], candidate_name):
                        if i not in matched_gt_indices:
                            tp += 1
                            matched_gt_indices.add(i)
                        matched = True
                        break
                    for alias in gt_lib['other_names']:
                        if is_lib_match(alias, candidate_name):
                            if i not in matched_gt_indices:
                                tp += 1
                                matched_gt_indices.add(i)
                            matched = True
                            break
                    if matched:
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

        return {'top_n': n, 'tp': total_tp, 'fp': total_fp, 'fn': total_fn,
                'precision': precision, 'recall': recall, 'f1': f1}

    top_n_metrics = [calc_metrics_for_top_n(n) for n in range(1, effective_max_top_n + 1)]

    # ========== 5. 打印结果 ==========
    print("\n" + "=" * 70)
    print("Top-N 指标分析 (Top-N Metrics Analysis)")
    print("=" * 70)
    print(f"\n{'Top-N':<8} {'TP':<8} {'FP':<8} {'FN':<8} {'Precision':<12} {'Recall':<12} {'F1-Score':<12}")
    print("-" * 70)
    for m in top_n_metrics:
        print(f"{m['top_n']:<8} {m['tp']:<8} {m['fp']:<8} {m['fn']:<8} {m['precision']:<12.2f} {m['recall']:<12.2f} {m['f1']:<12.2f}")

    # ========== 6. 生成折线图 ==========
    if output_dir:
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')

            # 放大字号，适应单栏论文
            plt.rcParams.update({
                'font.family': 'serif', 'font.serif': ['Times New Roman', 'DejaVu Serif'],
                'font.size': 24, 'axes.labelsize': 26, 'axes.titlesize': 28,
                'legend.fontsize': 22, 'xtick.labelsize': 22, 'ytick.labelsize': 22,
                'figure.dpi': 300, 'savefig.dpi': 300,
                'axes.grid': True, 'grid.alpha': 0.3, 'grid.linestyle': '--',
            })

            fig, ax = plt.subplots(figsize=(12, 4.5))  # 更宽的比例，适合单栏论文
            top_ns = [m['top_n'] for m in top_n_metrics]
            precisions = [m['precision'] for m in top_n_metrics]
            recalls = [m['recall'] for m in top_n_metrics]
            f1s = [m['f1'] for m in top_n_metrics]

            ax.plot(top_ns, precisions, 'o-', color='#2E86AB', label='Precision', markersize=5, linewidth=2.5)
            ax.plot(top_ns, recalls, 's-', color='#A23B72', label='Recall', markersize=5, linewidth=2.5)
            ax.plot(top_ns, f1s, '^-', color='#F18F01', label='F1-Score', markersize=5, linewidth=2.5)

            # 在 Top-N = 10 处画垂直虚线并标注值
            highlight_n = 10
            if highlight_n <= effective_max_top_n:
                ax.axvline(x=highlight_n, color='gray', linestyle='--', linewidth=1.5, alpha=0.7)

                # 获取 Top-10 对应的值
                idx = highlight_n - 1  # 索引从 0 开始
                p_val = precisions[idx]
                r_val = recalls[idx]
                f1_val = f1s[idx]

                # 在数据点旁边添加标签
                offset_x = 1.3  # 水平偏移
                # 蓝色
                ax.annotate(f'{p_val:.2f}%', xy=(highlight_n, p_val), xytext=(highlight_n + offset_x - 11, p_val - 8),
                           fontsize=20, color='#2E86AB', fontweight='bold')
                # 紫色
                ax.annotate(f'{r_val:.2f}%', xy=(highlight_n, r_val), xytext=(highlight_n + offset_x, r_val - 12),
                           fontsize=20, color='#A23B72', fontweight='bold')
                # 黄色
                ax.annotate(f'{f1_val:.2f}%', xy=(highlight_n, f1_val), xytext=(highlight_n + offset_x, f1_val + 5),
                           fontsize=20, color='#F18F01', fontweight='bold')

            ax.set_xlabel('Top-N')
            ax.set_ylabel('Score (%)')
            ax.legend(loc='best', frameon=True, fancybox=False, edgecolor='black')
            ax.set_xlim(0, effective_max_top_n + 1)
            ax.set_ylim(0, 105)

            # x轴每10标注一次，y轴每20标注一次
            import numpy as np
            xticks = np.arange(0, effective_max_top_n + 1, 10)
            if xticks[0] == 0:
                xticks = xticks[1:]  # 去掉0，从10开始
            ax.set_xticks(xticks)
            ax.set_yticks(np.arange(0, 110, 20))

            plt.tight_layout()
            os.makedirs(output_dir, exist_ok=True)
            plt.savefig(os.path.join(output_dir, 'topn_metrics.pdf'), format='pdf', bbox_inches='tight', pad_inches=0)
            plt.savefig(os.path.join(output_dir, 'topn_metrics.png'), format='png', bbox_inches='tight', pad_inches=0)
            plt.close()
            logger.info(f"图片已保存到 {output_dir}")
        except Exception as e:
            logger.warning(f"生成图片失败: {e}")

    # ========== 7. 分析未召回的库 ==========
    print(f"\n" + "=" * 70)
    print(f"Top-{effective_max_top_n} 未召回库分析")
    print("=" * 70)

    gt_lib_stats: Dict[str, Dict] = {}
    for pr in processed_results:
        candidates_n = pr['candidates'][:effective_max_top_n]
        for gt_lib in pr['gt_libs']:
            lib_name = gt_lib['name']
            if lib_name not in gt_lib_stats:
                gt_lib_stats[lib_name] = {
                    'name': lib_name, 'vendor': gt_lib['vendor'], 'repository': gt_lib['repository'],
                    'other_names': gt_lib['other_names'], 'occurrences': [], 'recalled_count': 0, 'total_count': 0,
                }

            recalled = any(is_lib_match(lib_name, c) or any(is_lib_match(a, c) for a in gt_lib['other_names'])
                          for c in candidates_n)
            gt_lib_stats[lib_name]['occurrences'].append({'binary_name': pr['binary_name'], 'recalled': recalled})
            gt_lib_stats[lib_name]['total_count'] += 1
            if recalled:
                gt_lib_stats[lib_name]['recalled_count'] += 1

    unrecalled_libs = sorted([s for s in gt_lib_stats.values() if s['recalled_count'] == 0],
                            key=lambda x: x['total_count'], reverse=True)
    print(f"\n【摘要】")
    print(f"  GT 库总数（去重）: {len(gt_lib_stats)}")
    print(f"  完全未召回: {len(unrecalled_libs)} ({round(len(unrecalled_libs) / len(gt_lib_stats) * 100, 2) if gt_lib_stats else 0}%)")

    if unrecalled_libs:
        print(f"\n【完全未召回的库 (共 {len(unrecalled_libs)} 个)】")
        for lib in unrecalled_libs[:15]:
            print(f"  - {lib['name']} (出现 {lib['total_count']} 次)")

    print("\n" + "=" * 70)

    # ========== 8. 保存报告 ==========
    report = {
        'analysis_params': {'max_top_n': max_top_n, 'effective_max_top_n': effective_max_top_n},
        'top_n_metrics': top_n_metrics,
        'unrecalled_libraries': unrecalled_libs,
    }
    if output_dir:
        with open(os.path.join(output_dir, 'topn_analysis.json'), 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    return report


# =============================================================================
# 2. 检索阶段贡献分析（String vs Symbol 消融）
# =============================================================================

def analyze_retrieval_contribution(
    raw_results_path: str,
    benchmark_path: str,
    max_top_n: int = 10,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    检索阶段消融分析：对比 String-only / Symbol-only / Combined 的效果

    【背景】
    检索阶段使用两种特征进行匹配：
    1. String features：从二进制中提取的字符串
    2. Symbol features：从二进制中提取的符号名

    本函数分析这两种特征各自的贡献度。

    【功能】
    1. 计算只用 String 特征的 P/R/F1
    2. 计算只用 Symbol 特征的 P/R/F1
    3. 计算两者合并的 P/R/F1
    4. 生成对比图表

    【用途】
    - 分析两种特征的贡献度
    - 生成论文消融实验表格

    Args:
        raw_results_path: raw_results.json 文件路径
        benchmark_path: benchmark JSON 文件路径
        max_top_n: 最大 Top-N（默认 10）
        output_dir: 输出目录（保存图片和报告）

    Returns:
        Dict 包含三种配置的指标对比
    """
    from app.interface import AnalysisResult
    from evaluation.tpl_detection_evaluation.interface import Benchmark

    # ========== 1. 加载数据 ==========
    logger.info(f"加载原始结果: {raw_results_path}")
    with open(raw_results_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    results = [AnalysisResult.init_from_dict(r) for r in raw_data]

    logger.info(f"加载 Benchmark: {benchmark_path}")
    benchmark = Benchmark.load_from_json_file(benchmark_path)
    tc_by_sha256 = {tc.test_binary.sha256: tc for tc in benchmark.test_cases}

    # ========== 2. 辅助函数 ==========
    def normalize_name(name: str) -> str:
        return name.lower().strip().replace('-', '_').replace('.', '_')

    def is_lib_match(lib_name: str, candidate_name: str) -> bool:
        if not lib_name or not candidate_name:
            return False
        n1, n2 = normalize_name(lib_name), normalize_name(candidate_name)
        if n1 == n2:
            return True
        if normalize_name('lib' + lib_name) == n2 or n1 == normalize_name('lib' + candidate_name):
            return True
        return False

    # ========== 3. 预处理 ==========
    processed_results = []
    for result in results:
        sha256 = result.binary_sha256
        if sha256 not in tc_by_sha256:
            continue

        tc = tc_by_sha256[sha256]
        string_candidates, symbol_candidates = [], []
        if result.analysis_data and result.analysis_data.feature_match_candidates:
            for c in result.analysis_data.feature_match_candidates:
                if not c.library_name:
                    continue
                if c.match_type == "string_feature":
                    string_candidates.append(c.library_name)
                elif c.match_type == "symbol_feature":
                    symbol_candidates.append(c.library_name)

        gt_libs = [{'name': gt_lib.name, 'other_names': gt_lib.other_names or []}
                   for gt_lib in tc.reused_libraries]

        processed_results.append({
            'string_candidates': string_candidates,
            'symbol_candidates': symbol_candidates,
            'gt_libs': gt_libs,
        })

    # ========== 4. 计算指标 ==========
    def calc_metrics(candidates_list: List[List[str]], gt_libs_list: List[List[Dict]], n: int) -> Dict:
        total_tp, total_fp, total_fn = 0, 0, 0
        for candidates_full, gt_libs in zip(candidates_list, gt_libs_list):
            candidates_n = candidates_full[:n]
            matched_gt_indices = set()
            tp, fp = 0, 0

            for candidate_name in candidates_n:
                if not candidate_name or candidate_name.lower() in ('null', 'unknown', 'none'):
                    continue
                if candidate_name.lower().startswith('gcc'):
                    continue

                matched = False
                for i, gt_lib in enumerate(gt_libs):
                    if is_lib_match(gt_lib['name'], candidate_name):
                        if i not in matched_gt_indices:
                            tp += 1
                            matched_gt_indices.add(i)
                        matched = True
                        break
                    for alias in gt_lib['other_names']:
                        if is_lib_match(alias, candidate_name):
                            if i not in matched_gt_indices:
                                tp += 1
                                matched_gt_indices.add(i)
                            matched = True
                            break
                    if matched:
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

        return {'tp': total_tp, 'fp': total_fp, 'fn': total_fn,
                'precision': precision, 'recall': recall, 'f1': f1}

    # 准备三种配置的数据
    string_only = [pr['string_candidates'] for pr in processed_results]
    symbol_only = [pr['symbol_candidates'] for pr in processed_results]
    combined = [pr['string_candidates'] + pr['symbol_candidates'] for pr in processed_results]
    gt_libs_list = [pr['gt_libs'] for pr in processed_results]

    ablation_results = {'string_only': [], 'symbol_only': [], 'combined': []}
    for n in range(1, max_top_n + 1):
        ablation_results['string_only'].append({'top_n': n, **calc_metrics(string_only, gt_libs_list, n)})
        ablation_results['symbol_only'].append({'top_n': n, **calc_metrics(symbol_only, gt_libs_list, n)})
        ablation_results['combined'].append({'top_n': n, **calc_metrics(combined, gt_libs_list, n)})

    # ========== 5. 打印结果 ==========
    print("\n" + "=" * 90)
    print("检索阶段贡献分析 (Retrieval Contribution Analysis)")
    print("=" * 90)
    print(f"\n{'Top-N':<8} {'String Only':<25} {'Symbol Only':<25} {'Combined':<25}")
    print(f"{'':8} {'P / R / F1':<25} {'P / R / F1':<25} {'P / R / F1':<25}")
    print("-" * 90)

    for i in range(max_top_n):
        n = i + 1
        s, y, c = ablation_results['string_only'][i], ablation_results['symbol_only'][i], ablation_results['combined'][i]
        print(f"{n:<8} {s['precision']:.1f} / {s['recall']:.1f} / {s['f1']:.1f}{'':8}"
              f"{y['precision']:.1f} / {y['recall']:.1f} / {y['f1']:.1f}{'':8}"
              f"{c['precision']:.1f} / {c['recall']:.1f} / {c['f1']:.1f}")

    print(f"\n【Recall 对比】")
    print(f"{'Top-N':<8} {'String Only':<15} {'Symbol Only':<15} {'Combined':<15}")
    print("-" * 53)
    for i in range(max_top_n):
        s, y, c = ablation_results['string_only'][i], ablation_results['symbol_only'][i], ablation_results['combined'][i]
        print(f"{i+1:<8} {s['recall']:<15.2f} {y['recall']:<15.2f} {c['recall']:<15.2f}")

    print("\n" + "=" * 90)

    # ========== 6. 生成图片 ==========
    if output_dir:
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')

            plt.rcParams.update({
                'font.family': 'serif', 'font.serif': ['Times New Roman', 'DejaVu Serif'],
                'font.size': 11, 'axes.labelsize': 12, 'legend.fontsize': 10,
                'figure.dpi': 300, 'savefig.dpi': 300,
                'axes.grid': True, 'grid.alpha': 0.3, 'grid.linestyle': '--',
            })

            fig, ax = plt.subplots(figsize=(8, 5))
            top_ns = list(range(1, max_top_n + 1))
            ax.plot(top_ns, [m['recall'] for m in ablation_results['string_only']], 'o-', color='#2E86AB', label='String Only', markersize=4)
            ax.plot(top_ns, [m['recall'] for m in ablation_results['symbol_only']], 's-', color='#A23B72', label='Symbol Only', markersize=4)
            ax.plot(top_ns, [m['recall'] for m in ablation_results['combined']], '^-', color='#F18F01', label='Combined', markersize=4)
            ax.set_xlabel('Top-N')
            ax.set_ylabel('Recall (%)')
            ax.set_title('Retrieval Recall: Feature Contribution Analysis')
            ax.legend(loc='lower right', frameon=True, fancybox=False, edgecolor='black')
            ax.set_xlim(0, max_top_n + 1)
            ax.set_ylim(0, 105)

            os.makedirs(output_dir, exist_ok=True)
            plt.savefig(os.path.join(output_dir, 'retrieval_contribution.pdf'), format='pdf')
            plt.savefig(os.path.join(output_dir, 'retrieval_contribution.png'), format='png')
            plt.close()
            logger.info(f"图片已保存到 {output_dir}")
        except Exception as e:
            logger.warning(f"生成图片失败: {e}")

    # ========== 7. 保存报告 ==========
    report = {'max_top_n': max_top_n, 'ablation_results': ablation_results}
    if output_dir:
        with open(os.path.join(output_dir, 'retrieval_contribution.json'), 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    return report


# =============================================================================
# 3. 失败案例分析
# =============================================================================

def analyze_failure_cases(
    evaluation_report_path: str,
    test_case_dir: str,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    分析最终检测结果中的误报(FP)和漏报(FN)

    【背景】
    检测系统分为两个阶段：
    1. 检索阶段：通过特征匹配召回候选库
    2. 验证阶段：LLM 对候选库进行验证

    【功能】
    分析最终检测结果的失败情况：

    FN（漏报）分为两类：
    1. 检索失败：GT 库没有出现在 feature_match_candidates 中（特征匹配没召回）
    2. 验证误排除：GT 库在 candidates 中但被 LLM 错误排除了

    FP（误报）：
    非 GT 库被错误地检测出来

    【输出】
    - 统计摘要（FN 中检索失败占比 vs 验证误排除占比）
    - 按库名聚合统计
    - failure_analysis.json：完整分析报告
    - fn_test_case_paths.json：FN 测试用例路径列表
    - fp_test_case_paths.json：FP 测试用例路径列表

    Args:
        evaluation_report_path: evaluation_report.json 文件路径
        test_case_dir: 测试用例目录路径
        output_dir: 输出目录

    Returns:
        Dict 包含失败分析结果
    """
    from evaluation.tpl_detection_evaluation.interface import EvaluationReport

    # ========== 1. 加载评估报告 ==========
    logger.info(f"加载评估报告: {evaluation_report_path}")
    report = EvaluationReport.load_from_file(evaluation_report_path)
    results_check = report.results_check
    logger.info(f"加载了 {len(results_check)} 条评估结果")

    # ========== 2. 辅助函数 ==========
    def normalize_name(name: str) -> str:
        return name.lower().strip().replace('-', '_').replace('.', '_')

    def is_lib_in_list(lib_name: str, lib_list: List[str]) -> bool:
        if not lib_name or not lib_list:
            return False
        normalized_lib = normalize_name(lib_name)
        for candidate in lib_list:
            normalized_candidate = normalize_name(candidate)
            if normalized_lib == normalized_candidate:
                return True
            if normalize_name('lib' + lib_name) == normalized_candidate:
                return True
            if normalized_lib == normalize_name('lib' + candidate):
                return True
        return False

    # ========== 3. 分析 FN 和 FP ==========
    fn_retrieval_failures = []   # 检索失败
    fn_verification_errors = []  # 验证误排除
    fp_cases = []                # 误报

    for check in results_check:
        if not check.succeed:
            continue

        binary_path = check.binary_path or os.path.join(test_case_dir, check.binary_name)

        # 分析 FN
        for fn_lib in (check.fn_libs or []):
            in_candidates = is_lib_in_list(fn_lib, check.feature_match_candidates or [])
            fn_entry = {
                'library': fn_lib,
                'binary_name': check.binary_name,
                'binary_hash': check.binary_hash,
                'binary_path': binary_path,
            }
            if in_candidates:
                fn_entry['reason'] = 'verification_exclusion'
                fn_entry['note'] = '在候选列表中但被 LLM 错误排除'
                fn_verification_errors.append(fn_entry)
            else:
                fn_entry['reason'] = 'retrieval_failure'
                fn_entry['note'] = '特征匹配未能召回该库'
                fn_retrieval_failures.append(fn_entry)

        # 分析 FP
        for fp_lib in (check.fp_libs or []):
            fp_cases.append({
                'library': fp_lib,
                'binary_name': check.binary_name,
                'binary_hash': check.binary_hash,
                'binary_path': binary_path,
                'ground_truth': check.ground_truth or [],
            })

    # ========== 4. 统计摘要 ==========
    total_fn = len(fn_retrieval_failures) + len(fn_verification_errors)
    total_fp = len(fp_cases)
    summary = {
        'total_fn': total_fn,
        'fn_retrieval_failure': len(fn_retrieval_failures),
        'fn_verification_exclusion': len(fn_verification_errors),
        'fn_retrieval_ratio': round(len(fn_retrieval_failures) / total_fn * 100, 2) if total_fn > 0 else 0,
        'fn_verification_ratio': round(len(fn_verification_errors) / total_fn * 100, 2) if total_fn > 0 else 0,
        'total_fp': total_fp,
    }

    # ========== 5. 打印结果 ==========
    print("\n" + "=" * 80)
    print("失败案例分析 (Failure Case Analysis)")
    print("=" * 80)

    print(f"\n【摘要】")
    print(f"  总 FN（漏报）: {total_fn}")
    print(f"    - 检索失败（特征没匹配）: {summary['fn_retrieval_failure']} ({summary['fn_retrieval_ratio']}%)")
    print(f"    - 验证误排除（LLM 错误排除）: {summary['fn_verification_exclusion']} ({summary['fn_verification_ratio']}%)")
    print(f"  总 FP（误报）: {total_fp}")

    # 打印 FN 示例
    if fn_retrieval_failures:
        print(f"\n【FN - 检索失败 (共 {len(fn_retrieval_failures)} 个)】")
        print(f"  {'库名':<30} {'二进制文件':<40}")
        print(f"  {'-'*30} {'-'*40}")
        for entry in fn_retrieval_failures[:15]:
            print(f"  {entry['library'][:30]:<30} {entry['binary_name'][:40]:<40}")
        if len(fn_retrieval_failures) > 15:
            print(f"  ... 还有 {len(fn_retrieval_failures) - 15} 个")

    if fn_verification_errors:
        print(f"\n【FN - 验证误排除 (共 {len(fn_verification_errors)} 个)】")
        print(f"  {'库名':<30} {'二进制文件':<40}")
        print(f"  {'-'*30} {'-'*40}")
        for entry in fn_verification_errors[:15]:
            print(f"  {entry['library'][:30]:<30} {entry['binary_name'][:40]:<40}")
        if len(fn_verification_errors) > 15:
            print(f"  ... 还有 {len(fn_verification_errors) - 15} 个")

    if fp_cases:
        print(f"\n【FP - 误报 (共 {len(fp_cases)} 个)】")
        print(f"  {'误报库':<30} {'二进制文件':<40}")
        print(f"  {'-'*30} {'-'*40}")
        for entry in fp_cases[:15]:
            print(f"  {entry['library'][:30]:<30} {entry['binary_name'][:40]:<40}")
        if len(fp_cases) > 15:
            print(f"  ... 还有 {len(fp_cases) - 15} 个")

    # ========== 6. 按库名聚合 ==========
    def aggregate_by_lib(entries: List[Dict]) -> List[tuple]:
        by_lib: Dict[str, int] = {}
        for e in entries:
            by_lib[e['library']] = by_lib.get(e['library'], 0) + 1
        return sorted(by_lib.items(), key=lambda x: x[1], reverse=True)

    sorted_fn_retrieval = aggregate_by_lib(fn_retrieval_failures)
    sorted_fn_verification = aggregate_by_lib(fn_verification_errors)
    sorted_fp = aggregate_by_lib(fp_cases)

    print(f"\n【按库名聚合 - FN 检索失败 Top 10】")
    for lib, count in sorted_fn_retrieval[:10]:
        print(f"  {lib:<40} {count}")

    print(f"\n【按库名聚合 - FN 验证误排除 Top 10】")
    for lib, count in sorted_fn_verification[:10]:
        print(f"  {lib:<40} {count}")

    print(f"\n【按库名聚合 - FP 误报 Top 10】")
    for lib, count in sorted_fp[:10]:
        print(f"  {lib:<40} {count}")

    print("\n" + "=" * 80)

    # ========== 7. 构建并保存报告 ==========
    analysis_report = {
        'summary': summary,
        'fn_retrieval_failures': fn_retrieval_failures,
        'fn_verification_errors': fn_verification_errors,
        'fp_cases': fp_cases,
        'aggregated': {
            'fn_retrieval_by_lib': dict(sorted_fn_retrieval),
            'fn_verification_by_lib': dict(sorted_fn_verification),
            'fp_by_lib': dict(sorted_fp),
        }
    }

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

        with open(os.path.join(output_dir, 'failure_analysis.json'), 'w', encoding='utf-8') as f:
            json.dump(analysis_report, f, indent=2, ensure_ascii=False)

        fn_paths = {
            'fn_retrieval_failure_paths': [e['binary_path'] for e in fn_retrieval_failures],
            'fn_verification_exclusion_paths': [e['binary_path'] for e in fn_verification_errors],
        }
        with open(os.path.join(output_dir, 'fn_test_case_paths.json'), 'w', encoding='utf-8') as f:
            json.dump(fn_paths, f, indent=2, ensure_ascii=False)

        fp_paths = [e['binary_path'] for e in fp_cases]
        with open(os.path.join(output_dir, 'fp_test_case_paths.json'), 'w', encoding='utf-8') as f:
            json.dump(fp_paths, f, indent=2, ensure_ascii=False)

        logger.info(f"分析报告已保存到 {output_dir}")

    return analysis_report


# =============================================================================
# 4. 按编译配置分组分析（RQ1 表格数据）
# =============================================================================

def _parse_compile_config(notes: str) -> str:
    """从 notes 中解析 compile_config"""
    import re
    if not notes:
        return "unknown"
    match = re.search(r'compile_config:\s*(\S+)', notes)
    if match:
        return match.group(1)
    return "unknown"


def _normalize_config(config: str) -> str:
    """
    将 compile_config 标准化为 compiler+arch 格式
    例如:
    - arm_64-gcc-release-shared -> gcc+arm
    - x86_64-gcc-release-shared -> gcc+x86_64
    - x86_64-clang-release-shared -> clang+x86_64
    """
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


def analyze_by_config(
    evaluation_report_path: str,
    benchmark_path: str,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    按编译配置分组统计 P/R/F1，生成论文 RQ1 表格数据

    【背景】
    论文 RQ1 需要按编译配置（gcc+x86_64, clang+x86_64, gcc+arm）分别展示效果，
    以及总体效果（Overall）。

    【功能】
    1. 从评估报告中读取每个测试用例的 TP/FP/FN
    2. 通过 binary_hash 匹配 benchmark 获取编译配置
    3. 按配置分组统计并计算 P/R/F1
    4. 输出论文表格格式

    【输出格式】
    - Overall: 总体 P/R/F1
    - gcc+x86_64: 主配置
    - clang+x86_64: 编译器变体
    - gcc+arm: 架构变体

    Args:
        evaluation_report_path: evaluation_report.json 文件路径
        benchmark_path: benchmark JSON 文件路径（包含编译配置信息）
        output_dir: 输出目录（可选，保存 JSON 报告）

    Returns:
        Dict 包含各配置的指标
    """
    from evaluation.tpl_detection_evaluation.interface import EvaluationReport, Benchmark

    # ========== 1. 加载数据 ==========
    logger.info(f"加载评估报告: {evaluation_report_path}")
    report = EvaluationReport.load_from_file(evaluation_report_path)
    results_check = report.results_check
    logger.info(f"加载了 {len(results_check)} 条评估结果")

    logger.info(f"加载 Benchmark: {benchmark_path}")
    benchmark = Benchmark.load_from_json_file(benchmark_path)

    # 构建 sha256 -> 编译配置 的映射
    sha256_to_config = {}
    for tc in benchmark.test_cases:
        sha256 = tc.test_binary.sha256
        notes = tc.test_binary.notes or ""
        raw_config = _parse_compile_config(notes)
        normalized_config = _normalize_config(raw_config)
        sha256_to_config[sha256] = normalized_config

    # ========== 2. 按配置分组统计 ==========
    # 初始化各配置的计数器
    config_stats = {}  # config -> {'tp': 0, 'fp': 0, 'fn': 0}

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

    # ========== 3. 计算各配置的 P/R/F1 ==========
    def calc_metrics(stats: Dict) -> Dict:
        tp, fp, fn = stats['tp'], stats['fp'], stats['fn']
        precision = round(tp / (tp + fp) * 100, 2) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn) * 100, 2) if (tp + fn) > 0 else 0.0
        f1 = round(2 * precision * recall / (precision + recall), 2) if (precision + recall) > 0 else 0.0
        return {
            'tp': tp, 'fp': fp, 'fn': fn,
            'precision': precision, 'recall': recall, 'f1': f1,
            'count': stats['count']
        }

    # 计算总体指标
    total_stats = {'tp': 0, 'fp': 0, 'fn': 0, 'count': 0}
    for stats in config_stats.values():
        total_stats['tp'] += stats['tp']
        total_stats['fp'] += stats['fp']
        total_stats['fn'] += stats['fn']
        total_stats['count'] += stats['count']

    results = {
        'overall': calc_metrics(total_stats),
    }

    # 按指定顺序添加各配置
    config_order = ['gcc+x86_64', 'clang+x86_64', 'gcc+arm']
    for config in config_order:
        if config in config_stats:
            results[config] = calc_metrics(config_stats[config])

    # 添加未识别的配置
    for config, stats in config_stats.items():
        if config not in results and config != 'unknown':
            results[config] = calc_metrics(stats)

    # ========== 4. 打印结果 ==========
    print("\n" + "=" * 90)
    print("按编译配置分组分析 (RQ1 Table Data)")
    print("=" * 90)

    print(f"\n{'配置':<20} {'Cases':<8} {'TP':<8} {'FP':<8} {'FN':<8} {'Recall':<10} {'Precision':<10} {'F1':<10}")
    print("-" * 90)

    # Overall
    m = results['overall']
    print(f"{'Overall':<20} {m['count']:<8} {m['tp']:<8} {m['fp']:<8} {m['fn']:<8} {m['recall']:<10.2f} {m['precision']:<10.2f} {m['f1']:<10.2f}")
    print("-" * 90)

    # 各配置
    for config in config_order:
        if config in results:
            m = results[config]
            print(f"{config:<20} {m['count']:<8} {m['tp']:<8} {m['fp']:<8} {m['fn']:<8} {m['recall']:<10.2f} {m['precision']:<10.2f} {m['f1']:<10.2f}")

    # ========== 5. 输出论文表格格式 ==========
    print(f"\n" + "=" * 90)
    print("论文表格格式 (LaTeX Row)")
    print("=" * 90)

    # 生成一行 LaTeX 格式的数据
    # 格式: Tool & R & P & F1 & R & P & F1 & R & P & F1 & R & P & F1 \\
    #       Overall      gcc+x86_64    gcc+arm       clang+x86_64

    overall = results['overall']
    gcc_x86 = results.get('gcc+x86_64', {'recall': 0, 'precision': 0, 'f1': 0})
    gcc_arm = results.get('gcc+arm', {'recall': 0, 'precision': 0, 'f1': 0})
    clang_x86 = results.get('clang+x86_64', {'recall': 0, 'precision': 0, 'f1': 0})

    latex_row = (
        f"\\tool & "
        f"{overall['recall']:.2f} & {overall['precision']:.2f} & {overall['f1']:.2f} & "
        f"{gcc_x86['recall']:.2f} & {gcc_x86['precision']:.2f} & {gcc_x86['f1']:.2f} & "
        f"{gcc_arm['recall']:.2f} & {gcc_arm['precision']:.2f} & {gcc_arm['f1']:.2f} & "
        f"{clang_x86['recall']:.2f} & {clang_x86['precision']:.2f} & {clang_x86['f1']:.2f} \\\\"
    )
    print(f"\n{latex_row}")

    print("\n" + "=" * 90)

    # ========== 6. 保存报告 ==========
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        report_data = {
            'evaluation_report_path': evaluation_report_path,
            'benchmark_path': benchmark_path,
            'results': results,
            'latex_row': latex_row,
        }
        output_path = os.path.join(output_dir, 'config_analysis.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        logger.info(f"分析报告已保存到 {output_path}")

    return results


# =============================================================================
# 5. 验证阶段排除统计分析
# =============================================================================

def analyze_exclusion_stats(
    raw_results_path: str,
    evaluation_report_path: str = None,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    统计验证阶段的排除情况

    【功能】
    1. 通过 = TP + FP（从 evaluation_report 读取）
    2. 排除 = C1 + C2 + C3 + C4 + C5（从 excluded_candidates 统计）
    3. 候选总数 = 通过 + 排除

    【fp_type 类型说明】
    - C1: Dynamic Linking (Code-Related) - 外部动态依赖
    - C2: Code Cloning (Code-Related) - 匹配来自 vendor/third_party
    - C3: Derivative Relationship (Code-Related) - Fork/变体关系
    - C4: Coincidental Match (Not Code-Related) - 只有通用特征
    - C5: Similar Functionality (Not Code-Related) - 共享标准/协议

    Args:
        raw_results_path: raw_results.json 文件路径
        evaluation_report_path: evaluation_report.json 文件路径（可选，默认同目录）
        output_dir: 输出目录（可选，保存 JSON 报告）

    Returns:
        Dict 包含统计结果
    """
    from app.interface import AnalysisResult
    from evaluation.tpl_detection_evaluation.interface import EvaluationReport
    from collections import Counter

    # ========== 1. 加载数据 ==========
    logger.info(f"加载原始结果: {raw_results_path}")
    with open(raw_results_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    results = [AnalysisResult.init_from_dict(r) for r in raw_data]
    logger.info(f"加载了 {len(results)} 条结果")

    # 加载 evaluation_report 获取 TP/FP
    if evaluation_report_path is None:
        evaluation_report_path = raw_results_path.replace('raw_results.json', 'evaluation_report.json')
    report = EvaluationReport.load_from_file(evaluation_report_path)
    total_tp = sum(r.tp_count for r in report.results_check)
    total_fp = sum(r.fp_count for r in report.results_check)

    # ========== 2. 统计 ==========
    # 通过 = TP + FP
    total_confirmed = total_tp + total_fp

    # 排除 = 各类型加起来
    total_excluded = 0
    fp_type_counter = Counter()
    for result in results:
        if result.excluded_candidates:
            total_excluded += len(result.excluded_candidates)
            for exc in result.excluded_candidates:
                fp_type_counter[exc.fp_type] += 1

    # 候选总数 = 通过 + 排除
    total_retrieved = total_confirmed + total_excluded

    # ========== 3. 计算比例 ==========
    fp_type_stats = {}
    for fp_type in ['C1', 'C2', 'C3', 'C4', 'C5']:
        count = fp_type_counter.get(fp_type, 0)
        ratio = round(count / total_excluded * 100, 2) if total_excluded > 0 else 0.0
        fp_type_stats[fp_type] = {'count': count, 'ratio': ratio}

    # 处理可能存在的其他类型
    other_types = set(fp_type_counter.keys()) - {'C1', 'C2', 'C3', 'C4', 'C5'}
    for fp_type in other_types:
        count = fp_type_counter[fp_type]
        ratio = round(count / total_excluded * 100, 2) if total_excluded > 0 else 0.0
        fp_type_stats[fp_type] = {'count': count, 'ratio': ratio}

    # ========== 4. 构建报告 ==========
    report = {
        'total_cases': len(results),
        'total_retrieved': total_retrieved,
        'total_confirmed': total_confirmed,
        'total_tp': total_tp,
        'total_fp': total_fp,
        'total_excluded': total_excluded,
        'exclusion_rate': round(total_excluded / total_retrieved * 100, 2) if total_retrieved > 0 else 0.0,
        'fp_type_stats': fp_type_stats,
    }

    # ========== 5. 打印结果 ==========
    print("\n" + "=" * 80)
    print("验证阶段排除统计 (Exclusion Statistics)")
    print("=" * 80)

    print(f"\n【总体统计】")
    print(f"  测试用例数: {report['total_cases']}")
    print(f"  候选总数: {report['total_retrieved']} (= 通过 + 排除)")
    print(f"  通过: {report['total_confirmed']} (TP={report['total_tp']} + FP={report['total_fp']})")
    print(f"  排除: {report['total_excluded']} ({report['exclusion_rate']:.2f}%)")

    print(f"\n【按排除类型统计】")
    print(f"  {'类型':<6} {'数量':<10} {'比例':<10} {'说明':<40}")
    print(f"  {'-'*6} {'-'*10} {'-'*10} {'-'*40}")

    fp_type_descriptions = {
        'C1': 'Dynamic Linking (外部动态依赖)',
        'C2': 'Code Cloning (vendor/third_party 代码)',
        'C3': 'Derivative Relationship (Fork/变体)',
        'C4': 'Coincidental Match (通用特征误匹配)',
        'C5': 'Similar Functionality (共享标准/协议)',
    }

    for fp_type in ['C1', 'C2', 'C3', 'C4', 'C5']:
        stats = fp_type_stats.get(fp_type, {'count': 0, 'ratio': 0.0})
        desc = fp_type_descriptions.get(fp_type, '')
        print(f"  {fp_type:<6} {stats['count']:<10} {stats['ratio']:.2f}%{'':<6} {desc:<40}")

    # 打印其他类型（如果有）
    for fp_type in sorted(other_types):
        stats = fp_type_stats[fp_type]
        print(f"  {fp_type:<6} {stats['count']:<10} {stats['ratio']:.2f}%{'':<6} {'(其他类型)':<40}")

    print("\n" + "=" * 80)

    # ========== 6. 保存报告 ==========
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'exclusion_stats.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"统计报告已保存到 {output_path}")

    return report
