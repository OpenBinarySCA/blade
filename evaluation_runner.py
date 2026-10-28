"""
BLADE experiment runner (see REPRODUCE.md)

    python evaluation_runner.py conan       # Table 3
    python evaluation_runner.py ablation    # Table 4
    python evaluation_runner.py car         # Table 5
    python evaluation_runner.py topn        # Figure 10

The LLM is selected with LLM_PROVIDER / LLM_MODEL_ID in .env.
"""
import argparse
import os
import time

from environs import Env

from app.config import settings
from evaluation.tpl_detection_evaluation.analyzer import (
    analyze_topn_metrics,
    analyze_failure_cases,
    analyze_by_config,
    analyze_exclusion_stats,
)
from evaluation.tpl_detection_evaluation.evaluator import Evaluator
from evaluation.tpl_detection_evaluation.interface import EvaluationConfig

env = Env()
env.read_env()

BENCHMARKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "benchmarks")
CONAN_DIR = os.path.join(BENCHMARKS_DIR, "conan_bench")
CAR_DIR = os.path.join(BENCHMARKS_DIR, "car_bench")
CONAN_BENCHMARK = os.path.join(CONAN_DIR, "conan_benchmark.json")
CONAN_TEST_CASES = os.path.join(CONAN_DIR, "test_cases")

# Results reported in the paper
CONAN_RESULTS = os.path.join(CONAN_DIR, "results")
GPT5_RUN = os.path.join(CONAN_RESULTS, "gpt-5")
TOPN_RUN = os.path.join(CONAN_RESULTS, "retrieval_only")
# New runs are written here
CONAN_RUNS = os.path.join(CONAN_DIR, "runs")


def create_output_dir(runs_dir: str, name: str = None) -> str:
    """{runs_dir}/{name or model_id}/{timestamp}"""
    name = name or settings.LLM_MODEL_ID.split("/")[-1]
    output_dir = os.path.join(runs_dir, name, time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def run_benchmark(benchmark_file: str, test_case_dir: str, runs_dir: str, name: str = None,
                  retrieval_top_n: int = 10, use_agent: bool = True, **ablation):
    """运行一个 benchmark 并保存评估报告"""
    output_dir = create_output_dir(runs_dir, name)
    config = EvaluationConfig(
        benchmark_file=benchmark_file,
        test_case_dir=test_case_dir,
        silent=True,
        enable_version_analysis=False,
        enable_explanation_generation=False,
        concurrency=100,
        enable_hint_recall=True,
        enable_string_recall=True,
        enable_symbol_recall=True,
        min_match_count_threshold=4,
        retrieval_top_n=retrieval_top_n,
        use_agent=use_agent,
        **ablation,
    )
    evaluator = Evaluator(config)
    evaluator.run_test_cases(analyze_context=False)
    evaluator.evaluate()
    evaluator.report.dump(output_dir)
    print(f"结果已保存到: {output_dir}")
    return output_dir


def run_conan_benchmark():
    """Table 3：Conan benchmark"""
    return run_benchmark(CONAN_BENCHMARK, CONAN_TEST_CASES, CONAN_RUNS)


def run_car_benchmark():
    """Table 5：车载数据集（不公开）"""
    return run_benchmark(os.path.join(CAR_DIR, "car_benchmark.json"),
                         os.path.join(CAR_DIR, "test_cases"),
                         os.path.join(CAR_DIR, "runs"))


def run_ablation_experiments():
    """Table 4：w/o Structured Evidence、w/o Category-Guided Verification"""
    experiments = [
        ("wo_structured_evidence", {"ablation_all": True}),
        ("wo_category_guided_verification", {"ablation_no_cot": True}),
    ]
    for name, flags in experiments:
        run_benchmark(CONAN_BENCHMARK, CONAN_TEST_CASES, CONAN_RUNS, name=name, **flags)


def run_topn():
    """Table 4 w/o Verification、Figure 10：只做检索（不经 LLM 验证），取前 100 个候选"""
    output_dir = run_benchmark(CONAN_BENCHMARK, CONAN_TEST_CASES, CONAN_RUNS, name="retrieval_only",
                               retrieval_top_n=100, use_agent=False)
    analyze_topn_metrics(
        raw_results_path=os.path.join(output_dir, "raw_results.json"),
        benchmark_path=CONAN_BENCHMARK,
        max_top_n=0,
        output_dir=output_dir,
    )


def analyze_topn():
    """Top-N 指标（Figure 10）"""
    analyze_topn_metrics(
        raw_results_path=os.path.join(TOPN_RUN, "raw_results.json"),
        benchmark_path=CONAN_BENCHMARK,
        max_top_n=0,
        output_dir=TOPN_RUN,
    )


def analyze_failures():
    """FN / FP 分析（RQ1）"""
    analyze_failure_cases(
        evaluation_report_path=os.path.join(GPT5_RUN, "evaluation_report.json"),
        test_case_dir=CONAN_TEST_CASES,
        output_dir=GPT5_RUN,
    )


def analyze_config():
    """按编译配置分列（Table 3）"""
    analyze_by_config(
        evaluation_report_path=os.path.join(GPT5_RUN, "evaluation_report.json"),
        benchmark_path=CONAN_BENCHMARK,
        output_dir=GPT5_RUN,
    )


def analyze_exclusion():
    """验证阶段排除统计（RQ1）"""
    analyze_exclusion_stats(
        raw_results_path=os.path.join(GPT5_RUN, "raw_results.json"),
        output_dir=GPT5_RUN,
    )


TASKS = {
    "conan": run_conan_benchmark,
    "ablation": run_ablation_experiments,
    "car": run_car_benchmark,
    "topn": run_topn,
    "analyze-topn": analyze_topn,
    "analyze-config": analyze_config,
    "analyze-failures": analyze_failures,
    "analyze-exclusion": analyze_exclusion,
}


def main():
    parser = argparse.ArgumentParser(description="BLADE experiment runner (see REPRODUCE.md)")
    parser.add_argument("task", choices=TASKS)
    args = parser.parse_args()
    TASKS[args.task]()


if __name__ == "__main__":
    main()
