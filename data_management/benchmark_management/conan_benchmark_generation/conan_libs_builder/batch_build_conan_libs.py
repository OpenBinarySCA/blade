import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional

from environs import Env
from loguru import logger

from data_management.benchmark_management.conan_benchmark_generation.conan_libs_builder.conan_library_builder import build_multiple_profiles, ConanBuildError

env = Env()
env.read_env()
logger.remove()
logger.add(sys.stderr, level="INFO")


@dataclass
class BuildMetadata:
    """构建元数据"""
    build_time: str
    total_libraries: int
    evaluation_dir: str
    profile_dir: str
    total_build_time: float  # 新增：总构建时间（秒）
    average_build_time: float  # 新增：平均构建时间（秒）


@dataclass
class ProfileBuildDetail:
    """单个profile的构建详情"""
    status: str
    dependencies_count: Optional[int] = None
    error: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class ErrorDetail:
    """错误详情"""
    profile: Optional[str] = None
    error: str = ""


@dataclass
class LibraryBuildStats:
    """单个库的构建统计"""
    version: str
    status: str
    successful_profiles: List[str]
    failed_profiles: List[str]
    successful_count: int
    failed_count: int
    total_profiles: int
    build_details: Dict[str, ProfileBuildDetail]
    error_summary: Dict[str, List[ErrorDetail]]
    build_time: float  # 新增：构建耗时（秒）
    build_time_formatted: str  # 新增：格式化的构建耗时


@dataclass
class GlobalSummary:
    """全局统计摘要"""
    fully_successful: int
    partially_successful: int
    completely_failed: int
    fully_successful_libraries: List[str]
    partially_successful_libraries: List[str]
    completely_failed_libraries: List[str]
    total_build_time: float  # 新增：总构建时间（秒）
    total_build_time_formatted: str  # 新增：格式化的总构建时间
    average_build_time: float  # 新增：平均构建时间（秒）
    average_build_time_formatted: str  # 新增：格式化的平均构建时间


@dataclass
class BuildStatistics:
    """完整的构建统计数据"""
    metadata: BuildMetadata
    library_details: Dict[str, LibraryBuildStats]
    global_summary: GlobalSummary


def format_time(seconds: float) -> str:
    """
    格式化时间显示

    :param seconds: 秒数
    :return: 格式化的时间字符串
    """
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"


def load_conan_list(conan_libs_json: str) -> Dict[str, List[str]]:
    """
    加载conan库列表

    :param conan_libs_json: conan库配置文件路径
    :return: 库名到版本列表的映射
    """
    with open(conan_libs_json, 'r') as f:
        data = json.load(f)
    return data


def create_initial_statistics(evaluation_dir: str, profile_dir: str, total_libraries: int) -> BuildStatistics:
    """
    创建初始的统计数据结构

    :param evaluation_dir: 评估目录路径
    :param profile_dir: profile目录路径
    :param total_libraries: 总库数量
    :return: 初始化的统计数据
    """
    metadata = BuildMetadata(
        build_time=datetime.now().isoformat(),
        total_libraries=total_libraries,
        evaluation_dir=evaluation_dir,
        profile_dir=profile_dir,
        total_build_time=0.0,
        average_build_time=0.0
    )

    global_summary = GlobalSummary(
        fully_successful=0,
        partially_successful=0,
        completely_failed=0,
        fully_successful_libraries=[],
        partially_successful_libraries=[],
        completely_failed_libraries=[],
        total_build_time=0.0,
        total_build_time_formatted="0秒",
        average_build_time=0.0,
        average_build_time_formatted="0秒"
    )

    return BuildStatistics(
        metadata=metadata,
        library_details={},
        global_summary=global_summary
    )


