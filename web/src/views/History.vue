<template>
  <div class="history-page">
    <div class="history-head">
      <h1 class="history-h1">Analysis history</h1>
      <button class="new-btn" @click="goToUpload">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 5v14M5 12h14" /></svg>
        New analysis
      </button>
    </div>

    <div class="filter-box">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" stroke-width="1.8" class="filter-icon"><circle cx="11" cy="11" r="7" /><path stroke-linecap="round" d="m20 20-3.5-3.5" /></svg>
      <input v-model="filter" class="filter-input" placeholder="Filter by filename…" />
    </div>

    <div v-if="loading" class="state-msg">Loading history…</div>
    <div v-else-if="tasks.length === 0" class="state-msg">No analysis records yet</div>

    <div v-else class="table-card">
      <div class="thead">
        <span>Binary</span><span>Status</span><span>Components</span><span>Type</span><span>Started</span><span class="right">Duration</span>
      </div>
      <button
        v-for="task in filteredTasks"
        :key="task.task_id"
        class="trow"
        @click="goToResult(task.task_id)"
      >
        <span class="cell-binary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" stroke-width="1.6" class="binary-icon"><path stroke-linecap="round" stroke-linejoin="round" d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M13 3v6h6" /></svg>
          <span class="binary-name">{{ getFileName(task) }}</span>
        </span>
        <span class="cell-status" :style="{ color: statusMeta(task.status).color }">
          <span class="status-dot" :class="{ pulse: statusMeta(task.status).pulse }" :style="{ background: statusMeta(task.status).color }"></span>
          {{ statusMeta(task.status).label }}
        </span>
        <span class="cell-components">{{ componentCount(task) }}</span>
        <span class="cell-type">{{ fileType(task) }}</span>
        <span class="cell-started">{{ formatStarted(task.start_at) }}</span>
        <span class="cell-duration">{{ formatDuration(task) }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import bladeAPI from '../api/blade'

const router = useRouter()
const tasks = ref([])
const loading = ref(true)
const filter = ref('')

onMounted(async () => {
  try {
    const data = await bladeAPI.getTaskHistory()
    tasks.value = data.tasks || []
  } catch (error) {
    console.error('Failed to load task history:', error)
  } finally {
    loading.value = false
  }
})

const filteredTasks = computed(() => {
  const q = filter.value.trim().toLowerCase()
  if (!q) return tasks.value
  return tasks.value.filter((t) => getFileName(t).toLowerCase().includes(q))
})

function getFileName(task) {
  if (task.file_name) return task.file_name
  const p = task.file_minio_path
  if (!p) return 'Unknown'
  const parts = p.split('/')
  return parts[parts.length - 1] || 'Unknown'
}

const IN_PROGRESS = ['analyzing', 'file_downloading', 'unpacking', 'unpacking_result_uploading', 'result_uploading', 'running']

function statusMeta(status) {
  if (status === 'success') return { label: 'Completed', color: 'var(--text-2)', pulse: false }
  if (status === 'failed') return { label: 'Failed', color: 'var(--crit)', pulse: false }
  if (status === 'cancelled' || status === 'cancelling') return { label: 'Cancelled', color: 'var(--crit)', pulse: false }
  if (status === 'pending') return { label: 'Queued', color: 'var(--text-3)', pulse: false }
  if (IN_PROGRESS.includes(status)) return { label: 'Analyzing', color: 'var(--accent)', pulse: true }
  return { label: status || 'Unknown', color: 'var(--text-3)', pulse: false }
}

function componentCount(task) {
  const n = task.detected_library_count ?? task.library_count ?? task.component_count
  return (n === 0 || n) ? n : '—'
}

function fileType(task) {
  const name = getFileName(task).toLowerCase()
  if (name.endsWith('.tar.gz') || name.endsWith('.tgz') || name.endsWith('.gz')) return 'GZIP'
  if (name.endsWith('.zip')) return 'ZIP'
  if (name.endsWith('.tar')) return 'TAR'
  if (name.endsWith('.img')) return 'IMG'
  if (name.endsWith('.bin')) return 'BIN'
  if (name.endsWith('.exe') || name.endsWith('.dll')) return 'PE'
  if (name.endsWith('.so') || name.endsWith('.elf') || name.includes('.so.')) return 'ELF'
  const ext = name.includes('.') ? name.split('.').pop() : ''
  return ext ? ext.toUpperCase().slice(0, 5) : '—'
}

function formatStarted(ts) {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false
    })
  } catch (e) {
    return '—'
  }
}

function formatDuration(task) {
  const s = task.start_at
  const e = task.end_at
  if (!s || !e) return '—'
  try {
    const sec = Math.max(0, Math.floor((new Date(e).getTime() - new Date(s).getTime()) / 1000))
    if (sec < 60) return `${sec}s`
    const m = Math.floor(sec / 60)
    const r = sec % 60
    return r ? `${m}m ${r}s` : `${m}m`
  } catch (err) {
    return '—'
  }
}

function goToResult(taskId) {
  router.push({ name: 'result', params: { taskId } })
}
function goToUpload() {
  router.push({ name: 'upload' })
}
</script>

<style scoped>
.history-page {
  padding: 24px 18px 40px;
  width: 100%;
  max-width: 1020px;
  flex: 1;
  min-height: 0;
}

.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}
.history-h1 {
  font-size: var(--t-h1);
  font-weight: 600;
  color: var(--text-1);
  margin: 0;
}
.new-btn {
  height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 13px;
  background: var(--accent);
  color: var(--accent-ink);
  border-radius: var(--r2);
  font-size: var(--t-sm);
  font-weight: 600;
  transition: background .15s;
}
.new-btn:hover {
  background: var(--accent-bright);
}

.filter-box {
  position: relative;
  max-width: 320px;
  margin-bottom: 14px;
}
.filter-icon {
  position: absolute;
  left: 11px;
  top: 50%;
  transform: translateY(-50%);
}
.filter-input {
  width: 100%;
  height: 34px;
  background: var(--surface-1);
  border: 1px solid var(--line);
  border-radius: var(--r2);
  padding: 0 11px 0 32px;
  color: var(--text-1);
  font-size: var(--t-sm);
}
.filter-input:focus {
  border-color: var(--accent-line);
}

.state-msg {
  padding: 48px 0;
  text-align: center;
  color: var(--text-3);
  font-size: var(--t-sm);
}

.table-card {
  border: 1px solid var(--line);
  border-radius: var(--r3);
  overflow: hidden;
  background: var(--surface-1);
}
.thead {
  display: grid;
  grid-template-columns: 1fr 120px 96px 70px 124px 84px;
  gap: 12px;
  padding: 10px 16px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--line);
  font-size: var(--t-micro);
  color: var(--text-3);
}
.thead .right {
  text-align: right;
}
.trow {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 120px 96px 70px 124px 84px;
  gap: 12px;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line-soft);
  text-align: left;
  transition: background .12s;
}
.trow:hover {
  background: var(--surface-2);
}
.cell-binary {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}
.binary-icon {
  flex-shrink: 0;
}
.binary-name {
  font-family: var(--mono-font);
  font-size: var(--t-sm);
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cell-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--t-meta);
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.pulse {
  animation: pulse 1.2s ease-in-out infinite;
}
.cell-components {
  font-family: var(--mono-font);
  font-size: var(--t-sm);
  color: var(--text-2);
}
.cell-type {
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-3);
}
.cell-started {
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-3);
}
.cell-duration {
  text-align: right;
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-3);
}
</style>
