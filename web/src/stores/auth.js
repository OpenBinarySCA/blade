/**
 * Authentication Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, getToken, setToken, removeToken } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref(getToken() || null)
  const user = ref(null)
  const loading = ref(false)

  // Getters
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin || false)
  const username = computed(() => user.value?.username || '')
  const userEmail = computed(() => user.value?.email || '')
  const userAvatar = computed(() => user.value?.profile_picture || '')

  // Actions
  function setAuthToken(newToken) {
    token.value = newToken
    setToken(newToken)
  }

  async function fetchCurrentUser() {
    if (!token.value) return null

    loading.value = true
    try {
      const userData = await authApi.getCurrentUser()
      user.value = userData
      return userData
    } catch (error) {
      console.error('Failed to fetch current user:', error)
      // Token might be invalid, clear it
      if (error.response?.status === 401) {
        logout()
      }
      return null
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      token.value = null
      user.value = null
      removeToken()
    }
  }

  // Initialize: try to fetch user if token exists
  async function initialize() {
    if (token.value) {
      await fetchCurrentUser()
    }
  }

  return {
    // State
    token,
    user,
    loading,
    // Getters
    isLoggedIn,
    isAdmin,
    username,
    userEmail,
    userAvatar,
    // Actions
    setToken: setAuthToken,
    fetchCurrentUser,
    logout,
    initialize,
  }
}, {
  persist: {
    key: 'blade_auth',
    paths: ['token'],
  },
})
