"""
TPL Processors - 模块化的 TPL 数据处理器

包含以下组件：
- GitProcessor: Git 相关操作
- VersionProcessor: 版本处理
- LicenseProcessor: License 检测与提取
- MetadataProcessor: 元数据解析
- IngestionProcessor: 数据库入库
"""

from .interface import LibraryInfo, VersionInfo, LicenseInfo, FeatureData, FileFeatureData, ProcessingResult
from .git_processor import GitProcessor
from .version_processor import VersionProcessor
from .license_processor import LicenseProcessor
from .metadata_processor import MetadataProcessor
from .ingestion_processor import IngestionProcessor

__all__ = [
    # Data models
    'LibraryInfo',
    'VersionInfo',
    'LicenseInfo',
    'FeatureData',
    'FileFeatureData',
    'ProcessingResult',
    # Processors
    'GitProcessor',
    'VersionProcessor',
    'LicenseProcessor',
    'MetadataProcessor',
    'IngestionProcessor',
]