def process_build_results(results: Dict[str, Dict]) -> tuple[
    List[str], List[str], Dict[str, ProfileBuildDetail], Dict[str, List[ErrorDetail]]]:
    """
    处理构建结果，提取成功和失败的profile信息

    :param results: build_multiple_profiles的返回结果
    :return: (成功profiles, 失败profiles, 构建详情, 错误摘要)
    """
    successful_builds = []
    failed_builds = []
    build_details = {}
    error_summary = {}

    for profile_name, result in results.items():
        if result['status'] == 'success':
            successful_builds.append(profile_name)
            metadata = result['metadata']
            deps_count = metadata['dependencies']['summary']['total_packages']
            build_details[profile_name] = ProfileBuildDetail(
                status="success",
                dependencies_count=deps_count,
                metadata=metadata
            )
        else:
            failed_builds.append(profile_name)
            error_msg = result['error']
            build_details[profile_name] = ProfileBuildDetail(
                status="failed",
                error=error_msg
            )

            # 统计错误类型
            error_type = type(result.get('exception', Exception())).__name__
            if error_type not in error_summary:
                error_summary[error_type] = []
            error_summary[error_type].append(ErrorDetail(
                profile=profile_name,
                error=error_msg
            ))

    return successful_builds, failed_builds, build_details, error_summary


def create_library_stats(library_version: str, successful_profiles: List[str], failed_profiles: List[str],
                         build_details: Dict[str, ProfileBuildDetail],
                         error_summary: Dict[str, List[ErrorDetail]], build_time: float) -> LibraryBuildStats:
    """
    创建单个库的统计信息

    :param library_version: 库版本
    :param successful_profiles: 成功的profile列表
    :param failed_profiles: 失败的profile列表
    :param build_details: 构建详情
    :param error_summary: 错误摘要
    :param build_time: 构建耗时（秒）
    :return: 库统计信息
    """
    successful_count = len(successful_profiles)
    failed_count = len(failed_profiles)
    total_profiles = successful_count + failed_count

    # 确定库的整体状态
    if failed_count == 0:
        status = "fully_successful"
    elif successful_count == 0:
        status = "completely_failed"
    else:
        status = "partially_successful"

    return LibraryBuildStats(
        version=library_version,
        status=status,
        successful_profiles=successful_profiles,
        failed_profiles=failed_profiles,
        successful_count=successful_count,
        failed_count=failed_count,
        total_profiles=total_profiles,
        build_details=build_details,
        error_summary=error_summary,
        build_time=build_time,
        build_time_formatted=format_time(build_time)
    )


def update_global_summary(global_summary: GlobalSummary, library_name: str, library_stats: LibraryBuildStats):
    """
    更新全局统计摘要

    :param global_summary: 全局摘要对象
    :param library_name: 库名
    :param library_stats: 库统计信息
    """
    if library_stats.status == "fully_successful":
        global_summary.fully_successful += 1
        global_summary.fully_successful_libraries.append(library_name)
    elif library_stats.status == "completely_failed":
        global_summary.completely_failed += 1
        global_summary.completely_failed_libraries.append(library_name)
    else:  # partially_successful
        global_summary.partially_successful += 1
        global_summary.partially_successful_libraries.append(library_name)


def handle_build_exception(library_name: str, exception: Exception, build_time: float) -> LibraryBuildStats:
    """
    处理构建异常，创建失败的库统计信息

    :param library_name: 库名
    :param exception: 异常对象
    :param build_time: 构建耗时（秒）
    :return: 失败的库统计信息
    """
    error_type = type(exception).__name__
    error_msg = str(exception)

    error_summary = {error_type: [ErrorDetail(error=error_msg)]}

    return LibraryBuildStats(
        version="",
        status="completely_failed",
        successful_profiles=[],
        failed_profiles=[],
        successful_count=0,
        failed_count=0,
        total_profiles=0,
        build_details={},
        error_summary=error_summary,
        build_time=build_time,
        build_time_formatted=format_time(build_time)
    )


