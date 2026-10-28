from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, Float, create_engine, ARRAY, \
    Boolean, UniqueConstraint, Index, JSON
from sqlalchemy.orm import declarative_base, relationship, declared_attr
from sqlalchemy.sql import func

Base = declarative_base()


# 创建时间戳 Mixin
class TimestampMixin:
    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=func.now(), nullable=False, server_default=func.now())

    @declared_attr
    def updated_at(cls):
        return Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False, server_default=func.now())


# 2.1 库与源代码模块（4个表）
class Library(TimestampMixin, Base):
    __tablename__ = 'meta_libraries'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Basic fields from section 5.1.1
    name = Column(String(255), nullable=False, index=True)
    vendor = Column(String(255), index=True)
    source = Column(ARRAY(String(100)), nullable=False)
    homepage = Column(String(255))
    giturl = Column(String(255))  # Git repository URL (renamed from github_repo)
    alias = Column(String(255))
    description = Column(Text)  # Library description
    purl = Column(String(500))  # Package URL (SBOM standard identifier)
    language = Column(ARRAY(String(50)))  # Programming languages (e.g., ["C", "C++"])
    categories = Column(ARRAY(String(100)))  # Library categories/tags (e.g., ["crypto", "network"])

    # Relationships
    # One-to-many with SourceCode
    source_codes = relationship("SourceCode", back_populates="library")

    # One-to-one with LibraryStatus
    status = relationship("LibraryStatus", back_populates="library", uselist=False)

    # Many-to-many with Binary through BinaryToLibrary entity
    binary_relations = relationship("BinaryToLibrary", back_populates="library")
    binaries = relationship("Binary", secondary="r_library_binary", viewonly=True)

    # Many-to-many with Vulnerability through VulnerabilityToLibrary entity
    vulnerability_relations = relationship("VulnerabilityToLibrary", back_populates="library")
    vulnerabilities = relationship("Vulnerability", secondary="r_library_vulnerability", viewonly=True)

    # Many-to-many with StringFeature through StringToLibrary entity
    string_relations = relationship("StringToLibrary", back_populates="library")
    string_features = relationship("StringFeature", secondary="r_library_string", viewonly=True)

    # Many-to-many with FunctionNameFeature through FunctionNameToLibrary entity
    function_name_relations = relationship("FunctionNameToLibrary", back_populates="library")
    function_names = relationship("FunctionNameFeature", secondary="r_library_function_name", viewonly=True)

    # 添加复合唯一索引和其他索引
    __table_args__ = (
        UniqueConstraint('name', 'giturl', name='uix_library_name_giturl'),
        Index('idx_library_name', 'name'),
        Index('idx_library_vendor', 'vendor'),
    )


class LibraryStatus(TimestampMixin, Base):
    """
    Library status tracking table - stores completeness and feature statistics for each library
    """
    __tablename__ = 'meta_library_status'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    library_id = Column(BigInteger, ForeignKey('meta_libraries.id'), unique=True, nullable=False)

    # Completeness indicators
    has_basic_info = Column(Boolean, default=False, nullable=False)
    has_description = Column(Boolean, default=False, nullable=False)
    has_features = Column(Boolean, default=False, nullable=False)
    has_binaries = Column(Boolean, default=False, nullable=False)
    has_vulnerabilities = Column(Boolean, default=False, nullable=False)

    # Status notes - explanation for each status (only set when status is False/incomplete)
    metadata_note = Column(String(500), nullable=True)
    features_note = Column(String(500), nullable=True)
    binaries_note = Column(String(500), nullable=True)
    vulnerabilities_note = Column(String(500), nullable=True)

    # Counts
    source_code_count = Column(BigInteger, default=0, nullable=False)
    string_feature_count = Column(BigInteger, default=0, nullable=False)
    function_name_feature_count = Column(BigInteger, default=0, nullable=False)
    binary_count = Column(BigInteger, default=0, nullable=False)
    vulnerability_count = Column(BigInteger, default=0, nullable=False)

    # Last refresh timestamp
    last_refreshed_at = Column(DateTime, nullable=True)

    # Relationship back to Library
    library = relationship("Library", back_populates="status")

    __table_args__ = (
        Index('idx_library_status_library_id', 'library_id'),
    )


