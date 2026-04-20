import { defineStore } from 'pinia'
import { api } from 'boot/axios'

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
      return res.data
    },

    async updateTask(id, data) {
      const res = await api.patch(`/tasks/${id}/`, data)
      return res.data
    },

    async deleteTask(id) {
      await api.delete(`/tasks/${id}/`)
    },

    async addComment(taskId, text) {
      const res = await api.post(`/tasks/${taskId}/comments/`, { text })
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
