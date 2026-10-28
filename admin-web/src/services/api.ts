import axios from 'axios';
import type {
  User,
  TokenResponse,
  Library,
  LibraryListResponse,
  LibraryDetail,
  LibraryStatus,
  SourceCode,
  SourceCodeListResponse,
  Statistics,
  BatchRefreshTask,
  CreateLibraryRequest,
  UpdateLibraryRequest,
  CreateSourceCodeRequest,
  UpdateSourceCodeRequest,
  SystemSetting,
  UpdateSettingRequest,
  UserListResponse,
  UserStats,
  UpdateAdminStatusRequest,
  AnalysisTask,
  TaskListResponse,
  TaskStats,
  CancelTaskResponse,
  BatchCancelResponse,
  SystemStatus,
  VulnerabilityListResponse,
  BinaryListResponse,
  StringFeatureListResponse,
  FunctionNameListResponse,
  License,
  LicenseListResponse,
  CreateLicenseRequest,
  AddLicenseToSourceCodeRequest,
  Sample,
  SampleListResponse,
  SampleViewListResponse,
  CreateSampleRequest,
  UpdateSampleRequest,
} from '../types/api';

const API_BASE_URL = '/api/v1';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  async googleLogin(idToken: string): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/auth/google', {
      id_token: idToken,
    });
    return response.data;
  },

  async getCurrentUser(): Promise<User> {
    const response = await api.get<User>('/auth/me');
    return response.data;
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout');
  },
};

// Statistics API
export const statsAPI = {
  async getStatistics(): Promise<Statistics> {
    const response = await api.get<Statistics>('/statistics');
    return response.data;
  },
};

// Library API
export const libraryAPI = {
  async getLibraries(
    page: number = 1,
    pageSize: number = 20,
    search?: string,
    vendor?: string,
    orderBy: string = 'created_at',
    orderDesc: boolean = true
  ): Promise<LibraryListResponse> {
    const params: Record<string, unknown> = {
      page,
      page_size: pageSize,
      order_by: orderBy,
      order_desc: orderDesc,
    };
    if (search) params.search = search;
    if (vendor) params.vendor = vendor;
    const response = await api.get<LibraryListResponse>('/libraries', { params });
    return response.data;
  },

  async getLibrary(id: number): Promise<LibraryDetail> {
    const response = await api.get<LibraryDetail>(`/libraries/${id}`);
    return response.data;
  },

  async createLibrary(data: CreateLibraryRequest): Promise<Library> {
    const response = await api.post<Library>('/libraries', data);
    return response.data;
  },

  async updateLibrary(id: number, data: UpdateLibraryRequest): Promise<Library> {
    const response = await api.put<Library>(`/libraries/${id}`, data);
    return response.data;
  },

  async deleteLibrary(id: number, cascade: boolean = false): Promise<void> {
    await api.delete(`/libraries/${id}`, { params: { cascade } });
  },

  async getLibraryStatus(id: number): Promise<LibraryStatus> {
    const response = await api.get<LibraryStatus>(`/libraries/${id}/status`);
    return response.data;
  },

  async refreshLibraryStatus(id: number): Promise<LibraryStatus> {
    const response = await api.post<LibraryStatus>(`/libraries/${id}/status/refresh`);
    return response.data;
  },

  async batchRefreshStatus(): Promise<BatchRefreshTask> {
    const response = await api.post<BatchRefreshTask>('/libraries/batch-refresh-status');
    return response.data;
  },

  async getBatchRefreshStatus(taskId: string): Promise<BatchRefreshTask> {
    const response = await api.get<BatchRefreshTask>(`/libraries/batch-refresh-status/${taskId}`);
    return response.data;
  },

  // Library related data
  async getLibraryVulnerabilities(
    libraryId: number,
    page: number = 1,
    pageSize: number = 20
  ): Promise<VulnerabilityListResponse> {
    const params = { page, page_size: pageSize };
    const response = await api.get<VulnerabilityListResponse>(
      `/libraries/${libraryId}/vulnerabilities`,
      { params }
    );
    return response.data;
  },

  async getLibraryBinaries(
    libraryId: number,
    page: number = 1,
    pageSize: number = 20
  ): Promise<BinaryListResponse> {
    const params = { page, page_size: pageSize };
    const response = await api.get<BinaryListResponse>(
      `/libraries/${libraryId}/binaries`,
      { params }
    );
    return response.data;
  },

  async getLibraryStringFeatures(
    libraryId: number,
    page: number = 1,
    pageSize: number = 50,
    search?: string
  ): Promise<StringFeatureListResponse> {
    const params: Record<string, unknown> = { page, page_size: pageSize };
    if (search) params.search = search;
    const response = await api.get<StringFeatureListResponse>(
      `/libraries/${libraryId}/string-features`,
      { params }
    );
    return response.data;
  },

  async getLibraryFunctionNames(
    libraryId: number,
    page: number = 1,
    pageSize: number = 50,
    search?: string
  ): Promise<FunctionNameListResponse> {
    const params: Record<string, unknown> = { page, page_size: pageSize };
    if (search) params.search = search;
    const response = await api.get<FunctionNameListResponse>(
      `/libraries/${libraryId}/function-names`,
      { params }
    );
    return response.data;
  },

  async getLibraryLicenses(
    libraryId: number,
    page: number = 1,
    pageSize: number = 20
  ): Promise<LicenseListResponse> {
    const params = { page, page_size: pageSize };
    const response = await api.get<LicenseListResponse>(
      `/libraries/${libraryId}/licenses`,
      { params }
    );
    return response.data;
  },
};

