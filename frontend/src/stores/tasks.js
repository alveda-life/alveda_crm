import { defineStore } from 'pinia'
import { api } from 'boot/axios'
import { getActivityTracker } from 'src/composables/useActivityTracker'

function trackSafe (eventType, payload) {
  try { getActivityTracker().track(eventType, payload) } catch { /* best-effort */ }
}

export const useTasksStore = defineStore('tasks', {
  state: () => ({
    openCount: 0,
  }),

  actions: {
    async fetchTasks(params = {}) {
      const res = await api.get('/tasks/', { params })
      return res.data
    },

    async fetchTask(id) {
      const res = await api.get(`/tasks/${id}/`)
      return res.data
    },

    async createTask(data) {
      const res = await api.post('/tasks/', data)
      trackSafe('task_create', {
        object_type: 'task',
        object_id:   res.data?.id ?? null,
        metadata:    {
          partner: data?.partner ?? null,
          due:     data?.due_date ?? null,
        },
      })
      return res.data
    },

    async updateTask(id, data) {
      const res = await api.patch(`/tasks/${id}/`, data)
      const eventType = data?.status === 'done' ? 'task_complete' : 'other'
      trackSafe(eventType, {
        object_type: 'task',
        object_id:   id,
        metadata:    { action: 'task_update', fields: Object.keys(data || {}) },
      })
      return res.data
    },

    async deleteTask(id) {
      await api.delete(`/tasks/${id}/`)
    },

    async addComment(taskId, text) {
      const res = await api.post(`/tasks/${taskId}/comments/`, { text })
      trackSafe('note_create', {
        object_type: 'task',
        object_id:   taskId,
        metadata:    { length: text?.length || 0 },
      })
      return res.data  // returns updated full task
    },

    async deleteComment(taskId, commentId) {
      const res = await api.delete(`/tasks/${taskId}/comments/${commentId}/`)
      return res.data  // returns updated full task
    },

    async refreshOpenCount() {
      const res = await api.get('/tasks/open-count/')
      this.openCount = res.data.count
      return this.openCount
    },
  },
})
