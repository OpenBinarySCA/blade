"""
API v1 Pydantic schemas for request/response models
"""
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field


# ============ File Operations Schemas ============

class UploadFileResponse(BaseModel):
    """File upload response model"""
    success: bool
    file_name: str
    file_path: str
    file_sha256: str


class DownloadFileRequest(BaseModel):
    """File download request model"""
    file_path: str


# ============ TPL Detection Task Schemas ============

class TPLDetectionTaskRequest(BaseModel):
    """TPL detection task request model"""
    file_minio_path: str
    file_name: str
    file_sha256: str


class TPLDetectionTaskResponse(BaseModel):
    """TPL detection task response model"""
    task_id: str
    file_minio_path: str
    status: str
    result_minio_path: Optional[str] = None
    result_local_path: Optional[str] = None
    error_message: Optional[str] = None


# ============ Result Chat Schemas ============

class ChatMessageRequest(BaseModel):
    """Chat message request model"""
    task_id: str
    message: str
    session_id: Optional[str] = None
    result_minio_path: Optional[str] = None


class ClearHistoryRequest(BaseModel):
    """Clear chat history request model"""
    session_id: str


class ClearHistoryResponse(BaseModel):
    """Clear chat history response model"""
    success: bool
    message: str


# ============ Data Management - Library Schemas ============

class CreateLibraryRequest(BaseModel):
    """Create library request model"""
    name: str = Field(..., min_length=1, max_length=255)
    vendor: Optional[str] = Field(None, max_length=255)
    source: List[str] = Field(..., min_items=1)
    homepage: Optional[str] = Field(None, max_length=255)
    giturl: Optional[str] = Field(None, max_length=255)
    alias: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    purl: Optional[str] = Field(None, max_length=500)
    language: Optional[List[str]] = None
    categories: Optional[List[str]] = None


