<template>
  <div class="upload-page">
    <h1 class="upload-h1">Analyze a binary</h1>
    <p class="upload-sub">Upload a binary, archive, or firmware image. BLADE extracts and identifies every embedded component.</p>

    <!-- Dropzone -->
    <div
      class="dropzone"
      :class="{ active: isDragging }"
      @drop.prevent="handleDrop"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @click="triggerFileInput"
    >
      <input
        ref="fileInput"
        type="file"
        class="hidden-input"
        @change="handleFileSelect"
        accept=".zip,.tar,.gz,.img,.bin,.elf,.so,.exe,.dll"
      />

      <template v-if="isUploading">
        <div class="dz-glyph">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2.2" class="dz-spinner"><path stroke-linecap="round" d="M12 3a9 9 0 1 0 9 9" /></svg>
        </div>
        <div class="dz-title">Uploading &amp; creating task…</div>
      </template>

      <template v-else-if="selectedFile">
        <div class="dz-glyph">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path stroke-linecap="round" stroke-linejoin="round" d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M13 3v6h6" /></svg>
        </div>
        <div class="dz-title mono">{{ selectedFile.name }}</div>
        <div class="dz-formats">{{ formatFileSize(selectedFile.size) }}</div>
      </template>

      <template v-else>
        <div class="dz-glyph">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path stroke-linecap="round" stroke-linejoin="round" d="M12 16V4m0 0L8 8m4-4 4 4" /><path stroke-linecap="round" stroke-linejoin="round" d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" /></svg>
        </div>
        <div class="dz-title">Drop your program here</div>
        <div class="dz-formats">or click to browse · ELF, PE, Mach-O, .zip, .tar.gz, .img, .bin</div>
      </template>
    </div>

    <!-- Error -->
    <div v-if="errorMessage" class="upload-error">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9" /><path stroke-linecap="round" d="M12 8v5M12 16h.01" /></svg>
      <span>{{ errorMessage }}</span>
    </div>

    <!-- Samples -->
    <div v-if="samples.length > 0" class="samples">
      <div class="samples-label">Sample analyses</div>
      <div class="samples-list">
        <button
          v-for="sample in samples"
          :key="sample.id"
          class="sample-row"
          @click="goToSample(sample.task_id)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" stroke-width="1.6" class="sample-icon"><path stroke-linecap="round" stroke-linejoin="round" d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M13 3v6h6" /></svg>
          <div class="sample-text">
            <div class="sample-name">{{ sample.file_name }}</div>
            <div v-if="sample.description" class="sample-desc">{{ sample.description }}</div>
          </div>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" stroke-width="1.8" class="sample-chev"><path stroke-linecap="round" stroke-linejoin="round" d="m9 6 6 6-6 6" /></svg>
        </button>
      </div>
    </div>

    <!-- Login Required Modal -->
    <div v-if="showLoginModal" class="modal-overlay" @click.self="showLoginModal = false">
      <div class="modal-content">
        <h3 class="modal-title">Free limit reached</h3>
        <p class="modal-message">
          You've used all {{ guestLimit }} free analyses. Sign in to continue analyzing your binaries without limits.
        </p>
        <div class="modal-actions">
          <button class="modal-btn outline" @click="showLoginModal = false">Cancel</button>
          <button class="modal-btn solid" @click="goToLogin">Sign in</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '../stores/task'
import bladeAPI from '../api/blade'

const router = useRouter()
const taskStore = useTaskStore()

const fileInput = ref(null)
const selectedFile = ref(null)
const isDragging = ref(false)
const isUploading = ref(false)
const errorMessage = ref('')
const showLoginModal = ref(false)
const guestLimit = ref(3)
const samples = ref([])

function triggerFileInput() {
  if (!isUploading.value) {
    fileInput.value.click()
  }
}

function handleFileSelect(event) {
  const file = event.target.files[0]
  if (file) {
    selectedFile.value = file
    errorMessage.value = ''
    setTimeout(() => {
      handleUpload()
    }, 500)
  }
}

async function handleDrop(event) {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file) {
    selectedFile.value = file
    errorMessage.value = ''
    setTimeout(() => {
      handleUpload()
    }, 500)
  }
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