def build_single_library(library_name: str, library_version: str, profile_dir: str,
                         base_output_dir: str) -> LibraryBuildStats:
    """
    构建单个库并返回统计信息

    :param library_name: 库名
    :param library_version: 库版本
    :param profile_dir: profile目录
    :param base_output_dir: 输出基础目录
    :return: 库统计信息
    """
    start_time = time.time()  # 记录开始时间

    try:
        logger.info(f"开始构建库: {library_name} v{library_version}")

        # 编译所有profile
        results = build_multiple_profiles(
            library_name=library_name,
            library_version=library_version,
            profile_dir=profile_dir,
            base_output_dir=os.path.join(base_output_dir, library_name, library_version)
        )

        # 处理构建结果
        successful_profiles, failed_profiles, build_details, error_summary = process_build_results(results)

        # 计算构建耗时
        build_time = time.time() - start_time

        # 创建库统计信息
        library_stats = create_library_stats(
            library_version, successful_profiles, failed_profiles, build_details, error_summary, build_time
        )

        # 记录构建结果
        logger.info(f"✅ {library_name} 库构建完成! 耗时: {format_time(build_time)}")
        logger.info(f"成功编译: {len(successful_profiles)} 个profile")
        logger.info(f"失败编译: {len(failed_profiles)} 个profile")

        # 显示每个profile的详细信息
        log_profile_details(results)

        return library_stats

    except ConanBuildError as e:
        build_time = time.time() - start_time
        logger.error(f"❌ {library_name} 构建失败: {e} (耗时: {format_time(build_time)})")
        return handle_build_exception(library_name, e, build_time)

    except Exception as e:
        build_time = time.time() - start_time
        logger.error(f"❌ {library_name} 未知错误: {e} (耗时: {format_time(build_time)})")
        import traceback
        traceback.print_exc()
        return handle_build_exception(library_name, e, build_time)


def log_profile_details(results: Dict[str, Dict]):
    """
    记录profile的详细信息

    :param results: 构建结果
    """
    for profile_name, result in results.items():
        if result['status'] == 'success':
            metadata = result['metadata']
            deps_count = metadata['dependencies']['summary']['total_packages']
            logger.info(f"  {profile_name}: {deps_count} 个依赖包")
        else:
            logger.error(f"  {profile_name}: 编译失败 - {result['error']}")


def finalize_global_summary(statistics: BuildStatistics):
    """
    完善全局统计摘要，计算总耗时和平均耗时

    :param statistics: 构建统计数据
    """
    # 计算总构建时间
    total_time = sum(lib_stats.build_time for lib_stats in statistics.library_details.values())

    # 计算平均构建时间
    library_count = len(statistics.library_details)
    average_time = total_time / library_count if library_count > 0 else 0.0

    # 更新全局摘要
    statistics.global_summary.total_build_time = total_time
    statistics.global_summary.total_build_time_formatted = format_time(total_time)
    statistics.global_summary.average_build_time = average_time
    statistics.global_summary.average_build_time_formatted = format_time(average_time)

    # 更新元数据
    statistics.metadata.total_build_time = total_time
    statistics.metadata.average_build_time = average_time


def log_global_summary(statistics: BuildStatistics):
    """
    记录全局统计摘要

    :param statistics: 构建统计数据
    """
    logger.info("\n" + "=" * 50)
    logger.info("📊 全局构建统计摘要")
    logger.info("=" * 50)
    logger.info(f"总库数量: {statistics.metadata.total_libraries}")
    logger.info(f"完全成功: {statistics.global_summary.fully_successful} 个")
    logger.info(f"部分成功: {statistics.global_summary.partially_successful} 个")
    logger.info(f"完全失败: {statistics.global_summary.completely_failed} 个")
    logger.info(f"总构建时间: {statistics.global_summary.total_build_time_formatted}")
    logger.info(f"平均构建时间: {statistics.global_summary.average_build_time_formatted}")

    if statistics.global_summary.fully_successful_libraries:
        logger.info(f"完全成功的库: {', '.join(statistics.global_summary.fully_successful_libraries)}")

    if statistics.global_summary.partially_successful_libraries:
        logger.info(f"部分成功的库: {', '.join(statistics.global_summary.partially_successful_libraries)}")

    if statistics.global_summary.completely_failed_libraries:
        logger.info(f"完全失败的库: {', '.join(statistics.global_summary.completely_failed_libraries)}")

    # 显示耗时最长的前5个库
    if statistics.library_details:
        sorted_libs = sorted(
            statistics.library_details.items(),
            key=lambda x: x[1].build_time,
            reverse=True
        )
        logger.info(f"\n耗时最长的前5个库:")
        for i, (lib_name, lib_stats) in enumerate(sorted_libs[:5], 1):
            logger.info(f"  {i}. {lib_name}: {lib_stats.build_time_formatted}")


