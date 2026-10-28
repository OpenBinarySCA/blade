import axios from 'axios'

const API_BASE_URL = '/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000
})

// Token interceptor - automatically attach JWT token to requests
api.interceptors.request.use(config => {
  const token = localStorage.getItem('blade_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const bladeAPI = {
  // Get version info
  async getVersion() {
    const response = await api.get('/version')
    return response.data
  },

  // Upload file and create task
  async uploadFile(file) {
    const formData = new FormData()
    formData.append('file', file)

    const response = await api.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return response.data
  },

  // Create detection task
  async createTask(fileMinioPath, fileName, fileSha256, forceReanalyze = false) {
    const response = await api.post('/tpl_detection_task', {
      file_minio_path: fileMinioPath,
      file_name: fileName,
      file_sha256: fileSha256,
      force_reanalyze: forceReanalyze
    })
    return response.data
  },

  // Get guest usage status
  async getGuestStatus() {
    const response = await api.get('/guest_status')
    return response.data
  },

  // Get task status
  async getTaskStatus(taskId) {
    const response = await api.get('/tpl_detection_task', {
      params: { task_id: taskId }
    })
    return response.data
  },

  // Get task history
  async getTaskHistory() {
    const response = await api.get('/tpl_detection_tasks')
    return response.data
  },

  // Download file
  async downloadFile(minioPath) {
    const response = await api.get('/download', {
      params: { file_path: minioPath },
      responseType: 'blob'
    })
    return response.data
  },

  // Generate report for a task
  async generateReport(taskId) {
    const response = await api.post('/generate_report', {
      task_id: taskId
    })
    return response.data
  },

  // Get active samples for display
  async getSamples() {
    const response = await api.get('/samples')
    return response.data
  },

  // Get public settings
  async getPublicSettings() {
    const response = await api.get('/settings/public')
    return response.data
  }
}

export default bladeAPI
