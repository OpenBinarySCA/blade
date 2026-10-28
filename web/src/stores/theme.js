import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  // 2-state theme: 'light' (default) | 'dark'
  const stored = localStorage.getItem('theme')
  const preference = ref(stored === 'dark' ? 'dark' : 'light')

  const actualTheme = computed(() => preference.value)
  const isDark = computed(() => preference.value === 'dark')
  const isLight = computed(() => preference.value === 'light')

  // Apply theme to <html data-theme>
  const applyTheme = () => {
    const root = document.documentElement
    root.classList.add('theme-transition')
    root.setAttribute('data-theme', preference.value)
    setTimeout(() => root.classList.remove('theme-transition'), 200)
  }

  const setTheme = (theme) => {
    preference.value = theme === 'dark' ? 'dark' : 'light'
    localStorage.setItem('theme', preference.value)
    applyTheme()
  }

  const toggleTheme = () => setTheme(isDark.value ? 'light' : 'dark')

  // Kept as an alias for any legacy caller (now a 2-state toggle)
  const cycleTheme = toggleTheme

  const init = () => applyTheme()

  return {
    preference,
    actualTheme,
    isDark,
    isLight,
    setTheme,
    toggleTheme,
    cycleTheme,
    applyTheme,
    init
  }
})