class UpdateLibraryRequest(BaseModel):
    """Update library request model"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    vendor: Optional[str] = Field(None, max_length=255)
    source: Optional[List[str]] = Field(None, min_items=1)
    homepage: Optional[str] = Field(None, max_length=255)
    giturl: Optional[str] = Field(None, max_length=255)
    alias: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    purl: Optional[str] = Field(None, max_length=500)
    language: Optional[List[str]] = None
    categories: Optional[List[str]] = None


class LibraryResponse(BaseModel):
    """Library response model"""
    id: int
    name: str
    vendor: Optional[str]
    source: List[str]
    homepage: Optional[str]
    giturl: Optional[str]
    alias: Optional[str]
    description: Optional[str]
    purl: Optional[str]
    language: Optional[List[str]]
    categories: Optional[List[str]]
    created_at: Optional[str]
    updated_at: Optional[str]


class SourceCodeSummary(BaseModel):
    """SourceCode summary for library detail"""
    id: int
    commit_id: Optional[str]
    semantic_version_str: Optional[str]
    version_source: Optional[str]
    commit_datetime: Optional[str]
    has_features: bool = False  # 是否已提取特征


class LibraryDetailResponse(LibraryResponse):
    """Library detail with source codes"""
    source_codes: List[SourceCodeSummary] = []


class LibraryListResponse(BaseModel):
    """Library list with pagination"""
    items: List[LibraryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============ Data Management - SourceCode Schemas ============

class CreateSourceCodeRequest(BaseModel):
    """Create source code request model"""
    library_id: int
    commit_id: str = Field(..., max_length=40)
    version_source: Optional[str] = Field(None, max_length=100)
    original_version_strs: Optional[List[str]] = None
    semantic_version_str: Optional[str] = Field(None, max_length=100)
    commit_datetime: Optional[datetime] = None
    tag_datetime: Optional[datetime] = None


class UpdateSourceCodeRequest(BaseModel):
    """Update source code request model"""
    library_id: Optional[int] = None
    commit_id: Optional[str] = Field(None, max_length=40)
    version_source: Optional[str] = Field(None, max_length=100)
    original_version_strs: Optional[List[str]] = None
    semantic_version_str: Optional[str] = Field(None, max_length=100)
    commit_datetime: Optional[datetime] = None
    tag_datetime: Optional[datetime] = None


class SourceCodeResponse(BaseModel):
    """SourceCode response model"""
    id: int
    library_id: int
    commit_id: Optional[str]
    version_source: Optional[str]
    original_version_strs: Optional[List[str]]
    semantic_version_str: Optional[str]
    commit_datetime: Optional[str]
    tag_datetime: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    has_features: bool = False  # 是否已提取特征


class LibrarySummary(BaseModel):
    """Library summary for source code detail"""
    id: int
    name: str
    vendor: Optional[str]


class SourceCodeWithLibraryResponse(SourceCodeResponse):
    """SourceCode with library info"""
    library: Optional[LibrarySummary] = None


class SourceCodeListResponse(BaseModel):
    """SourceCode list with pagination"""
    items: List[SourceCodeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============ Data Management - Statistics Schemas ============

class LibraryStats(BaseModel):
    """Library-level statistics"""
    total: int
    complete_metadata: int
    has_features: int
    has_binaries: int
    has_vulnerabilities: int


class MetadataFieldsStats(BaseModel):
    """Metadata fields completeness statistics"""
    has_vendor: int
    has_giturl: int
    has_homepage: int
    has_description: int
    has_purl: int
    has_language: int
    has_source_code: int


class SourceCodeStats(BaseModel):
    """Source code statistics"""
    total: int
    avg_per_library: float
    libraries_with_source: int
    libraries_without_source: int


class BinaryStats(BaseModel):
    """Binary statistics"""
    total: int
    avg_per_library: float
    libraries_with_binary: int
    libraries_without_binary: int


class VulnerabilityStats(BaseModel):
    """Vulnerability statistics"""
    total: int
    affected_libraries: int
    high_risk_libraries: int
    safe_libraries: int


class LibraryStatisticsResponse(BaseModel):
    """Comprehensive library statistics"""
    library: LibraryStats
    metadata_fields: MetadataFieldsStats
    source_code: SourceCodeStats
    binary: BinaryStats
    vulnerability: VulnerabilityStats


# ============ Data Management - Library Status Schemas ============

class LibraryStatusResponse(BaseModel):
    """Library status response model"""
    id: int
    library_id: int
    has_basic_info: bool
    has_description: bool
    has_features: bool
    has_binaries: bool
    has_vulnerabilities: bool
    metadata_note: Optional[str]
    features_note: Optional[str]
    binaries_note: Optional[str]
    vulnerabilities_note: Optional[str]
    source_code_count: int
    string_feature_count: int
    function_name_feature_count: int
    binary_count: int
    vulnerability_count: int
    last_refreshed_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class UpdateLibraryStatusRequest(BaseModel):
    """Update library status request model (for manual updates)"""
    has_basic_info: Optional[bool] = None
    has_description: Optional[bool] = None
    has_features: Optional[bool] = None
    has_binaries: Optional[bool] = None
    has_vulnerabilities: Optional[bool] = None
    metadata_note: Optional[str] = None
    features_note: Optional[str] = None
    binaries_note: Optional[str] = None
    vulnerabilities_note: Optional[str] = None
    source_code_count: Optional[int] = None
    string_feature_count: Optional[int] = None
    function_name_feature_count: Optional[int] = None
    binary_count: Optional[int] = None
    vulnerability_count: Optional[int] = None


# ============ Data Management - Batch Refresh Task Schemas ============

class BatchRefreshTaskResponse(BaseModel):
    """Batch refresh task response model"""
    task_id: str
    status: str  # pending, running, success, partial_success, failed
    total_libraries: int
    completed_libraries: int
    failed_libraries: int
    current_library_id: Optional[int]
    current_library_name: Optional[str]
    failed_library_details: Dict[int, str] = {}  # {library_id: error_message}
    start_at: Optional[str]
    end_at: Optional[str]
    error_message: Optional[str]
    progress_percent: Optional[float] = None  # 前端展示用


# ============ Authentication Schemas ============

class GoogleLoginRequest(BaseModel):
    """Google OAuth login request"""
    id_token: str = Field(..., description="Google ID token from frontend")


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User information response"""
    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None
    is_admin: bool = False

    class Config:
        from_attributes = True


# ============ Report Generation Schemas ============

class GenerateReportRequest(BaseModel):
    """Report generation request model"""
    task_id: str = Field(..., description="Task ID to generate report for")


class GenerateReportResponse(BaseModel):
    """Report generation response model"""
    success: bool
    task_id: str
    report_minio_path: Optional[str] = None
    message: Optional[str] = None


# ============ License Schemas ============

class CreateLicenseRequest(BaseModel):
    """Create license request model"""
    name: str = Field(..., min_length=1, max_length=255)
    content: Optional[str] = None


class UpdateLicenseRequest(BaseModel):
    """Update license request model"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None


class LicenseResponse(BaseModel):
    """License response model"""
    id: int
    name: str
    content: Optional[str] = None
    content_hash: Optional[str] = None
    file_path: Optional[str] = None  # From relation table
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class LicenseListResponse(BaseModel):
    """License list with pagination"""
    items: List[LicenseResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AddLicenseToSourceCodeRequest(BaseModel):
    """Request to link a license to source code"""
    license_id: int
    file_path: Optional[str] = Field(None, max_length=500)
