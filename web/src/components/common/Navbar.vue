<template>
  <nav class="rail">
    <!-- BLADE mark -->
    <div class="rail-logo" aria-hidden="true">
      <svg viewBox="0 0 28 28" width="24" height="24"><path d="M7 23 L18 5 L22 5 L11 23 Z" fill="var(--accent)" /></svg>
    </div>

    <button class="rail-btn" :class="{ active: isActive('upload') }" title="New analysis" aria-label="New analysis" @click="go('upload')">
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path stroke-linecap="round" stroke-linejoin="round" d="M12 5v14M5 12h14" /></svg>
    </button>
    <button class="rail-btn" :class="{ active: isActive('result') }" title="Result" aria-label="Result" @click="goResult">
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path stroke-linecap="round" stroke-linejoin="round" d="M3.5 8 12 3l8.5 5v8L12 21l-8.5-5V8Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M3.5 8 12 13l8.5-5M12 13v8" /></svg>
    </button>
    <button class="rail-btn" :class="{ active: isActive('history') }" title="History" aria-label="History" @click="go('history')">
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12a9 9 0 1 0 3-6.7L3 8m0-5v5h5" /><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 2" /></svg>
    </button>
    <button class="rail-btn" :class="{ active: isActive('docs') }" title="Docs" aria-label="Docs" @click="go('docs')">
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path stroke-linecap="round" stroke-linejoin="round" d="M4 5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M13 3v5h5M8 13h8M8 17h6" /></svg>
    </button>

    <div class="rail-spacer"></div>

    <!-- Theme toggle -->
    <button class="rail-toggle" title="Toggle theme" :aria-label="themeStore.isDark ? 'Switch to light theme' : 'Switch to dark theme'" @click="themeStore.toggleTheme()">
      <svg v-if="themeStore.isDark" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="4.5" /><path stroke-linecap="round" d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19" /></svg>
      <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z" /></svg>
    </button>

    <!-- Account -->
    <div class="rail-account">
      <button class="rail-avatar" :title="authStore.user ? authStore.user.email : 'Account'" aria-label="Account" @click="toggleAccount">
        {{ avatarText }}
      </button>
      <div v-if="accountOpen" class="account-pop" @click.stop>
        <div v-if="authStore.user" class="account-email">{{ authStore.user.email }}</div>
        <button v-if="authStore.user" class="account-item" @click="handleLogout">Sign out</button>
        <button v-else class="account-item" @click="go('login')">Sign in</button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed, ref, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useThemeStore } from '../../stores/theme'
import { useTaskStore } from '../../stores/task'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const taskStore = useTaskStore()

const accountOpen = ref(false)

const avatarText = computed(() => {
  const email = authStore.user?.email || ''
  return email ? email.substring(0, 2).toUpperCase() : 'AN'
})

function isActive(name) {
  return route.name === name
}

function go(name) {
  accountOpen.value = false
  if (route.name !== name) router.push({ name })
}

function goResult() {
  accountOpen.value = false
  if (taskStore.currentTaskId) {
    router.push({ name: 'result', params: { taskId: taskStore.currentTaskId } })
  } else {
    router.push({ name: 'history' })
  }
}

function toggleAccount() {
  accountOpen.value = !accountOpen.value
  if (accountOpen.value) {
    setTimeout(() => document.addEventListener('click', closeAccount, { once: true }), 0)
  }
}
function closeAccount() {
  accountOpen.value = false
}
onBeforeUnmount(() => document.removeEventListener('click', closeAccount))

async function handleLogout() {
  accountOpen.value = false
  await authStore.logout()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.rail {
  width: 58px;
  flex-shrink: 0;
  background: var(--surface-1);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 0;
  gap: 4px;
  z-index: 5;
}

.rail-logo {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.rail-btn {
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--r2);
  color: var(--text-3);
  transition: color .15s, background .15s;
}
.rail-btn.active {
  color: var(--accent);
  background: var(--accent-dim);
}

.rail-spacer {
  flex: 1;
}

.rail-toggle {
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--r2);
  color: var(--text-3);
  transition: color .15s, background .15s;
}
.rail-toggle:hover {
  color: var(--text-1);
  background: var(--surface-3);
}

.rail-account {
  position: relative;
}
.rail-avatar {
  width: 34px;
  height: 34px;
  border-radius: var(--r2);
  background: var(--surface-3);
  border: 1px solid var(--line);
  color: var(--text-2);
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.rail-avatar:hover {
  color: var(--text-1);
  border-color: var(--line-strong);
}

.account-pop {
  position: absolute;
  left: 44px;
  bottom: 0;
  min-width: 180px;
  background: var(--surface-1);
  border: 1px solid var(--line);
  border-radius: var(--r2);
  box-shadow: var(--shadow);
  padding: 6px;
  z-index: 20;
}
.account-email {
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-3);
  padding: 6px 9px 8px;
  border-bottom: 1px solid var(--line-soft);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.account-item {
  width: 100%;
  text-align: left;
  padding: 8px 9px;
  border-radius: var(--r1);
  font-size: var(--t-sm);
  color: var(--text-2);
}
.account-item:hover {
  background: var(--surface-2);
  color: var(--text-1);
}
</style>
