<template>
  <!-- Contextual header actions (rendered into the app header) -->
  <teleport to="#app-header-actions">
    <button
      v-if="showReanalyzeButton && (isDone || isFailed)"
      class="hdr-btn outline"
      :disabled="isReanalyzing"
      @click="handleReanalyze"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h5M20 20v-5h-5" /><path stroke-linecap="round" stroke-linejoin="round" d="M4.6 15a8 8 0 0 0 14-3M19.4 9a8 8 0 0 0-14-3" /></svg>
      {{ isReanalyzing ? 'Re-analyzing…' : 'Re-analyze' }}
    </button>
    <button v-if="isDone" class="hdr-btn solid" @click="handleReportClick">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14" /></svg>
      {{ exportLabel }}
    </button>
  </teleport>

  <div class="result-page">
    <div v-if="loading && !taskData" class="state-msg">Loading analysis…</div>
    <div v-else-if="error" class="state-msg state-error">{{ error }}</div>
    <div v-else-if="isFailed" class="state-msg state-error">Analysis failed: {{ taskData?.error_message || 'unknown error' }}</div>

    <template v-else>
      <!-- View toggle -->
      <div class="toggle-row">
        <div class="segmented">
          <button class="seg" :class="{ active: view === 'workbench' }" @click="view = 'workbench'">Workbench</button>
          <button class="seg" :class="{ active: view === 'report' }" @click="view = 'report'">Report</button>
        </div>
        <div class="toggle-spacer"></div>
        <span v-if="isDone" class="toggle-summary">
          {{ totals.total }} components<template v-if="totals.hasReview"> · <span class="warn">{{ totals.review }} to verify</span></template>
        </span>
      </div>

      <!-- Workbench -->
      <div v-if="view === 'workbench'" class="workbench">
        <!-- Col 1: INPUT FILE -->
        <section class="col-input">
          <div class="col-head">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" stroke-width="1.7" class="head-icon"><path stroke-linecap="round" stroke-linejoin="round" d="M14 3v5h5M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" /></svg>
            <span class="eyebrow">INPUT FILE</span>
          </div>
          <div class="col-input-body">
            <div class="input-name">{{ fileName }}</div>
            <div v-for="f in artifactFacts" :key="f.label" class="fact">
              <div class="fact-label">{{ f.label }}</div>
              <div class="fact-value" :title="f.full">{{ f.value }}</div>
            </div>
          </div>
          <div class="col-input-footer">
            <div v-if="isProcessing" class="proc-foot">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2.4" class="spinner"><path stroke-linecap="round" d="M12 3a9 9 0 1 0 9 9" /></svg>
              <span>{{ currentPhaseLabel || 'Analyzing…' }}</span>
            </div>
            <template v-else-if="isDone">
              <div class="verdict">
                <span class="verdict-num">{{ totals.total }}</span>
                <span class="verdict-label">components</span>
              </div>
              <div class="verdict-sub">
                {{ totals.high }} high<template v-if="totals.hasReview"> · <span class="warn">{{ totals.review }} to verify</span></template>
              </div>
            </template>
          </div>
        </section>

        <!-- Col 2-4 -->
        <TPLList :result-data="resultData" :processing="isProcessing" />
      </div>

      <!-- Report -->
      <ReportView v-else :result-data="resultData" />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTaskStore } from '../stores/task'
import bladeAPI from '../api/blade'
import TPLList from '../components/result/TPLList.vue'
import ReportView from '../components/result/ReportView.vue'
import { useComposition, shortType, basename } from '../composables/useComposition'
import { useAppHeader } from '../composables/useAppHeader'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()
const appHeader = useAppHeader()

const taskId = ref(route.params.taskId || taskStore.currentTaskId)
const taskData = ref(null)
const resultData = ref(null)
const loading = ref(true)
const error = ref(null)
const elapsedSeconds = ref(0)
const reportStatus = ref('none') // 'none' | 'generating' | 'ready'
const reportMinioPath = ref(null)
const isReanalyzing = ref(false)
const showReanalyzeButton = ref(true)
const lastCompletedChangeTime = ref(Date.now())
const ESTIMATED_TIME_PER_FILE = 100
const view = ref('workbench') // 'workbench' | 'report'

const phaseLabels = {
  'parsing': 'Parsing binary…',
  'feature_matching': 'Feature matching…',
  'tpl_analysis': 'Analyzing TPLs…',
  'version_analysis': 'Identifying versions…',
  'generating_explanation': 'Generating results…'
}
let pollInterval = null
let timerInterval = null

// ---------- derived ----------
const isProcessing = computed(() => {
  const status = taskData.value?.status
  return status && !['success', 'failed'].includes(status)
})
const isDone = computed(() => taskData.value?.status === 'success' && !!resultData.value)
const isFailed = computed(() => taskData.value?.status === 'failed')

const { totals } = useComposition(resultData)

const fileName = computed(() =>
  resultData.value?.input_file?.file_name ||
  basename(taskData.value?.file_minio_path) ||
  'Result'
)