def save_build_statistics(statistics: BuildStatistics, output_file: str):
    """
    保存构建统计结果到JSON文件

    :param statistics: 统计数据
    :param output_file: 输出文件路径
    """
    try:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # 转换为字典并保存
        stats_dict = asdict(statistics)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(stats_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"📊 构建统计已保存到: {output_file}")
    except Exception as e:
        logger.error(f"❌ 保存统计文件失败: {e}")


def batch_build_conan_libs() -> BuildStatistics:
    """
    批量构建Conan库，并生成详细统计报告
    :return: 构建统计数据
    """
    overall_start_time = time.time()  # 记录整体开始时间
    # 获取路径配置
    from data_management.benchmark_management.conan_benchmark_generation import paths
    evaluation_dir = paths.GENERATION_DIR
    conan_libs_builder_output_dir = paths.BUILDER_OUTPUT_DIR
    os.makedirs(conan_libs_builder_output_dir, exist_ok=True)

    profile_dir = paths.PROFILE_DIR
    conan_libs_json = paths.CONAN_LIBS_JSON
    stats_output_file = os.path.join(conan_libs_builder_output_dir, "build_summary.json")

    # 加载库列表
    conan_libs = load_conan_list(conan_libs_json)
    # 初始化统计数据
    statistics = create_initial_statistics(evaluation_dir, profile_dir, len(conan_libs))
    # 逐个构建库
    count = 0

    # 初始空间
    total, used, free = shutil.disk_usage(conan_libs_builder_output_dir)
    initial_free_gb = free / (1024 ** 3)  # 转换为GB

    for library_name, versions in conan_libs.items():

        count += 1
        library_version = versions[-1]

        # 检查硬盘剩余空间
        total, used, free = shutil.disk_usage(conan_libs_builder_output_dir)
        free_gb = free / (1024 ** 3)  # 转换为GB

        if free_gb < 10:
            logger.warning(f"硬盘剩余空间不足10GB (当前剩余: {free_gb:.2f}GB)，停止构建")
            break

        # 构建单个库
        library_stats = build_single_library(
            library_name, library_version, profile_dir, conan_libs_builder_output_dir
        )
        # 更新统计信息
        statistics.library_details[library_name] = library_stats
        update_global_summary(statistics.global_summary, library_name, library_stats)
        overall_build_time = time.time() - overall_start_time
        logger.success(
            f"构建 第{count}/{len(conan_libs)}个库: {library_name} v{library_version} 完成，"
            f"状态: {library_stats.status}，"
            f"本库耗时: {library_stats.build_time_formatted}，"
            f"累计耗时: {format_time(overall_build_time)}，"
            f"平均耗时: {format_time(overall_build_time / count)}，"
            f"剩余空间: {free_gb:.2f}GB， 初始空间: {initial_free_gb:.2f}GB")

    # 完善全局统计摘要（计算总耗时和平均耗时）
    finalize_global_summary(statistics)
    # 记录整体构建结束
    overall_build_time = time.time() - overall_start_time
    logger.info(f"\n🎉 全部库构建完成! 总耗时: {format_time(overall_build_time)}")
    # 记录全局统计摘要
    log_global_summary(statistics)
    # 保存统计结果
    if stats_output_file:
        save_build_statistics(statistics, stats_output_file)
    return statistics


if __name__ == '__main__':
    batch_build_conan_libs()