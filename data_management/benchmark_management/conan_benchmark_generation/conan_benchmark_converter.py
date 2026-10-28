import os
import sys
from datetime import datetime

from environs import Env
from loguru import logger

from data_management.benchmark_management.conan_benchmark_generation.interface import Benchmark as ConanBenchmark
from evaluation.tpl_detection_evaluation.interface import TestBinary, ReusedLibrary, TestCase, Benchmark as GeneralBenchmark, \
    BenchmarkNote, BenchmarkSummary

env = Env()
env.read_env()
logger.remove()
logger.add(sys.stderr, level="INFO")




def load_json(file_path: str) -> dict:
    """
    Load the library information from a JSON file.

    Args:
        lib_info_path (str): Path to the JSON file containing library information.

    Returns:
        dict: Parsed JSON data.
    """
    import json

    with open(file_path, 'r') as file:
        lib_info = json.load(file)

    return lib_info



def dump_to_json(data: dict, file_path: str):
    """
    Dump the data to a JSON file.

    Args:
        data (dict): Data to be dumped.
        file_path (str): Path to the output JSON file.
    """
    import json

    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def convert(conan_benchmark: ConanBenchmark) -> GeneralBenchmark:
    library_dict = {software.source_library.name:software.source_library for software in conan_benchmark.test_software}

    test_case_hash_set = set()
    test_cases = []
    for software in conan_benchmark.test_software:
        for test_binary_suite in software.test_binary_suites:
            compile_config = test_binary_suite.compile_config
            library_reuses = test_binary_suite.library_reuses
            tpl_binaries_dict = test_binary_suite.binaries

            for tpl_name, binaries in tpl_binaries_dict.items():

                reused_library = ReusedLibrary(
                    name = tpl_name,
                )
                if tpl_name in library_dict:
                    tpl_library = library_dict.get(tpl_name)
                    reused_library.repository = tpl_library.homepage
                    reused_library.version = tpl_library.version
                    reused_library.description = tpl_library.description
                    reused_library.type = ", ".join(tpl_library.topics) if tpl_library.topics else None

                # 创建新的
                for binary in binaries:
                    # 相同的只要一个
                    if binary.sha256 in test_case_hash_set:
                        continue
                    test_case_hash_set.add(binary.sha256)
                    test_binary = TestBinary(
                        original_name = binary.name,
                        relative_path = binary.rel_path,
                        file_size_kb = binary.file_size_kb,
                        sha256 = binary.sha256,
                        notes = f"type: {binary.type}, tpl_name: {tpl_name}, conan version: {compile_config.conan_version}, compile_config: {compile_config.profile}",
                    )

                    test_case = TestCase(
                        test_binary = test_binary,
                        reused_libraries= [reused_library,]
                    )
                    test_cases.append(test_case)


    reused_library_num = len({lib.name for tc in test_cases for lib in tc.reused_libraries})
    general_benchmark = GeneralBenchmark(
        name = conan_benchmark.name,
        version = '20250722',
        summary=BenchmarkSummary(
            test_case_num= len(test_cases),
            covered_library_num= reused_library_num,
        ),
        notes= [
            BenchmarkNote(
                message= "converted from the conan benchmark",
                update_at= datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        ],
        test_cases = test_cases,
    )

    return general_benchmark



def main():
    # paths
    from data_management.benchmark_management.conan_benchmark_generation import paths
    conan_benchmark_path = paths.LIBRARY_BENCHMARK_JSON
    general_benchmark_path = paths.BENCHMARK_JSON

    # Load library information
    benchmark = load_json(conan_benchmark_path)

    # 加载conan的benchmark
    conan_benchmark = ConanBenchmark.init_from_dict(benchmark)

    general_benchmark = convert(conan_benchmark)

    dump_to_json(general_benchmark.customer_serialize(), general_benchmark_path)

    """
    conan benchmark generator 生成出来的是
        software
            reused tpls
            binaries

    一方面，这个数据不是以binary为主，主要是分析每个软件中的那些二进制代表了第三方库。
    另一方面，这些数据的binary中有很多其实是重复的。

    因此，我们需要把它转换成最初的那种binary为主的benchmark，
        一方面，那种更容易看懂。
        另一方面，那种数据结构可以直接使用我们之前的框架进行分析，就不用再重新写一个新的框架了。


    所以，我们要转换过去。
    :return:
    """

if __name__ == '__main__':
    main()