// License API
export const licenseAPI = {
  async createLicense(data: CreateLicenseRequest): Promise<License> {
    const response = await api.post<License>('/licenses', data);
    return response.data;
  },

  async getSourceCodeLicenses(
    sourceCodeId: number,
    page: number = 1,
    pageSize: number = 20
  ): Promise<LicenseListResponse> {
    const params = { page, page_size: pageSize };
    const response = await api.get<LicenseListResponse>(
      `/source_codes/${sourceCodeId}/licenses`,
      { params }
    );
    return response.data;
  },

  async addLicenseToSourceCode(
    sourceCodeId: number,
    data: AddLicenseToSourceCodeRequest
  ): Promise<License> {
    const response = await api.post<License>(
      `/source_codes/${sourceCodeId}/licenses`,
      data
    );
    return response.data;
  },
};

// Source Code API
export const sourceCodeAPI = {
  async getSourceCodes(
    page: number = 1,
    pageSize: number = 20,
    libraryId?: number,
    versionSource?: string,
    orderBy: string = 'commit_datetime',
    orderDesc: boolean = true
  ): Promise<SourceCodeListResponse> {
    const params: Record<string, unknown> = {
      page,
      page_size: pageSize,
      order_by: orderBy,
      order_desc: orderDesc,
    };
    if (libraryId) params.library_id = libraryId;
    if (versionSource) params.version_source = versionSource;
    const response = await api.get<SourceCodeListResponse>('/source_codes', { params });
    return response.data;
  },

  async getLibrarySourceCodes(
    libraryId: number,
    page: number = 1,
    pageSize: number = 50,
    orderBy: string = 'commit_datetime',
    orderDesc: boolean = true
  ): Promise<SourceCodeListResponse> {
    const params = {
      page,
      page_size: pageSize,
      order_by: orderBy,
      order_desc: orderDesc,
    };
    const response = await api.get<SourceCodeListResponse>(
      `/libraries/${libraryId}/source_codes`,
      { params }
    );
    return response.data;
  },

  async getSourceCode(id: number): Promise<SourceCode> {
    const response = await api.get<SourceCode>(`/source_codes/${id}`);
    return response.data;
  },

  async createSourceCode(data: CreateSourceCodeRequest): Promise<SourceCode> {
    const response = await api.post<SourceCode>('/source_codes', data);
    return response.data;
  },

  async updateSourceCode(id: number, data: UpdateSourceCodeRequest): Promise<SourceCode> {
    const response = await api.put<SourceCode>(`/source_codes/${id}`, data);
    return response.data;
  },

  async deleteSourceCode(id: number): Promise<void> {
    await api.delete(`/source_codes/${id}`);
  },
};

// Settings API (Admin)
export const settingsAPI = {
  async getAllSettings(category?: string): Promise<SystemSetting[]> {
    const params: Record<string, unknown> = {};
    if (category) params.category = category;
    const response = await api.get<SystemSetting[]>('/admin/settings', { params });
    return response.data;
  },

  async getSetting(key: string): Promise<SystemSetting> {
    const response = await api.get<SystemSetting>(`/admin/settings/${key}`);
    return response.data;
  },

  async updateSetting(key: string, data: UpdateSettingRequest): Promise<SystemSetting> {
    const response = await api.put<SystemSetting>(`/admin/settings/${key}`, data);
    return response.data;
  },

  async getCategories(): Promise<string[]> {
    const response = await api.get<string[]>('/admin/settings/categories');
    return response.data;
  },

  async refreshCache(key?: string): Promise<{ message: string }> {
    const params: Record<string, unknown> = {};
    if (key) params.key = key;
    const response = await api.post<{ message: string }>('/admin/settings/refresh', null, { params });
    return response.data;
  },

  async initDefaults(): Promise<{ message: string }> {
    const response = await api.post<{ message: string }>('/admin/settings/init-defaults');
    return response.data;
  },
};

