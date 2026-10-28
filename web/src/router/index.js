import { createRouter, createWebHistory } from 'vue-router'
import Upload from '../views/Upload.vue'
import Result from '../views/Result.vue'
import Login from '../views/Login.vue'
import History from '../views/History.vue'
import Docs from '../views/Docs.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: Login,
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      name: 'upload',
      component: Upload,
      meta: { requiresAuth: false }  // Allow guests with 3 free analyses
    },
    {
      path: '/result/:taskId?',
      name: 'result',
      component: Result,
      meta: { requiresAuth: false }  // Allow guests to view their results
    },
    {
      path: '/history',
      name: 'history',
      component: History,
      meta: { requiresAuth: true }   // Only logged-in users can view history
    },
    {
      path: '/docs',
      name: 'docs',
      component: Docs,
      meta: { requiresAuth: false }  // Public page
    }
  ]
})

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // Initialize auth store if needed
  if (authStore.token && !authStore.user) {
    await authStore.fetchCurrentUser()
  }

  // Check if route requires authentication
  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    next({ name: 'login', query: { redirect: to.fullPath } })
    return
  }

  // Check if route requires admin
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next({ name: 'upload' })
    return
  }

  // If logged in and trying to access login page, redirect to home
  if (to.name === 'login' && authStore.isLoggedIn) {
    next({ name: 'upload' })
    return
  }

  next()
})

export default router
