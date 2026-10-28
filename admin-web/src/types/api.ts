// Authentication Types
export interface User {
  id: number;
  username: string;
  email: string | null;
  full_name: string | null;
  profile_picture: string | null;
  is_admin: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// Library Types
export interface Library {
  id: number;
  name: string;
  vendor: string | null;
  source: string[];
  homepage: string | null;
  giturl: string | null;
  alias: string | null;
  description: string | null;
  purl: string | null;
  language: string[] | null;
  categories: string[] | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface LibraryListResponse {
  items: Library[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LibraryDetail extends Library {
  source_codes: SourceCodeSummary[];
}

export interface SourceCodeSummary {
  id: number;
  commit_id: string | null;
  semantic_version_str: string | null;
  version_source: string | null;
  commit_datetime: string | null;
  has_features?: boolean;  // 是否已提取特征
}

// Source Code Types
export interface SourceCode {
  id: number;
  library_id: number;
  commit_id: string | null;
  version_source: string | null;
  original_version_strs: string[] | null;
  semantic_version_str: string | null;
  commit_datetime: string | null;
  tag_datetime: string | null;
  created_at: string | null;
  updated_at: string | null;
  has_features: boolean;  // 是否已提取特征
}

export interface SourceCodeListResponse {
  items: SourceCode[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Library Status Types
export interface LibraryStatus {
  id: number;
  library_id: number;
  has_basic_info: boolean;
  has_description: boolean;
  has_features: boolean;
  has_binaries: boolean;
  has_vulnerabilities: boolean;
  metadata_note: string | null;
  features_note: string | null;
  binaries_note: string | null;
  vulnerabilities_note: string | null;
  source_code_count: number;
  string_feature_count: number;
  function_name_feature_count: number;
  binary_count: number;
  vulnerability_count: number;
  last_refreshed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// Statistics Types
export interface LibraryStats {
  total: number;
  complete_metadata: number;
  has_features: number;
  has_binaries: number;
  has_vulnerabilities: number;
}

export interface MetadataFieldsStats {
  has_vendor: number;
  has_giturl: number;
  has_homepage: number;
  has_description: number;
  has_purl: number;
  has_language: number;
  has_source_code: number;
}

export interface SourceCodeStats {
  total: number;
  avg_per_library: number;
  libraries_with_source: number;
  libraries_without_source: number;
}

export interface BinaryStats {
  total: number;
  avg_per_library: number;
  libraries_with_binary: number;
  libraries_without_binary: number;
}

export interface VulnerabilityStats {
  total: number;
  affected_libraries: number;
  high_risk_libraries: number;
  safe_libraries: number;
}

export interface Statistics {
  library: LibraryStats;
  metadata_fields: MetadataFieldsStats;
  source_code: SourceCodeStats;
  binary: BinaryStats;
  vulnerability: VulnerabilityStats;
}

// Batch Refresh Task Types
export interface BatchRefreshTask {
  task_id: string;
  status: string;
  total_libraries: number;
  completed_libraries: number;
  failed_libraries: number;
  current_library_id: number | null;
  current_library_name: string | null;
  failed_library_details: Record<number, string>;
  start_at: string | null;
  end_at: string | null;
  error_message: string | null;
  progress_percent: number | null;
}

// Request Types
export interface CreateLibraryRequest {
  name: string;
  vendor?: string;
  source: string[];
  homepage?: string;
  giturl?: string;
  alias?: string;
  description?: string;
  purl?: string;
  language?: string[];
  categories?: string[];
}

export interface UpdateLibraryRequest {
  name?: string;
  vendor?: string;
  source?: string[];
  homepage?: string;
  giturl?: string;
  alias?: string;
  description?: string;
  purl?: string;
  language?: string[];
  categories?: string[];
}

export interface CreateSourceCodeRequest {
  library_id: number;
  commit_id: string;
  version_source?: string;
  original_version_strs?: string[];
  semantic_version_str?: string;
  commit_datetime?: string;
  tag_datetime?: string;
}

export interface UpdateSourceCodeRequest {
  library_id?: number;
  commit_id?: string;
  version_source?: string;
  original_version_strs?: string[];
  semantic_version_str?: string;
  commit_datetime?: string;
  tag_datetime?: string;
}

// System Settings Types
export interface SystemSetting {
  key: string;
  value: string | number | boolean | Record<string, unknown> | unknown[];
  value_type: string;
  category: string;
  description: string | null;
  is_public: boolean;
  updated_at: string | null;
}

export interface UpdateSettingRequest {
  value: string;
  value_type?: string;
  category?: string;
  description?: string;
  is_public?: boolean;
}

export interface CreateSettingRequest {
  key: string;
  value: string;
  value_type?: string;
  category?: string;
  description?: string;
  is_public?: boolean;
}

// User Management Types
export interface UserListResponse {
  items: User[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UserStats {
  total_users: number;
  admin_users: number;
  regular_users: number;
}

export interface UpdateAdminStatusRequest {
  is_admin: boolean;
}

// Analysis Task Types
export interface TaskUserInfo {
  id: number;
  username: string;
  email: string | null;
}

export interface AnalysisTask {
  task_id: string;
  user_id: number | null;
  user: TaskUserInfo | null;
  engine_version: string;
  input_file_sha256: string;
  file_name: string;
  file_minio_path: string;
  status: string;
  start_at: string | null;
  end_at: string | null;
  result_minio_path: string | null;
  report_minio_path: string | null;
  error_message: string | null;
  analysis_total_files: number;
  analysis_completed_files: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface TaskListResponse {
  items: AnalysisTask[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TaskStats {
  total: number;
  pending: number;
  running: number;
  success: number;
  failed: number;
  cancelled: number;
}

// Task Cancel Response Types
export interface CancelTaskResponse {
  success: boolean;
  message: string;
  task_id: string;
}

export interface BatchCancelResult {
  task_id: string;
  success: boolean;
  error?: string;
}

export interface BatchCancelResponse {
  results: BatchCancelResult[];
}

// System Monitor Types
export interface CPUInfo {
  percent: number;
  count: number;
  count_logical: number;
  freq_current: number | null;
  freq_max: number | null;
}

export interface MemoryInfo {
  total: number;
  available: number;
  used: number;
  percent: number;
}

export interface DiskInfo {
  device: string;
  mountpoint: string;
  total: number;
  used: number;
  free: number;
  percent: number;
}

export interface DiskIOInfo {
  read_bytes: number;
  write_bytes: number;
  read_count: number;
  write_count: number;
}

export interface NetworkIOInfo {
  bytes_sent: number;
  bytes_recv: number;
  packets_sent: number;
  packets_recv: number;
}

export interface SystemStatus {
  timestamp: string;
  cpu: CPUInfo;
  memory: MemoryInfo;
  disks: DiskInfo[];
  disk_io: DiskIOInfo | null;
  network_io: NetworkIOInfo;
  boot_time: string;
  uptime_seconds: number;
}

// Library Related Data Types

export interface Vulnerability {
  id: number;
  cve_id: string | null;
  source: string | null;
  severity: string | null;
  description: string | null;
  published_date: string | null;
  affected_versions: string | null;
  fixed_versions: string | null;
  references: string | null;
  confirmed: boolean;
  notes: string | null;
  created_at: string | null;
}

export interface VulnerabilityListResponse {
  items: Vulnerability[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Binary {
  id: number;
  binary_name: string | null;
  binary_hash: string | null;
  architecture: string | null;
  file_size: number | null;
  compiler_info: string | null;
  linked_libraries: string | null;
  confidence: number | null;
  detection_method: string | null;
  created_at: string | null;
}

export interface BinaryListResponse {
  items: Binary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface StringFeature {
  id: number;
  string_value: string | null;
  string_hash: string | null;
  context: string | null;
}

export interface StringFeatureListResponse {
  items: StringFeature[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FunctionNameFeature {
  id: number;
  function_name: string | null;
  function_hash: string | null;
  context: string | null;
}

export interface FunctionNameListResponse {
  items: FunctionNameFeature[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// License Types

export interface License {
  id: number;
  name: string;
  content: string | null;
  content_hash: string | null;
  file_path: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface LicenseListResponse {
  items: License[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CreateLicenseRequest {
  name: string;
  content?: string;
}

export interface AddLicenseToSourceCodeRequest {
  license_id: number;
  file_path?: string;
}

// Sample Types
export interface Sample {
  id: number;
  file_name: string;
  description: string;
  task_id: string;
  sort_order: number;
  is_active: boolean;
  view_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface SampleListResponse {
  items: Sample[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SampleView {
  id: number;
  sample_id: number;
  ip_address: string;
  user_agent: string | null;
  viewed_at: string | null;
}

export interface SampleViewListResponse {
  items: SampleView[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CreateSampleRequest {
  file_name: string;
  description: string;
  task_id: string;
  sort_order?: number;
  is_active?: boolean;
}

export interface UpdateSampleRequest {
  file_name?: string;
  description?: string;
  task_id?: string;
  sort_order?: number;
  is_active?: boolean;
}
