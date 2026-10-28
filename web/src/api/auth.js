/**
 * Authentication API
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// Storage keys
const TOKEN_KEY = 'blade_token'

/**
 * Get stored auth token
 */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

/**
 * Set auth token
 */
export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

/**
 * Remove auth token
 */
export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/**
 * Auth API functions
 */
export const authApi = {
  /**
   * Login with Google OAuth
   * @param {string} idToken - Google ID token
   * @returns {Promise<{access_token: string, token_type: string}>}
   */
  async googleLogin(idToken) {
    const response = await api.post('/auth/google', {
      id_token: idToken,
    })
    if (response.data?.access_token) {
      setToken(response.data.access_token)
    }
    return response.data
  },

  /**
   * Get current user info
   * @returns {Promise<Object>}
   */
  async getCurrentUser() {
    const token = getToken()
    if (!token) {
      throw new Error('No auth token')
    }
    const response = await api.get('/auth/me', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
    return response.data
  },

  /**
   * Logout
   */
  async logout() {
    try {
      const token = getToken()
      if (token) {
        await api.post('/auth/logout', null, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })
      }
    } catch (error) {
      console.error('Logout API error:', error)
    } finally {
      removeToken()
    }
  },
}

export default authApi
