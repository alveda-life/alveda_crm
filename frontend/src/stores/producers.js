import { defineStore } from 'pinia'
import { api } from 'boot/axios'

export const useProducersStore = defineStore('producers', {
  state: () => ({
    // Kanban: { stage_key: [producer, ...] }
    kanbanData: {},
    // Flat list for table views
    producers: [],
    currentProducer: null,
    stats: null,
    users: [],
    loading: false,
    activeFunnel: 'onboarding',
    filters: {
      search: '',
      assigned_to: '',
    },
    openTasksCount: 0,
  }),

  actions: {
    // ── Kanban ──────────────────────────────────────────────────────────────
    async fetchKanban(funnel) {
      if (funnel) this.activeFunnel = funnel
      this.loading = true
      try {
        const params = { funnel: this.activeFunnel }
        if (this.filters.search)      params.search      = this.filters.search
        if (this.filters.assigned_to) params.assigned_to = this.filters.assigned_to
        const res = await api.get('/producers/kanban/', { params })
        const data = res.data
        // For onboarding funnel: sort each column by planned_connection_date ascending
        // (cards with a date first, closest date at top; no date goes to bottom)
        if (this.activeFunnel === 'onboarding') {
          for (const col of Object.values(data)) {
            col.sort((a, b) => {
              if (a.planned_connection_date && b.planned_connection_date)
                return a.planned_connection_date.localeCompare(b.planned_connection_date)
              if (a.planned_connection_date) return -1
              if (b.planned_connection_date) return 1
              return 0
            })
          }
        }
        this.kanbanData = data
      } finally {
        this.loading = false
      }
    },

    // ── Flat list ────────────────────────────────────────────────────────────
    async fetchProducers(params = {}) {
      const res = await api.get('/producers/', { params })
      this.producers = res.data.results ?? res.data
      return this.producers
    },

    // ── CRUD ─────────────────────────────────────────────────────────────────
    async fetchProducer(id) {
      this.loading = true
      try {
        const res = await api.get(`/producers/${id}/`)
        this.currentProducer = res.data
        return res.data
      } finally {
        this.loading = false
      }
    },

    async createProducer(data) {
      const res = await api.post('/producers/', data)
      // Add to kanban if current funnel matches
      const p = res.data
      if (p.funnel === this.activeFunnel && this.kanbanData[p.stage]) {
        this.kanbanData[p.stage].unshift(p)
      }
      return p
    },

    async updateProducer(id, data) {
      const res = await api.patch(`/producers/${id}/`, data)
      this._syncKanbanCard(res.data)
      if (this.currentProducer?.id === id) {
        this.currentProducer = { ...this.currentProducer, ...res.data }
      }
      return res.data
    },

    async deleteProducer(id) {
      await api.delete(`/producers/${id}/`)
      this._removeFromKanban(id)
      if (this.currentProducer?.id === id) this.currentProducer = null
    },

    // ── Stage ─────────────────────────────────────────────────────────────────
    async updateStage(id, stage, funnel) {
      const payload = { stage }
      if (funnel) payload.funnel = funnel
      const res = await api.patch(`/producers/${id}/stage/`, payload)
      this._removeFromKanban(id)
      const p = res.data
      // After auto-transition, funnel may differ from activeFunnel — only insert if still visible
      if (p.funnel === this.activeFunnel && this.kanbanData[p.stage] !== undefined) {
        this.kanbanData[p.stage].unshift(p)
      }
      if (this.currentProducer?.id === id) {
        this.currentProducer = { ...this.currentProducer, ...p }
      }
      return p
    },

    // ── Tasks ─────────────────────────────────────────────────────────────────
    async addTask(producerId, data) {
      const res = await api.post(`/producers/${producerId}/tasks/`, data)
      if (this.currentProducer?.id === producerId) {
        this.currentProducer = res.data
      }
      return res.data
    },

    async updateTask(producerId, taskId, data) {
      const res = await api.patch(`/producers/${producerId}/tasks/${taskId}/`, data)
      if (this.currentProducer?.id === producerId) {
        this.currentProducer = res.data
      }
      return res.data
    },

    async deleteTask(producerId, taskId) {
      const res = await api.delete(`/producers/${producerId}/tasks/${taskId}/delete/`)
      if (this.currentProducer?.id === producerId) {
        this.currentProducer = res.data
      }
      return res.data
    },

    // ── Comments ──────────────────────────────────────────────────────────────
    async addComment(producerId, formData) {
      const res = await api.post(`/producers/${producerId}/comments/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      if (this.currentProducer?.id === producerId) {
        this.currentProducer = res.data
      }
      return res.data
    },

    async deleteComment(producerId, commentId) {
      const res = await api.delete(`/producers/${producerId}/comments/${commentId}/`)
      if (this.currentProducer?.id === producerId) {
        this.currentProducer = res.data
      }
      return res.data
    },

    // ── Producer Tasks (global) ───────────────────────────────────────────────
    async fetchProducerTasks(params = {}) {
      const res = await api.get('/producer-tasks/', { params })
      return res.data
    },

    async createProducerTask(data) {
      const res = await api.post('/producer-tasks/', data)
      return res.data
    },

    async updateProducerTask(id, data) {
      const res = await api.patch(`/producer-tasks/${id}/`, data)
      return res.data
    },

    async deleteProducerTask(id) {
      await api.delete(`/producer-tasks/${id}/`)
    },

    async refreshOpenTasksCount() {
      const res = await api.get('/producer-tasks/open-count/')
      this.openTasksCount = res.data.count
      return this.openTasksCount
    },

    // ── Stats ─────────────────────────────────────────────────────────────────
    async fetchStats() {
      const res = await api.get('/producers/stats/')
      this.stats = res.data
      return res.data
    },

    async fetchUsers() {
      if (this.users.length) return this.users
      const res = await api.get('/users/')
      this.users = res.data
      return res.data
    },

    // ── Helpers ───────────────────────────────────────────────────────────────
    _removeFromKanban(id) {
      for (const col of Object.values(this.kanbanData)) {
        const idx = col.findIndex(p => p.id === id)
        if (idx !== -1) { col.splice(idx, 1); break }
      }
    },

    _syncKanbanCard(producer) {
      for (const col of Object.values(this.kanbanData)) {
        const idx = col.findIndex(p => p.id === producer.id)
        if (idx !== -1) { col.splice(idx, 1, producer); return }
      }
    },
  },
})
