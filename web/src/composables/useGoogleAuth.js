/**
 * Google OAuth Composable
 * 处理 Google 登录流程
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'

// Google Client ID from environment
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

export function useGoogleAuth() {
  const router = useRouter()
  const authStore = useAuthStore()
  const loading = ref(false)
  const isGoogleReady = ref(false)

  /**
   * Handle Google OAuth callback
   * @param {Object} response - Google callback response with credential
   */
  async function handleGoogleCallback(response) {
    loading.value = true
    try {
      console.log('[useGoogleAuth] Google callback received')
      const idToken = response.credential

      // Send token to backend
      const authResponse = await authApi.googleLogin(idToken)

      if (authResponse?.access_token) {
        // Store token and user info
        authStore.setToken(authResponse.access_token)
        await authStore.fetchCurrentUser()

        console.log('[useGoogleAuth] Google login successful')
        message.success('登录成功！')
        await router.push({ name: 'upload' })
      } else {
        throw new Error('No access token received from server')
      }
    } catch (error) {
      console.error('[useGoogleAuth] Google login failed:', error)
      message.error(error?.message || 'Google 登录失败，请重试')
    } finally {
      loading.value = false
    }
  }

  /**
   * Initialize Google Sign-In SDK
   */
  function initializeGoogleSignIn() {
    if (!GOOGLE_CLIENT_ID) {
      console.error('[useGoogleAuth] Google Client ID not configured')
      return
    }

    if (!window.google?.accounts?.id) {
      console.warn('[useGoogleAuth] Google Identity Services not loaded yet')
      setTimeout(initializeGoogleSignIn, 100) // Retry after 100ms
      return
    }

    try {
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleCallback,
        auto_select: false,
        cancel_on_tap_outside: true,
      })

      isGoogleReady.value = true
      console.log('[useGoogleAuth] Google Sign-In initialized')
    } catch (error) {
      console.error('[useGoogleAuth] Failed to initialize Google Sign-In:', error)
    }
  }

  /**
   * Render Google Sign-In button
   * @param {string} elementId - DOM element ID for the button
   * @param {Object} options - Button configuration options
   */
  function renderGoogleButton(elementId, options = {}) {
    if (!isGoogleReady.value) {
      console.warn('[useGoogleAuth] Google Sign-In not ready yet')
      // Retry after a short delay
      setTimeout(() => renderGoogleButton(elementId, options), 200)
      return
    }

    const element = document.getElementById(elementId)
    if (!element) {
      console.error(`[useGoogleAuth] Element with id '${elementId}' not found`)
      return
    }

    const defaultOptions = {
      type: 'standard',
      theme: 'outline',
      size: 'large',
      text: 'continue_with',
      shape: 'rectangular',
      logo_alignment: 'left',
      width: 320,
      ...options,
    }

    try {
      window.google.accounts.id.renderButton(element, defaultOptions)
      console.log('[useGoogleAuth] Google button rendered')
    } catch (error) {
      console.error('[useGoogleAuth] Failed to render Google button:', error)
    }
  }

  /**
   * Trigger Google One Tap prompt
   */
  function triggerGoogleSignIn() {
    if (!isGoogleReady.value) {
      console.warn('[useGoogleAuth] Google Sign-In not ready yet')
      message.warning('Google 登录正在加载，请稍后重试')
      return
    }

    try {
      window.google.accounts.id.prompt((notification) => {
        if (notification.isNotDisplayed() || notification.isDismissedMoment()) {
          console.log('[useGoogleAuth] One Tap not displayed or dismissed')
        }
      })
      console.log('[useGoogleAuth] Google Sign-In triggered')
    } catch (error) {
      console.error('[useGoogleAuth] Failed to trigger Google Sign-In:', error)
      message.error('无法打开 Google 登录')
    }
  }

  onMounted(() => {
    initializeGoogleSignIn()
  })

  return {
    loading,
    isGoogleReady,
    renderGoogleButton,
    triggerGoogleSignIn,
    initializeGoogleSignIn,
  }
}