class SourceCode(TimestampMixin, Base):
    __tablename__ = 'meta_source_codes'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields from section 5.1.3
    commit_id = Column(String(40))  # Git commit ID
    version_source = Column(String(100))  # tag, branch, commit, or other version source
    original_version_strs = Column(ARRAY(String(100)))  # Original version strings, e.g., tags
    semantic_version_str = Column(String(100))  # Semantic version string, only one, this is a normalized version
    commit_datetime = Column(DateTime)  # Commit datetime in ISO 8601 format
    tag_datetime = Column(DateTime)  # Tag datetime in ISO 8601 format

    # Foreign key for Library (many-to-one)
    library_id = Column(BigInteger, ForeignKey('meta_libraries.id'))

    # Relationship back to Library
    library = relationship("Library", back_populates="source_codes")

    # One-to-many with ProjectFeature
    project_features = relationship("ProjectFeature", back_populates="source_code")

    # Many-to-many with Vulnerability through VulnerabilityToSourceCode entity
    vulnerability_relations = relationship("VulnerabilityToSourceCode", back_populates="source_code")
    vulnerabilities = relationship("Vulnerability", secondary="r_source_code_vulnerability", viewonly=True)

    # Many-to-many with Binary through BinaryToSourceCode entity
    binary_relations = relationship("BinaryToSourceCode", back_populates="source_code")
    binaries = relationship("Binary", secondary="r_source_code_binary", viewonly=True)

    # Many-to-many with License through LicenseToSourceCode entity
    license_relations = relationship("LicenseToSourceCode", back_populates="source_code")
    licenses = relationship("License", secondary="r_source_code_license", viewonly=True)

    __table_args__ = (
        UniqueConstraint('library_id', 'commit_id', name='uix_source_code_library_commit'),  # 添加这行！
        Index('idx_source_code_library_version', 'library_id', 'semantic_version_str'),
        Index('idx_source_code_commit', 'commit_id'),
        Index('idx_source_code_library', 'library_id'),
    )


# 2.2 特征提取模块（9个表）
class ProjectFeature(TimestampMixin, Base):
    __tablename__ = 'feature_projects'

    # 使用 source_code_id 作为主键
    id = Column(BigInteger, ForeignKey('meta_source_codes.id'), primary_key=True, nullable=False)

    # Fields from section 5.2.1
    name = Column(String(255))
    project_size_mb = Column(Float)
    total_src_file = Column(BigInteger)
    failed_src_file = Column(BigInteger)
    exception_src_file = Column(BigInteger)
    function_count = Column(BigInteger)
    distinct_string_count = Column(BigInteger)
    extraction_succeed = Column(Boolean, default=True)
    extraction_log = Column(Text)

    # Relationship back to SourceCode
    source_code = relationship("SourceCode", back_populates="project_features")

    # One-to-many with FileMeta
    file_metas = relationship("FileMeta", back_populates="project_feature")

    # Many-to-many with StringFeature through StringToProject entity
    string_relations = relationship("StringToProject", back_populates="project")
    string_features = relationship("StringFeature", secondary="r_project_string", viewonly=True)

    # Many-to-many with FunctionNameFeature through FunctionNameToProject entity
    function_name_relations = relationship("FunctionNameToProject", back_populates="project")
    function_names = relationship("FunctionNameFeature", secondary="r_project_function_name", viewonly=True)

    __table_args__ = (
        Index('idx_project_feature_source_code', 'id'),
    )


class FileMeta(TimestampMixin, Base):
    __tablename__ = 'feature_file_metas'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields from section 5.2.2
    path = Column(String(512))
    file_sha256 = Column(String(64))

    # Foreign key for ProjectFeature (many-to-one)
    project_feature_id = Column(BigInteger, ForeignKey('feature_projects.id'))

    # Many-to-one with ProjectFeature
    project_feature = relationship("ProjectFeature", back_populates="file_metas")

    # Many-to-one with FileFeature
    file_feature_id = Column(BigInteger, ForeignKey('feature_files.id'))
    file_feature = relationship("FileFeature", back_populates="file_metas")

    __table_args__ = (
        UniqueConstraint('path', 'file_sha256', 'project_feature_id', 'file_feature_id',
                         name='uix_file_metas_unique'),
        Index('idx_file_metas_file_feature_id', 'file_feature_id'),
        Index('idx_file_metas_project_feature_id', 'project_feature_id'),
    )