const taskDuration = computed(() => {
  const s = taskData.value?.start_at
  const e = taskData.value?.end_at
  if (!s || !e) return ''
  try {
    const sec = Math.max(0, Math.floor((new Date(e).getTime() - new Date(s).getTime()) / 1000))
    return formatDuration(sec)
  } catch (err) {
    return ''
  }
})

function shortHash(h) {
  if (!h) return '—'
  return h.length > 12 ? `${h.slice(0, 6)}…${h.slice(-4)}` : h
}

const artifactFacts = computed(() => {
  const inf = resultData.value?.input_file
  if (!inf) return []
  const sha = resultData.value?.detection_results?.[0]?.analysis_data?.target_binary?.hash_sha256
  return [
    { label: 'Type', value: shortType(inf.readable_type) || '—', full: inf.readable_type || '' },
    { label: 'Size', value: inf.file_size || '—', full: inf.file_size || '' },
    { label: 'MD5', value: shortHash(inf.file_md5), full: inf.file_md5 || '' },
    { label: 'SHA-256', value: sha ? `${sha.slice(0, 24)}…` : '—', full: sha || '' },
    { label: 'Files extracted', value: String(resultData.value?.extraction?.extracted_file_num ?? '—'), full: '' },
    { label: 'Duration', value: taskDuration.value || '—', full: '' }
  ]
})

