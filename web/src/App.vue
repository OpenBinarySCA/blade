<template>
  <!-- Login is full-bleed: no rail / header chrome -->
  <router-view v-if="isLogin" />

  <div v-else class="app-shell">
    <Navbar />
    <div class="main-column">
      <header class="app-header">
        <span class="crumb">{{ header.crumb }}</span>
        <span class="crumb-sep">/</span>
        <span class="header-title">{{ header.title }}</span>
        <div class="header-spacer"></div>
        <div id="app-header-actions" class="header-actions"></div>
      </header>
      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Navbar from './components/common/Navbar.vue'
import bladeAPI from './api/blade'
import { useThemeStore } from './stores/theme'
import { useAppHeader } from './composables/useAppHeader'

const route = useRoute()
const themeStore = useThemeStore()
const header = useAppHeader()

const isLogin = computed(() => route.name === 'login')

const DEFAULT_HEADER = {
  upload: { crumb: 'Workspace', title: 'New analysis' },
  result: { crumb: 'Analyses', title: 'Result' },
  history: { crumb: 'Workspace', title: 'History' },
  docs: { crumb: 'Workspace', title: 'Docs' }
}

// Set a sensible default breadcrumb on every route change. Views with a
// dynamic title (Result) overwrite header.title afterwards.
watch(
  () => route.name,
  (name) => {
    const d = DEFAULT_HEADER[name]
    if (d) {
      header.crumb = d.crumb
      header.title = d.title
    }
  },
  { immediate: true }
)

onMounted(async () => {
  themeStore.init()
  try {
    await bladeAPI.getVersion()
  } catch (error) {
    console.error('Failed to fetch version info:', error)
  }
})
</script>

<style scoped>
.app-shell {
  height: 100vh;
  display: flex;
  background: var(--bg);
  color: var(--text-1);
  overflow: hidden;
}

.main-column {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  position: relative;
}

.app-header {
  height: 52px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  background: var(--surface-1);
  box-shadow: 0 1px 2px rgba(16, 21, 33, .05);
  position: relative;
  z-index: 3;
}

.crumb {
  font-size: var(--t-meta);
  color: var(--text-3);
}
.crumb-sep {
  color: var(--text-3);
  opacity: .5;
}
.header-title {
  font-weight: 600;
  font-size: var(--t-body);
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 440px;
}
.header-spacer {
  flex: 1;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.main-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* Faint 48px grid overlay — fixed on the column (not the scroll container) */
.main-column::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 48px 48px;
  pointer-events: none;
  z-index: 0;
}
</style>