class FileFeature(TimestampMixin, Base):
    __tablename__ = 'feature_files'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields from section 5.2.3
    file_sha256 = Column(String(64), unique=True, index=True)
    name = Column(String(255))
    extension = Column(String(50))
    file_size_kb = Column(Float)
    function_num = Column(BigInteger)
    distinct_string_num = Column(BigInteger)
    global_strings = Column(JSON)  # 改为JSON类型
    extraction_succeed = Column(Boolean, default=True)
    extraction_log = Column(Text)

    # One-to-many with FileMeta
    file_metas = relationship("FileMeta", back_populates="file_feature")

    # One-to-one with StringFeature
    string_feature_id = Column(BigInteger, ForeignKey('feature_strings.id'), unique=True, nullable=True)
    string_feature = relationship("StringFeature", back_populates="file_feature", uselist=False)

    # Many-to-many with StringFeature through StringToFile entity
    string_relations = relationship("StringToFile", back_populates="file")
    string_features = relationship("StringFeature", secondary="r_file_string", viewonly=True)

    # Many-to-many with FunctionNameFeature through FunctionNameToFile entity
    function_name_relations = relationship("FunctionNameToFile", back_populates="file")
    function_names = relationship("FunctionNameFeature", secondary="r_file_function_name", viewonly=True)

    __table_args__ = (
        Index('idx_file_feature_sha256', 'file_sha256'),  # 已有unique，但再加个普通索引用于查询
    )


class FunctionNameFeature(TimestampMixin, Base):
    __tablename__ = 'feature_function_names'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields
    function_name = Column(String(255))
    function_hash = Column(String(64), unique=True, index=True)

    # Many-to-many relationship with Library through FunctionNameToLibrary entity
    library_relations = relationship("FunctionNameToLibrary", back_populates="function_name")
    libraries = relationship("Library", secondary="r_library_function_name", viewonly=True)

    # Many-to-many relationship with ProjectFeature through FunctionNameToProject entity
    project_relations = relationship("FunctionNameToProject", back_populates="function_name")
    projects = relationship("ProjectFeature", secondary="r_project_function_name", viewonly=True)

    # Many-to-many relationship with FileFeature through FunctionNameToFile entity
    file_relations = relationship("FunctionNameToFile", back_populates="function_name")
    files = relationship("FileFeature", secondary="r_file_function_name", viewonly=True)

    __table_args__ = (
        Index('idx_function_name', 'function_name'),
        Index('idx_function_hash', 'function_hash'),
    )


class FunctionNameToFile(TimestampMixin, Base):
    __tablename__ = 'r_file_function_name'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Foreign keys for FunctionName and File
    function_name_id = Column(BigInteger, ForeignKey('feature_function_names.id'), nullable=False)
    file_id = Column(BigInteger, ForeignKey('feature_files.id'), nullable=False)

    # Context field for storing additional information
    context = Column(String(255))

    # Relationships to FunctionName and File
    function_name = relationship("FunctionNameFeature", back_populates="file_relations")
    file = relationship("FileFeature", back_populates="function_name_relations")

    # Add unique constraint for function_name-file pair
    __table_args__ = (
        UniqueConstraint('function_name_id', 'file_id', name='uix_function_name_file'),
        Index('idx_fn_to_file_file_id', 'file_id'),
    )


class FunctionNameToProject(TimestampMixin, Base):
    __tablename__ = 'r_project_function_name'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Foreign keys for FunctionName and Project
    function_name_id = Column(BigInteger, ForeignKey('feature_function_names.id'), nullable=False)
    project_id = Column(BigInteger, ForeignKey('feature_projects.id'), nullable=False)

    # Context field for storing additional information
    context = Column(String(255))

    # Relationships to FunctionName and Project
    function_name = relationship("FunctionNameFeature", back_populates="project_relations")
    project = relationship("ProjectFeature", back_populates="function_name_relations")

    # Add unique constraint for function_name-project pair
    __table_args__ = (UniqueConstraint('function_name_id', 'project_id', name='uix_function_name_project'),)


