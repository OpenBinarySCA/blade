"""
Conan benchmark 构建流程使用的路径

可通过环境变量覆盖：
    CONAN_LIBS_BUILDER_OUTPUT       编译产物目录（默认: ./conan_libs_builder_output）
    CONAN_BENCHMARK_TEST_CASE_DIR   最终测试二进制目录（默认: data/benchmarks/conan_bench/test_cases）
"""
import os

from environs import Env

env = Env()
env.read_env()

GENERATION_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(GENERATION_DIR, "..", "..", ".."))

BUILDER_DIR = os.path.join(GENERATION_DIR, "conan_libs_builder")
PROFILE_DIR = os.path.join(BUILDER_DIR, "profiles")
CONAN_LIBS_JSON = os.path.join(BUILDER_DIR, "conan_libs.json")

BENCHMARK_META_DIR = os.path.join(GENERATION_DIR, "benchmark_meta")
LIB_INFO_JSON = os.path.join(BENCHMARK_META_DIR, "conan_lib_info.json")
LIBRARY_BENCHMARK_JSON = os.path.join(BENCHMARK_META_DIR, "conan_library_benchmark.json")  # 以软件为单位
BENCHMARK_JSON = os.path.join(BENCHMARK_META_DIR, "conan_benchmark.json")                 # 以二进制为单位（评估格式）

BUILDER_OUTPUT_DIR = env.str("CONAN_LIBS_BUILDER_OUTPUT", os.path.join(GENERATION_DIR, "conan_libs_builder_output"))
TEST_CASE_DIR = env.str("CONAN_BENCHMARK_TEST_CASE_DIR",
                        os.path.join(REPO_ROOT, "data", "benchmarks", "conan_bench", "test_cases"))
