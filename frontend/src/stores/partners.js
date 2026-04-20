import { defineStore } from 'pinia'
import { api } from 'boot/axios'

export const usePartnersStore = defineStore('partners', {
  state: () => ({
    kanbanData: {
      new: [],
      trained: [],
      set_created: [],
      has_sale: [],
      no_answer: [],
      declined: [],
      no_sales: [],
    },
    kanbanTotals: {},
    kanbanHasMore: {},
    partnersList: [],
    currentPartner: null,
    stats: null,
    users: [],
    loading: false,
    filters: {
      search: '',
      type: '',
      category: '',
      assigned_to: '',
    },
  }),

  getters: {
    totalPartners: (state) => {
      return Object.values(state.kanbanTotals).reduce((sum, n) => sum + n, 0)
    },
  },

  actions: {
    _filterParams() {
      const params = {}
      if (this.filters.search) params.search = this.filters.search
      if (this.filters.type) params.type = this.filters.type
      if (this.filters.category) params.category = this.filters.category
      if (this.filters.assigned_to) params.assigned_to = this.filters.assigned_to
      return params
    },

    async fetchKanban() {
      this.loading = true
      try {
        const res = await api.get('/partners/kanban/', { params: this._filterParams() })
        const data = res.data
        const kanban = {}
        const totals = {}
        const hasMore = {}
        for (const [stage, info] of Object.entries(data)) {
          kanban[stage] = info.items
          totals[stage] = info.total
          hasMore[stage] = info.has_more
        }
        this.kanbanData = kanban
        this.kanbanTotals = totals
        this.kanbanHasMore = hasMore
      } finally {
        this.loading = false
      }
    },

    async fetchKanbanMore(stage) {
      const offset = (this.kanbanData[stage] || []).length
      const params = { ...this._filterParams(), stage, offset, limit: 50 }
      const res = await api.get('/partners/kanban-more/', { params })
      const data = res.data
      this.kanbanData[stage] = [...this.kanbanData[stage], ...data.items]
      this.kanbanTotals[stage] = data.total
      this.kanbanHasMore[stage] = data.has_more
    },

    async fetchPartners(params = {}) {
      this.loading = true
      try {
        const res = await api.get('/partners/', { params })
        this.partnersList = res.data.results || res.data
        return res.data
      } finally {
        this.loading = false
      }
    },

    async fetchPartner(id) {
      this.loading = true
      try {
        const res = await api.get(`/partners/${id}/`)
        this.currentPartner = res.data
        return res.data
      } finally {
        this.loading = false
      }
    },

    async createPartner(data) {
      const res = await api.post('/partners/', data)
      return res.data
    },

    async updatePartner(id, data) {
      const res = await api.patch(`/partners/${id}/`, data)
      if (this.currentPartner?.id === id) {
        this.currentPartner = res.data
      }
      return res.data
    },

    async updateStage(id, stage) {
      const res = await api.patch(`/partners/${id}/stage/`, { stage })
      for (const [col, items] of Object.entries(this.kanbanData)) {
        const idx = items.findIndex(p => p.id === id)
        if (idx !== -1) {
          items.splice(idx, 1)
          if (this.kanbanTotals[col]) this.kanbanTotals[col]--
          break
        }
      }
      if (this.kanbanData[stage]) {
        this.kanbanData[stage].unshift(res.data)
        this.kanbanTotals[stage] = (this.kanbanTotals[stage] || 0) + 1
      }
      return res.data
    },

    async deletePartner(id) {
      await api.delete(`/partners/${id}/`)
      // Remove from all collections
      for (const col of Object.values(this.kanbanData)) {
        const idx = col.findIndex(p => p.id === id)
        if (idx !== -1) col.splice(idx, 1)
      }
      const listIdx = this.partnersList.findIndex(p => p.id === id)
      if (listIdx !== -1) this.partnersList.splice(listIdx, 1)
    },

    async fetchStats() {
      const res = await api.get('/partners/stats/')
      this.stats = res.data
      return res.data
    },

    async fetchUsers() {
      const res = await api.get('/users/')
      this.users = res.data
      return res.data
    },

    async fetchOperatorStats(period = 'week') {
      const res = await api.get('/operators/stats/', { params: { period } })
      return res.data
    },

    async fetchAbandoned(params = {}) {
      const res = await api.get('/partners/abandoned/', { params })
      return res.data
    },

    async fetchAbandonedCount() {
      const res = await api.get('/partners/abandoned-count/')
      return res.data.count
    },

    async fetchAnalytics(period = 'week', dateFrom = null, dateTo = null) {
      const params = { period }
      if (period === 'custom' && dateFrom && dateTo) {
        params.date_from = dateFrom
        params.date_to = dateTo
      }
      const res = await api.get('/analytics/', { params })
      return res.data
    },

    // Contacts
    async fetchContacts(partnerId) {
      const res = await api.get('/contacts/', { params: { partner: partnerId } })
      return res.data.results || res.data
    },

    async createContact(formData) {
      const res = await api.post('/contacts/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return res.data
    },

    async updateContact(id, data) {
      const res = await api.patch(`/contacts/${id}/`, data, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return res.data
    },

    async deleteContact(id) {
      await api.delete(`/contacts/${id}/`)
    },

    async retryTranscription(id) {
      const res = await api.post(`/contacts/${id}/retry-transcription/`)
      return res.data
    },

    async retrySummary(id) {
      const res = await api.post(`/contacts/${id}/retry-summary/`)
      return res.data
    },
  },
})