class FunctionNameToLibrary(TimestampMixin, Base):
    __tablename__ = 'r_library_function_name'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Foreign keys for FunctionName and Library
    function_name_id = Column(BigInteger, ForeignKey('feature_function_names.id'), nullable=False)
    library_id = Column(BigInteger, ForeignKey('meta_libraries.id'), nullable=False)

    # Context field for storing additional information
    context = Column(String(255))

    # Relationships to FunctionName and Library
    function_name = relationship("FunctionNameFeature", back_populates="library_relations")
    library = relationship("Library", back_populates="function_name_relations")

    # Add unique constraint and indexes for efficient querying
    __table_args__ = (
        UniqueConstraint('function_name_id', 'library_id', name='uix_function_name_library'),
        Index('idx_fn_to_library_function_name_id', 'function_name_id'),
        Index('idx_fn_to_library_library_id', 'library_id'),
    )


class StringFeature(TimestampMixin, Base):
    __tablename__ = 'feature_strings'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields from section 5.2.5
    string_value = Column(Text)
    string_hash = Column(String(64), unique=True, index=True)

    # Many-to-many relationship with Library through StringToLibrary entity
    library_relations = relationship("StringToLibrary", back_populates="string")
    libraries = relationship("Library", secondary="r_library_string", viewonly=True)

    # Many-to-many relationship with ProjectFeature through StringToProject entity
    project_relations = relationship("StringToProject", back_populates="string")
    projects = relationship("ProjectFeature", secondary="r_project_string", viewonly=True)

    # One-to-one with FileFeature
    file_feature = relationship("FileFeature", back_populates="string_feature", uselist=False)

    # Many-to-many relationship with FileFeature through StringToFile entity
    file_relations = relationship("StringToFile", back_populates="string")
    files = relationship("FileFeature", secondary="r_file_string", viewonly=True)

    __table_args__ = (
        Index('idx_string_value', 'string_value'),
        Index('idx_string_hash', 'string_hash'),
    )


class StringToFile(TimestampMixin, Base):
    __tablename__ = 'r_file_string'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Foreign keys for String and File
    string_id = Column(BigInteger, ForeignKey('feature_strings.id'), nullable=False)
    file_id = Column(BigInteger, ForeignKey('feature_files.id'), nullable=False)

    # Context field for storing additional information
    context = Column(String(255))

    # Relationships to String and File
    string = relationship("StringFeature", back_populates="file_relations")
    file = relationship("FileFeature", back_populates="string_relations")

    # Add unique constraint for string-file pair
    __table_args__ = (
        UniqueConstraint('string_id', 'file_id', name='uix_string_file'),
        Index('idx_str_to_file_file_id', 'file_id'),
    )


class StringToProject(TimestampMixin, Base):
    __tablename__ = 'r_project_string'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Foreign keys for String and Project
    string_id = Column(BigInteger, ForeignKey('feature_strings.id'), nullable=False)
    project_id = Column(BigInteger, ForeignKey('feature_projects.id'), nullable=False)

    # Context field for storing additional information
    context = Column(String(255))

    # Relationships to String and Project
    string = relationship("StringFeature", back_populates="project_relations")
    project = relationship("ProjectFeature", back_populates="string_relations")

    # Add unique constraint for string-project pair
    __table_args__ = (UniqueConstraint('string_id', 'project_id', name='uix_string_project'),)


class StringToLibrary(TimestampMixin, Base):
    __tablename__ = 'r_library_string'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Foreign keys for String and Library
    string_id = Column(BigInteger, ForeignKey('feature_strings.id'), nullable=False)
    library_id = Column(BigInteger, ForeignKey('meta_libraries.id'), nullable=False)

    # Context field for storing additional information
    context = Column(String(255))

    # Relationships to String and Library
    string = relationship("StringFeature", back_populates="library_relations")
    library = relationship("Library", back_populates="string_relations")

    # Add unique constraint and indexes for efficient querying
    __table_args__ = (
        UniqueConstraint('string_id', 'library_id', name='uix_string_library'),
        Index('idx_string_to_library_string_id', 'string_id'),
        Index('idx_string_to_library_library_id', 'library_id'),
    )