const exportLabel = computed(() =>
  reportStatus.value === 'generating' ? 'Generating…' : reportStatus.value === 'ready' ? 'Download' : 'Export'
)

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return remainingSeconds ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`
}

const currentPhaseLabel = computed(() => {
  const phase = taskData.value?.current_analyzing_phase
  return phaseLabels[phase] || ''
})

// Keep the breadcrumb title in sync with the artifact name
watch(fileName, (n) => {
  if (n && n !== 'Result') appHeader.title = n
}, { immediate: true })

watch(() => taskData.value?.analysis_completed_files, (newVal, oldVal) => {
  if (newVal !== oldVal && newVal !== undefined) {
    lastCompletedChangeTime.value = Date.now()
  }
}, { immediate: true })

// ---------- actions ----------
async function handleReanalyze() {
  if (isReanalyzing.value || !taskData.value) return
  const fileMinioPath = taskData.value.file_minio_path
  const name = resultData.value?.input_file?.file_name || basename(fileMinioPath) || 'unknown'
  if (!fileMinioPath) {
    console.error('Cannot reanalyze: missing file_minio_path')
    return
  }
  try {
    isReanalyzing.value = true
    const newTask = await bladeAPI.createTask(fileMinioPath, name, '', true)
    taskStore.setCurrentTask(newTask.task_id)
    router.push({ name: 'result', params: { taskId: newTask.task_id } })
    taskId.value = newTask.task_id
    taskData.value = null
    resultData.value = null
    reportStatus.value = 'none'
    reportMinioPath.value = null
    elapsedSeconds.value = 0
    view.value = 'workbench'
    await fetchTaskData()
    if (isProcessing.value) {
      startPolling()
      startTimer()
    }
  } catch (err) {
    console.error('Reanalyze error:', err)
  } finally {
    isReanalyzing.value = false
  }
}

async function handleReportClick() {
  if (reportStatus.value === 'ready' && reportMinioPath.value) {
    await downloadReport()
  } else if (reportStatus.value === 'none') {
    await generateReport()
  }
}

async function generateReport() {
  if (!taskId.value) return
  try {
    reportStatus.value = 'generating'
    const response = await bladeAPI.generateReport(taskId.value)
    if (response.success && response.report_minio_path) {
      reportMinioPath.value = response.report_minio_path
      reportStatus.value = 'ready'
    } else {
      console.error('Report generation failed:', response.message)
      reportStatus.value = 'none'
    }
  } catch (err) {
    console.error('Report generation error:', err)
    reportStatus.value = 'none'
  }
}

async function downloadReport() {
  if (!reportMinioPath.value) return
  try {
    const blob = await bladeAPI.downloadFile(reportMinioPath.value)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'blade_report.zip'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (err) {
    console.error('Report download error:', err)
  }
}

// ---------- lifecycle / data ----------
onMounted(async () => {
  if (!taskId.value) {
    error.value = 'No task ID provided'
    loading.value = false
    return
  }
  try {
    const settings = await bladeAPI.getPublicSettings()
    if (settings.enable_reanalyze_button !== undefined) {
      showReanalyzeButton.value = settings.enable_reanalyze_button
    }
  } catch (err) {
    console.error('Failed to load settings:', err)
  }
  taskStore.setCurrentTask(taskId.value)
  await fetchTaskData()
  if (isProcessing.value) {
    startPolling()
    startTimer()
  }
})

onUnmounted(() => {
  stopPolling()
  stopTimer()
})

async function fetchTaskData() {
  try {
    loading.value = true
    error.value = null
    const data = await bladeAPI.getTaskStatus(taskId.value)
    taskData.value = data
    if (data.report_minio_path) {
      reportMinioPath.value = data.report_minio_path
      reportStatus.value = 'ready'
    }
    if (data.status === 'success' && data.result_minio_path) {
      try {
        const resultBlob = await bladeAPI.downloadFile(data.result_minio_path)
        const resultText = await resultBlob.text()
        resultData.value = JSON.parse(resultText)
      } catch (resultError) {
        console.error('Failed to load result data:', resultError)
      }
    }
    if (!isProcessing.value) {
      stopPolling()
      stopTimer()
    }
  } catch (err) {
    console.error('Failed to fetch task data:', err)
    error.value = err.response?.data?.detail || err.message || 'Unknown error'
  } finally {
    loading.value = false
  }
}

function startPolling() {
  pollInterval = setInterval(fetchTaskData, 1000)
}
function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}
function startTimer() {
  if (taskData.value?.start_at) {
    try {
      const startTime = new Date(taskData.value.start_at).getTime()
      elapsedSeconds.value = Math.floor((Date.now() - startTime) / 1000)
    } catch (e) {
      elapsedSeconds.value = 0
    }
  }
  timerInterval = setInterval(() => { elapsedSeconds.value++ }, 1000)
}
function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}
</script>

<style scoped>
.result-page {
  padding: 16px 18px 22px;
  width: 100%;
  max-width: 1360px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.state-msg {
  padding: 60px 18px;
  text-align: center;
  color: var(--text-3);
  font-size: var(--t-sm);
}
.state-error {
  color: var(--crit);
}

/* Header action buttons (teleported) */
.hdr-btn {
  height: 33px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border-radius: var(--r2);
  font-size: var(--t-sm);
  font-weight: 500;
  transition: all .15s;
}
.hdr-btn.outline {
  padding: 0 12px;
  border: 1px solid var(--line-strong);
  color: var(--text-2);
}
.hdr-btn.outline:hover:not(:disabled) {
  color: var(--text-1);
  border-color: var(--text-3);
}
.hdr-btn.outline:disabled {
  opacity: .6;
  cursor: default;
}
.hdr-btn.solid {
  padding: 0 13px;
  background: var(--accent);
  color: var(--accent-ink);
  font-weight: 600;
}
.hdr-btn.solid:hover {
  background: var(--accent-bright);
}

/* Toggle row */
.toggle-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.segmented {
  display: flex;
  gap: 2px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--r2);
  padding: 2px;
}
.seg {
  height: 28px;
  padding: 0 13px;
  border-radius: var(--r1);
  font-size: var(--t-meta);
  font-weight: 500;
  color: var(--text-3);
  transition: all .12s;
}
.seg.active {
  background: var(--surface-1);
  color: var(--text-1);
  box-shadow: var(--shadow);
}
.toggle-spacer {
  flex: 1;
}
.toggle-summary {
  font-size: var(--t-meta);
  color: var(--text-3);
}
.toggle-summary .warn {
  color: var(--warn);
  font-weight: 600;
}

/* Workbench */
.workbench {
  display: flex;
  gap: 12px;
  align-items: stretch;
  flex: 1;
  min-height: 0;
}

/* Col 1 input file */
.col-input {
  width: 280px;
  flex-shrink: 0;
  background: var(--surface-1);
  border: 1px solid var(--line);
  border-radius: var(--r3);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.col-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 15px;
  border-bottom: 1px solid var(--line);
  background: var(--surface-2);
}
.head-icon {
  flex-shrink: 0;
}
.eyebrow {
  font-size: var(--t-micro);
  font-weight: 700;
  letter-spacing: .06em;
  color: var(--text-3);
}
.col-input-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 15px;
}
.input-name {
  font-family: var(--mono-font);
  font-size: var(--t-sm);
  font-weight: 600;
  color: var(--text-1);
  word-break: break-all;
  margin-bottom: 15px;
}
.fact {
  margin-bottom: 11px;
}
.fact-label {
  font-size: var(--t-micro);
  color: var(--text-3);
  margin-bottom: 2px;
}
.fact-value {
  font-family: var(--mono-font);
  font-size: var(--t-meta);
  color: var(--text-1);
  word-break: break-all;
}
.col-input-footer {
  border-top: 1px solid var(--line);
  padding: 12px 15px;
  background: var(--surface-2);
}
.proc-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: var(--t-meta);
  color: var(--accent);
  font-weight: 500;
}
.spinner {
  animation: spin .9s linear infinite;
}
.verdict {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.verdict-num {
  font-family: var(--mono-font);
  font-size: 24px;
  font-weight: 600;
  color: var(--text-1);
}
.verdict-label {
  font-size: var(--t-meta);
  color: var(--text-2);
}
.verdict-sub {
  font-size: var(--t-micro);
  color: var(--text-3);
  margin-top: 3px;
}
.verdict-sub .warn,
.col-input-footer .warn {
  color: var(--warn);
  font-weight: 600;
}
</style>