async function handleUpload() {
  if (!selectedFile.value || isUploading.value) return

  isUploading.value = true
  errorMessage.value = ''

  try {
    const uploadResult = await bladeAPI.uploadFile(selectedFile.value)
    const taskResult = await bladeAPI.createTask(
      uploadResult.file_path,
      uploadResult.file_name,
      uploadResult.file_sha256
    )
    taskStore.setCurrentTask(taskResult.task_id)
    router.push({ name: 'result', params: { taskId: taskResult.task_id } })
  } catch (error) {
    console.error('Upload error:', error)
    if (error.response?.status === 429) {
      const detail = error.response?.data?.detail
      if (detail?.limit) {
        guestLimit.value = detail.limit
      }
      showLoginModal.value = true
      selectedFile.value = null
    } else {
      const detail = error.response?.data?.detail
      errorMessage.value = typeof detail === 'string' ? detail : detail?.message || error.message || 'Upload failed. Please try again.'
    }
    isUploading.value = false
  }
}

function goToLogin() {
  showLoginModal.value = false
  router.push({ name: 'login' })
}

async function loadSamples() {
  try {
    samples.value = await bladeAPI.getSamples()
  } catch (error) {
    console.error('Failed to load samples:', error)
  }
}

function goToSample(taskId) {
  router.push({ name: 'result', params: { taskId } })
}

onMounted(() => {
  loadSamples()
})
</script>

<style scoped>
.upload-page {
  padding: 40px 18px;
  width: 100%;
  max-width: 720px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.upload-h1 {
  font-size: var(--t-h1);
  font-weight: 600;
  color: var(--text-1);
  margin: 0 0 6px;
}
.upload-sub {
  color: var(--text-2);
  font-size: var(--t-sm);
  margin: 0 0 24px;
}

.hidden-input {
  display: none;
}

/* Dropzone */
.dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 42px 24px;
  border: 1.5px dashed var(--line-strong);
  border-radius: var(--r3);
  background: var(--surface-1);
  cursor: pointer;
  transition: border-color .15s, background .15s;
}
.dropzone:hover,
.dropzone.active {
  border-color: var(--accent);
  background: var(--accent-dim);
}
.dz-glyph {
  width: 54px;
  height: 54px;
  border-radius: var(--r3);
  background: var(--surface-3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-2);
  margin-bottom: 15px;
}
.dz-spinner {
  animation: spin .9s linear infinite;
}
.dz-title {
  font-size: var(--t-body);
  font-weight: 600;
  color: var(--text-1);
  margin-bottom: 4px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dz-title.mono {
  font-family: var(--mono-font);
  font-weight: 500;
}
.dz-formats {
  font-size: var(--t-meta);
  color: var(--text-3);
}

/* Error */
.upload-error {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  padding: 10px 13px;
  background: var(--warn-dim);
  border: 1px solid var(--line);
  border-radius: var(--r2);
  color: var(--crit);
  font-size: var(--t-meta);
}

/* Samples */
.samples {
  margin-top: 28px;
}
.samples-label {
  font-size: var(--t-meta);
  color: var(--text-3);
  margin-bottom: 11px;
}
.samples-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sample-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  text-align: left;
  padding: 12px 15px;
  background: var(--surface-1);
  border: 1px solid var(--line);
  border-radius: var(--r2);
  transition: border-color .15s, background .15s;
}
.sample-row:hover {
  border-color: var(--accent-line);
  background: var(--surface-2);
}
.sample-icon {
  flex-shrink: 0;
}
.sample-text {
  flex: 1;
  min-width: 0;
}
.sample-name {
  font-family: var(--mono-font);
  font-size: var(--t-sm);
  font-weight: 500;
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sample-desc {
  font-size: var(--t-meta);
  color: var(--text-3);
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sample-chev {
  flex-shrink: 0;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: var(--surface-1);
  border: 1px solid var(--line);
  border-radius: var(--r3);
  box-shadow: var(--shadow);
  padding: 22px;
  max-width: 380px;
  width: 90%;
  text-align: center;
}
.modal-title {
  font-size: var(--t-h1);
  font-weight: 600;
  color: var(--text-1);
  margin: 0 0 8px;
}
.modal-message {
  color: var(--text-2);
  font-size: var(--t-sm);
  line-height: 1.55;
  margin: 0 0 18px;
}
.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}
.modal-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: var(--r2);
  font-size: var(--t-sm);
  font-weight: 500;
  transition: all .15s;
}
.modal-btn.outline {
  border: 1px solid var(--line-strong);
  color: var(--text-2);
}
.modal-btn.outline:hover {
  color: var(--text-1);
  border-color: var(--text-3);
}
.modal-btn.solid {
  background: var(--accent);
  color: var(--accent-ink);
  font-weight: 600;
}
.modal-btn.solid:hover {
  background: var(--accent-bright);
}
</style>
