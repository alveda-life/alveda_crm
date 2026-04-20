import { defineStore } from 'pinia'
import { api } from 'boot/axios'

const POLL_INTERVAL = 4000

export const useReportsStore = defineStore('reports', {
  state: () => ({
    partnerReports:   [],
    producerReports:  [],
    loading: false,
    _pollTimer: null,
    // legacy alias — kept so any stray references don't crash
    get reports() { return this.partnerReports },
  }),
  actions: {
    _listFor(reportType) {
      return reportType === 'producers' ? this.producerReports : this.partnerReports
    },

    async fetchReports(reportType = 'partners') {
      const res = await api.get('/ai-reports/', { params: { report_type: reportType } })
      const list = res.data.results || res.data
      if (reportType === 'producers') this.producerReports = list
      else                            this.partnerReports  = list
      this._maybeStartPolling()
    },

    async generateReport(prompt, reportType = 'partners') {
      const res = await api.post('/ai-reports/generate/', { prompt, report_type: reportType })
      if (reportType === 'producers') this.producerReports.unshift(res.data)
      else                            this.partnerReports.unshift(res.data)
      this._maybeStartPolling()
      return res.data
    },

    async deleteReport(id, reportType = 'partners') {
      await api.delete(`/ai-reports/${id}/`)
      if (reportType === 'producers')
        this.producerReports = this.producerReports.filter(r => r.id !== id)
      else
        this.partnerReports  = this.partnerReports.filter(r => r.id !== id)
      if (!this._hasPending()) this._stopPolling()
    },

    async _pollOnce() {
      const allLists = [this.partnerReports, this.producerReports]
      const pending  = allLists.flat().filter(r => r.status === 'pending' || r.status === 'generating')
      if (!pending.length) { this._stopPolling(); return }

      for (const r of pending) {
        try {
          const res = await api.get(`/ai-reports/${r.id}/`)
          for (const list of allLists) {
            const idx = list.findIndex(x => x.id === r.id)
            if (idx !== -1) { list[idx] = res.data; break }
          }
        } catch (_) {}
      }

      if (!this._hasPending()) this._stopPolling()
    },

    _hasPending() {
      return [...this.partnerReports, ...this.producerReports]
        .some(r => r.status === 'pending' || r.status === 'generating')
    },

    _maybeStartPolling() {
      if (this._hasPending() && !this._pollTimer) {
        this._pollTimer = setInterval(() => this._pollOnce(), POLL_INTERVAL)
      }
    },

    _stopPolling() {
      if (this._pollTimer) {
        clearInterval(this._pollTimer)
        this._pollTimer = null
      }
    },
  },
})
