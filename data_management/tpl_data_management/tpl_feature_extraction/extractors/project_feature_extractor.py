import json
import multiprocessing
import os
from typing import List

from loguru import logger
from tqdm import tqdm

from ..constants import C_EXTENSION_SET, CPP_EXTENSION_SET
from .file_feature_extractor import extract_src_file_feature
from ..interface import ProjectFeature
from ..tools import calculate_sha256


class ProjectFeatureExtractor:

    def __init__(self,
                 project_name,
                 project_path,
                 file_feature_cache=None,
                 show_progress=False,
                 filter_third_party=True):

        self.project_path = project_path
        self.project_name = project_name

        self.file_feature_cache = file_feature_cache
        self.show_progress = show_progress
        self.filter_third_party = filter_third_party

        self.c_cpp_file_paths: List[str] = []

        # 第三方库文件夹黑名单（小写匹配）
        self.third_party_dirs = {
            # 第三方依赖目录
            'third_party', 'third-party', 'thirdparty', '3rdparty',
            '3rd',
            'vendor', 'vendors', 'vendored',
            'external', 'extern', 'externals',
            'deps', 'dependencies',
            # 测试目录
            'test', 'tests', 'testing',
            # 基准测试和示例
            'benchmark', 'benchmarks', 'bench',
            'examples', 'example', 'samples',
        }



    def is_c_cpp_file(self, file_path):
        if file_path.endswith(tuple(C_EXTENSION_SET)):
            return True
        elif file_path.endswith(tuple(CPP_EXTENSION_SET)):
            return True

        return False

    def filter_c_cpp_files(self):
        file_count = 0
        for root, dirs, files in os.walk(self.project_path):
            # 过滤第三方目录（修改 dirs 阻止 os.walk 进入这些目录）
            if self.filter_third_party:
                dirs[:] = [d for d in dirs if d.lower() not in self.third_party_dirs]

            for file in files:
                file_path = os.path.join(root, file)
                # 不是文件跳过
                if not os.path.isfile(file_path):
                    continue
                # 跳过链接
                if os.path.islink(file_path):
                    continue
                file_count += 1
                # 筛选c, cpp 文件
                if self.is_c_cpp_file(file_path):
                    self.c_cpp_file_paths.append(file_path)
        # print(f"find {len(self.c_cpp_file_paths)} c/cpp files from {file_count} files.")

    def extract_multiprocessing(self, process_num):
        with multiprocessing.Pool(process_num) as pool:
            tasks = pool.imap_unordered(extract_src_file_feature, self.c_cpp_file_paths)
            if self.show_progress:
                tasks = tqdm(tasks, total=len(self.c_cpp_file_paths), desc="multiprocess extract_src_file_feature")
            results = list(tasks)
        return results

    def extract_single_processing(self):
        src_files = []
        tasks = self.c_cpp_file_paths
        if self.show_progress:
            tasks = tqdm(tasks, total=len(self.c_cpp_file_paths), desc="single process extract_src_file_feature")
        for path in tasks:
            src_file = extract_src_file_feature(path)
            src_files.append(src_file)

        return src_files

    def extract(self, process_num=1) -> ProjectFeature:
        # 1. filter c/cpp files
        self.filter_c_cpp_files()

        # 2. 检查一下文件数量
        white_list = ['gcc']
        if len(self.c_cpp_file_paths) > 50000 and self.project_name not in white_list:
            error_msg = f"Too Many Files({len(self.c_cpp_file_paths)}), Skipped!"
            print(error_msg)
            src_project = ProjectFeature(
                name=self.project_name,
                project_size_mb=0,
                total_src_file=0,
                failed_src_file=0,
                exception_src_file=0,
                function_count=0,
                distinct_string_count=0,
                file_features=[],
                extraction_succeed=False,
                extraction_log=error_msg
            )
            return src_project

        # 2. 如果有缓存, 直接用缓存（缓存建议用上个版本的特征结果）
        cached_file_features = []  # 缓存的特征
        if self.file_feature_cache:
            uncached_c_cpp_file_paths = [] # 没有缓存的文件路径
            for file_path in self.c_cpp_file_paths:
                sha256 = calculate_sha256(file_path)
                if sha256 in self.file_feature_cache:
                    # 直接使用缓存的特征
                    file_feature= self.file_feature_cache[sha256]
                    file_feature.path = file_path
                    # 更新文件的路径（有可能hash一样，但是移动了目录）
                    file_feature.use_relative_file_path(self.project_path)
                    cached_file_features.append(file_feature)
                else:
                    uncached_c_cpp_file_paths.append(file_path)

            # 更新待提取的文件目录
            # print(f"cached {len(cached_file_features)} of {len(self.c_cpp_file_paths)} files")
            self.c_cpp_file_paths = uncached_c_cpp_file_paths

        # 3. extract file feature，没有缓存的部分，重新提取
        if process_num > 1:
            file_features = self.extract_multiprocessing(process_num)
        else:
            file_features = self.extract_single_processing()
        file_features = file_features + cached_file_features

        # 3. 简单统计
        failed_count = 0
        exception_count = 0
        function_count = 0
        distinct_strings = set()
        for file_feature in file_features:

            # 使用相对路径
            file_feature.use_relative_file_path(self.project_path)

            # 统计函数数量和字符串数量
            for src_function in file_feature.functions:
                function_count += len(file_feature.functions)
                distinct_strings.update(src_function.string_literals)
            distinct_strings.update(file_feature.global_strings)

            # 统计成功的数量(读取文件错误不会报日志，直接记录。)
            if not file_feature.extraction_succeed:
                failed_count += 1
            elif file_feature.extraction_log:
                exception_count += 1
        if self.show_progress:
            if failed_count > 0 or exception_count > 0:
                logger.warning(f"      📊 文件 {len(file_features)}, 失败 {failed_count}, 异常 {exception_count} ⚠️")
            else:
                logger.info(f"      📊 文件 {len(file_features)}, 失败 {failed_count}, 异常 {exception_count}")

        # 4. create project feature
        project_size_mb = round(sum([ff.file_size_kb for ff in file_features]) / 1024, 2)

        total_src_file = len(file_features)
        if total_src_file == 0 or (failed_count + exception_count) / total_src_file > 0.1:
            extraction_succeed = False
            err_msg = (f"Total Files: {total_src_file}, "
                       f"Failed Files: {failed_count}, "
                       f"Exception Files: {exception_count},"
                       f"Failed + Exception Files > 10%")
        else:
            extraction_succeed = True
            err_msg = ""

        src_project = ProjectFeature(
            name=self.project_name,
            project_size_mb=project_size_mb,
            total_src_file=len(file_features),
            failed_src_file=failed_count,
            exception_src_file=exception_count,
            function_count=function_count,
            distinct_string_count=len(distinct_strings),
            file_features=file_features,
            extraction_succeed=extraction_succeed,
            extraction_log=err_msg
        )

        return src_project


if __name__ == '__main__':
    demo_project_path = "path/to/openssl"
    project_extractor = ProjectFeatureExtractor(demo_project_path)
    src_project, err_msg = project_extractor.extract(process_num=20)
    print(src_project)
    with open("/tmp/demo_project.json", 'w') as f:
        json.dump(src_project.customer_serialize(), f, ensure_ascii=False, indent=4)
