import { defineStore } from 'pinia'
import { api } from 'boot/axios'
import { getActivityTracker } from 'src/composables/useActivityTracker'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    permissions: {},   // section → { view, create, edit, delete }
    accessToken:  localStorage.getItem('access_token')  || null,
    refreshToken: localStorage.getItem('refresh_token') || null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    isAdmin:         (state) => state.user?.role === 'admin',
    isOperator:      (state) => state.user?.is_restricted_operator === true
                                || state.user?.role === 'operator',
    fullName:        (state) => state.user?.full_name || state.user?.username || '',

    // Section-level helpers
    can: (state) => (section, action) => {
      if (state.user?.role === 'admin') return true
      return state.permissions[section]?.[action] ?? false
    },
  },

  actions: {
    async login(username, password) {
      const res = await api.post('/auth/login/', { username, password })
      this.accessToken  = res.data.access
      this.refreshToken = res.data.refresh
      this.user = {
        id:        res.data.user_id,
        role:      res.data.role,
        full_name: res.data.full_name,
      }
      localStorage.setItem('access_token',  res.data.access)
      localStorage.setItem('refresh_token', res.data.refresh)
      await this.fetchMe()
      try {
        const tracker = getActivityTracker()
        tracker.start()
        tracker.track('login', { metadata: { username } })
      } catch { /* tracker is best-effort */ }
      return res.data
    },

    async fetchMe() {
      try {
        const res = await api.get('/auth/me/')
        this.user        = res.data
        this.permissions = res.data.permissions || {}
      } catch {
        this.logout()
      }
    },

    logout() {
      try {
        const tracker = getActivityTracker()
        tracker.track('logout')
        tracker.stop()
      } catch { /* tracker is best-effort */ }
      this.user        = null
      this.permissions = {}
      this.accessToken  = null
      this.refreshToken = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    },
  },
})