// Users API (Admin)
export const usersAPI = {
  async getUsers(
    page: number = 1,
    pageSize: number = 20,
    search?: string,
    isAdmin?: boolean
  ): Promise<UserListResponse> {
    const params: Record<string, unknown> = {
      page,
      page_size: pageSize,
    };
    if (search) params.search = search;
    if (isAdmin !== undefined) params.is_admin = isAdmin;
    const response = await api.get<UserListResponse>('/admin/users', { params });
    return response.data;
  },

  async getUser(userId: number): Promise<User> {
    const response = await api.get<User>(`/admin/users/${userId}`);
    return response.data;
  },

  async getUserStats(): Promise<UserStats> {
    const response = await api.get<UserStats>('/admin/users/stats');
    return response.data;
  },

  async updateAdminStatus(userId: number, data: UpdateAdminStatusRequest): Promise<User> {
    const response = await api.put<User>(`/admin/users/${userId}/admin-status`, data);
    return response.data;
  },

  async deleteUser(userId: number): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/admin/users/${userId}`);
    return response.data;
  },
};

// Tasks API (Admin)
export const tasksAPI = {
  async getTasks(
    page: number = 1,
    pageSize: number = 20,
    search?: string,
    status?: string,
    userId?: number
  ): Promise<TaskListResponse> {
    const params: Record<string, unknown> = {
      page,
      page_size: pageSize,
    };
    if (search) params.search = search;
    if (status) params.status = status;
    if (userId !== undefined) params.user_id = userId;
    const response = await api.get<TaskListResponse>('/admin/tasks', { params });
    return response.data;
  },

  async getTask(taskId: string): Promise<AnalysisTask> {
    const response = await api.get<AnalysisTask>(`/admin/tasks/${taskId}`);
    return response.data;
  },

  async getTaskStats(): Promise<TaskStats> {
    const response = await api.get<TaskStats>('/admin/tasks/stats');
    return response.data;
  },

  async deleteTask(taskId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/admin/tasks/${taskId}`);
    return response.data;
  },

  async cancelTask(taskId: string): Promise<CancelTaskResponse> {
    const response = await api.post<CancelTaskResponse>(`/admin/tasks/${taskId}/cancel`);
    return response.data;
  },

  async batchCancelTasks(taskIds: string[]): Promise<BatchCancelResponse> {
    const response = await api.post<BatchCancelResponse>('/admin/tasks/batch-cancel', { task_ids: taskIds });
    return response.data;
  },
};

// System Monitor API (Admin)
export const systemAPI = {
  async getSystemStatus(): Promise<SystemStatus> {
    const response = await api.get<SystemStatus>('/admin/system/status');
    return response.data;
  },
};

// Samples API (Admin)
export const samplesAPI = {
  async getSamples(
    page: number = 1,
    pageSize: number = 20,
    isActive?: boolean
  ): Promise<SampleListResponse> {
    const params: Record<string, unknown> = {
      page,
      page_size: pageSize,
    };
    if (isActive !== undefined) params.is_active = isActive;
    const response = await api.get<SampleListResponse>('/admin/samples', { params });
    return response.data;
  },

  async getSample(id: number): Promise<Sample> {
    const response = await api.get<Sample>(`/admin/samples/${id}`);
    return response.data;
  },

  async createSample(data: CreateSampleRequest): Promise<Sample> {
    const response = await api.post<Sample>('/admin/samples', data);
    return response.data;
  },

  async updateSample(id: number, data: UpdateSampleRequest): Promise<Sample> {
    const response = await api.put<Sample>(`/admin/samples/${id}`, data);
    return response.data;
  },

  async deleteSample(id: number): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/admin/samples/${id}`);
    return response.data;
  },

  async getSampleViews(
    sampleId: number,
    page: number = 1,
    pageSize: number = 50
  ): Promise<SampleViewListResponse> {
    const params = { page, page_size: pageSize };
    const response = await api.get<SampleViewListResponse>(
      `/admin/samples/${sampleId}/views`,
      { params }
    );
    return response.data;
  },
};

export default api;