# 2.3 二进制文件模块（3个表）
class Binary(TimestampMixin, Base):
    __tablename__ = 'meta_binaries'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields from section 5.3.1
    binary_name = Column(String(255))
    binary_hash = Column(String(64), index=True)
    architecture = Column(String(50))
    file_size = Column(BigInteger)
    compiler_info = Column(String(255))
    linked_libraries = Column(Text)

    # Many-to-many relationship with Library through BinaryToLibrary entity
    library_relations = relationship("BinaryToLibrary", back_populates="binary")
    libraries = relationship("Library", secondary="r_library_binary", viewonly=True)

    # Many-to-many relationship with SourceCode through BinaryToSourceCode entity
    source_code_relations = relationship("BinaryToSourceCode", back_populates="binary")
    source_codes = relationship("SourceCode", secondary="r_source_code_binary", viewonly=True)

    # Many-to-many relationship with Vulnerability through VulnerabilityToBinary entity
    vulnerability_relations = relationship("VulnerabilityToBinary", back_populates="binary")
    vulnerabilities = relationship("Vulnerability", secondary="r_binary_vulnerability", viewonly=True)


class BinaryToLibrary(TimestampMixin, Base):
    __tablename__ = 'r_library_binary'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields from section 5.3.2
    confidence = Column(Float)
    detection_method = Column(String(100))

    # Foreign keys for Binary and Library
    binary_id = Column(BigInteger, ForeignKey('meta_binaries.id'), nullable=False)
    library_id = Column(BigInteger, ForeignKey('meta_libraries.id'), nullable=False)

    # Relationships to Binary and Library
    binary = relationship("Binary", back_populates="library_relations")
    library = relationship("Library", back_populates="binary_relations")

    # Add unique constraint for binary-library pair
    __table_args__ = (UniqueConstraint('binary_id', 'library_id', name='uix_binary_library'),)


class BinaryToSourceCode(TimestampMixin, Base):
    __tablename__ = 'r_source_code_binary'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields from section 5.3.3
    confidence = Column(Float)
    detection_method = Column(String(100))

    # Foreign keys for Binary and SourceCode
    binary_id = Column(BigInteger, ForeignKey('meta_binaries.id'), nullable=False)
    source_code_id = Column(BigInteger, ForeignKey('meta_source_codes.id'), nullable=False)

    # Relationships to Binary and SourceCode
    binary = relationship("Binary", back_populates="source_code_relations")
    source_code = relationship("SourceCode", back_populates="binary_relations")

    # Add unique constraint for binary-source_code pair
    __table_args__ = (UniqueConstraint('binary_id', 'source_code_id', name='uix_binary_source_code'),)


# 2.4 漏洞模块（4个表）
class Vulnerability(TimestampMixin, Base):
    __tablename__ = 'meta_vulnerabilities'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields from section 5.4.1
    cve_id = Column(String(20), index=True)
    source = Column(String(50))
    severity = Column(String(20))
    description = Column(Text)
    published_date = Column(DateTime)
    affected_versions = Column(Text)
    fixed_versions = Column(Text)
    references = Column(Text)

    # Many-to-many relationship with Library through VulnerabilityToLibrary entity
    library_relations = relationship("VulnerabilityToLibrary", back_populates="vulnerability")
    libraries = relationship("Library", secondary="r_library_vulnerability", viewonly=True)

    # Many-to-many relationship with SourceCode through VulnerabilityToSourceCode entity
    source_code_relations = relationship("VulnerabilityToSourceCode", back_populates="vulnerability")
    source_codes = relationship("SourceCode", secondary="r_source_code_vulnerability", viewonly=True)

    # Many-to-many relationship with Binary through VulnerabilityToBinary entity
    binary_relations = relationship("VulnerabilityToBinary", back_populates="vulnerability")
    binaries = relationship("Binary", secondary="r_binary_vulnerability", viewonly=True)


class VulnerabilityToLibrary(TimestampMixin, Base):
    __tablename__ = 'r_library_vulnerability'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields from section 5.4.2
    confirmed = Column(Boolean, default=False)
    notes = Column(Text)

    # Foreign keys for Vulnerability and Library
    vulnerability_id = Column(BigInteger, ForeignKey('meta_vulnerabilities.id'), nullable=False)
    library_id = Column(BigInteger, ForeignKey('meta_libraries.id'), nullable=False)

    # Relationships to Vulnerability and Library
    vulnerability = relationship("Vulnerability", back_populates="library_relations")
    library = relationship("Library", back_populates="vulnerability_relations")

    # Add unique constraint for vulnerability-library pair
    __table_args__ = (UniqueConstraint('vulnerability_id', 'library_id', name='uix_vulnerability_library'),)


