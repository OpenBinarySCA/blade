"""
数据模型定义

定义 TPL 处理过程中使用的数据类
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class LibraryInfo:
    """库的基本信息"""
    name: str
    git_url: str
    vendor: Optional[str] = None
    homepage: Optional[str] = None
    description: Optional[str] = None
    language: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    purl: Optional[str] = None  # Package URL (SBOM 标准标识符)
    alias: Optional[str] = None  # 库别名

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于数据库操作"""
        return {
            'name': self.name,
            'giturl': self.git_url,
            'vendor': self.vendor,
            'homepage': self.homepage,
            'description': self.description,
            'language': self.language if self.language else None,
            'categories': self.categories if self.categories else None,
            'purl': self.purl,
            'alias': self.alias,
            'source': ['git'],
        }


@dataclass
class VersionInfo:
    """版本信息"""
    tag: str
    commit_id: str
    commit_datetime: Optional[datetime] = None
    tag_datetime: Optional[datetime] = None
    is_selected_for_feature_extraction: bool = False
    semantic_version_str: Optional[str] = None  # 标准化版本号 (如 1.2.3)

    def to_source_code_dict(self, library_id: int) -> Dict[str, Any]:
        """转换为 SourceCode 数据库记录格式"""
        return {
            'library_id': library_id,
            'commit_id': self.commit_id,
            'original_version_strs': [self.tag],
            'version_source': 'git_tag',
            'commit_datetime': self.commit_datetime,
            'tag_datetime': self.tag_datetime,
            'semantic_version_str': self.semantic_version_str,
        }


@dataclass
class LicenseInfo:
    """License 信息"""
    name: str
    content: str
    file_path: str
    content_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'content': self.content,
            'content_hash': self.content_hash,
        }


@dataclass
class FileFeatureData:
    """文件级特征数据"""
    path: str                                           # 文件相对路径
    sha256: str                                         # 文件 SHA256
    name: str                                           # 文件名
    extension: str                                      # 扩展名
    file_size_kb: float = 0.0                          # 文件大小 KB
    function_num: int = 0                              # 函数数量
    distinct_string_num: int = 0                       # 去重后字符串数量
    extraction_succeed: bool = True
    extraction_log: str = ""
    global_strings: List[str] = field(default_factory=list)
    function_names: List[str] = field(default_factory=list)
    strings: List[str] = field(default_factory=list)   # 所有字符串（全局+函数内）


@dataclass
class FeatureData:
    """特征数据（从 JSON 加载或直接提取）"""
    tag: str
    commit_id: str
    strings: List[str] = field(default_factory=list)
    function_names: List[str] = field(default_factory=list)
    project_size_mb: float = 0.0
    total_src_file: int = 0
    failed_src_file: int = 0
    function_count: int = 0
    distinct_string_count: int = 0
    extraction_succeed: bool = True
    extraction_log: str = ""
    # 新增：文件级特征列表
    file_features: List[FileFeatureData] = field(default_factory=list)


@dataclass
class ProcessingResult:
    """处理结果"""
    success: bool = False
    library_id: Optional[int] = None
    library_name: Optional[str] = None
    versions_total: int = 0
    versions_added: int = 0
    versions_with_features: int = 0
    licenses_added: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, error: str):
        """添加错误信息"""
        self.errors.append(error)

    def add_warning(self, warning: str):
        """添加警告信息"""
        self.warnings.append(warning)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'library_id': self.library_id,
            'library_name': self.library_name,
            'versions_total': self.versions_total,
            'versions_added': self.versions_added,
            'versions_with_features': self.versions_with_features,
            'licenses_added': self.licenses_added,
            'errors': self.errors,
            'warnings': self.warnings,
        }
