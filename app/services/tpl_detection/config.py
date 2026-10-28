"""
TPL Detection Configuration

集中管理所有检测相关的配置常量，避免魔法数字散落在代码中。
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class FeatureMatchingConfig:
    """特征匹配配置"""
    # 字符串长度限制
    min_string_length: int = 5
    max_string_length: int = 500

    # 匹配阈值
    min_match_feature_num: int = 5
    return_top_n: int = 10

    # 置信度阈值
    confidence_thresholds: dict = field(default_factory=lambda: {
        "very_high": 20,  # >= 20 matches
        "high": 10,       # >= 10 matches
        "medium": 5,      # >= 5 matches
    })

    # 置信度分数
    confidence_scores: dict = field(default_factory=lambda: {
        "very_high": 0.9,
        "high": 0.7,
        "medium": 0.5,
        "low": 0.3,
    })


@dataclass
class CompositionAnalysisConfig:
    """成分分析配置"""
    # Prompt 中显示的最大条目数
    max_copyright_notices: int = 15
    max_version_strings: int = 15
    max_urls: int = 10
    max_source_paths: int = 15
    max_symbol_prefixes: int = 10
    max_feature_candidates: int = 10

    # 符号前缀统计
    min_symbol_prefix_length: int = 2
    min_symbol_prefix_count: int = 3  # 前缀至少出现 N 次才计入


@dataclass
class VersionAnalysisConfig:
    """版本分析配置"""
    # 每个库分析的字符串数量上限
    analysis_string_limit_per_library: int = 20

    # 批量分析时每批的库数量上限
    max_libraries_per_batch: int = 10

    # 是否默认启用联网搜索
    default_enable_web_search: bool = False


@dataclass
class ReportingConfig:
    """报告配置"""
    # 是否报告低置信度结果
    report_low_confidence: bool = False

    # 是否报告 unknown_program
    report_unknown_program: bool = False


@dataclass
class SystemLibraryConfig:
    """系统库过滤配置"""
    # 不报告为动态依赖的系统库模式
    system_library_patterns: List[str] = field(default_factory=lambda: [
        # glibc
        "libc.so*", "libm.so*", "libpthread.so*", "libdl.so*", "librt.so*",
        # C++ runtime
        "libstdc++.so*", "libgcc_s.so*",
        # Dynamic linker
        "ld-linux*.so*", "ld.so*",
        # Other system libs
        "linux-vdso.so*", "linux-gate.so*",
    ])


@dataclass
class TPLDetectionConfig:
    """TPL 检测总配置"""
    feature_matching: FeatureMatchingConfig = field(default_factory=FeatureMatchingConfig)
    composition_analysis: CompositionAnalysisConfig = field(default_factory=CompositionAnalysisConfig)
    version_analysis: VersionAnalysisConfig = field(default_factory=VersionAnalysisConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)
    system_libraries: SystemLibraryConfig = field(default_factory=SystemLibraryConfig)


# 默认配置实例
default_config = TPLDetectionConfig()


def get_config() -> TPLDetectionConfig:
    """获取默认配置"""
    return default_config