class VulnerabilityToSourceCode(TimestampMixin, Base):
    __tablename__ = 'r_source_code_vulnerability'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields from section 5.4.3
    confirmed = Column(Boolean, default=False)
    notes = Column(Text)

    # Foreign keys for Vulnerability and SourceCode
    vulnerability_id = Column(BigInteger, ForeignKey('meta_vulnerabilities.id'), nullable=False)
    source_code_id = Column(BigInteger, ForeignKey('meta_source_codes.id'), nullable=False)

    # Relationships to Vulnerability and SourceCode
    vulnerability = relationship("Vulnerability", back_populates="source_code_relations")
    source_code = relationship("SourceCode", back_populates="vulnerability_relations")

    # Add unique constraint for vulnerability-source_code pair
    __table_args__ = (UniqueConstraint('vulnerability_id', 'source_code_id', name='uix_vulnerability_source_code'),)


class VulnerabilityToBinary(TimestampMixin, Base):
    __tablename__ = 'r_binary_vulnerability'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Fields from section 5.4.4
    confirmed = Column(Boolean, default=False)
    notes = Column(Text)

    # Foreign keys for Vulnerability and Binary
    vulnerability_id = Column(BigInteger, ForeignKey('meta_vulnerabilities.id'), nullable=False)
    binary_id = Column(BigInteger, ForeignKey('meta_binaries.id'), nullable=False)

    # Relationships to Vulnerability and Binary
    vulnerability = relationship("Vulnerability", back_populates="binary_relations")
    binary = relationship("Binary", back_populates="vulnerability_relations")

    # Add unique constraint for vulnerability-binary pair
    __table_args__ = (UniqueConstraint('vulnerability_id', 'binary_id', name='uix_vulnerability_binary'),)


# 2.5 License 模块（2个表）
class License(TimestampMixin, Base):
    """
    License table - stores license full text with deduplication via content_hash
    """
    __tablename__ = 'meta_licenses'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # License name (e.g., "MIT License", "Apache-2.0")
    name = Column(String(255), nullable=False, index=True)

    # Full license text content
    content = Column(Text)

    # SHA256 hash of content for deduplication
    content_hash = Column(String(64), unique=True, index=True)

    # Many-to-many relationship with SourceCode through LicenseToSourceCode entity
    source_code_relations = relationship("LicenseToSourceCode", back_populates="license")
    source_codes = relationship("SourceCode", secondary="r_source_code_license", viewonly=True)

    __table_args__ = (
        Index('idx_license_name', 'name'),
        Index('idx_license_content_hash', 'content_hash'),
    )


class LicenseToSourceCode(TimestampMixin, Base):
    """
    Relation table linking SourceCode to License with file path information
    """
    __tablename__ = 'r_source_code_license'
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)

    # Foreign keys
    source_code_id = Column(BigInteger, ForeignKey('meta_source_codes.id'), nullable=False)
    license_id = Column(BigInteger, ForeignKey('meta_licenses.id'), nullable=False)

    # Relative file path in source code (e.g., "LICENSE", "COPYING", "licenses/MIT.txt")
    file_path = Column(String(500))

    # Relationships
    source_code = relationship("SourceCode", back_populates="license_relations")
    license = relationship("License", back_populates="source_code_relations")

    __table_args__ = (
        UniqueConstraint('source_code_id', 'license_id', 'file_path', name='uix_source_code_license_path'),
        Index('idx_license_source_code', 'source_code_id'),
        Index('idx_license_license', 'license_id'),
    )


def create_all_tables(drop_existing: bool = False):
    """
    创建所有表（public schema）

    Args:
        drop_existing: 是否先删除现有表（危险操作，仅用于开发）
    """
    from ...config import settings

    engine = create_engine(
        url=settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=-1,
        pool_recycle=3600,
    )

    if drop_existing:
        Base.metadata.drop_all(engine)

    Base.metadata.create_all(engine)


if __name__ == '__main__':
    create_all_tables()
    print("Tables created successfully.")