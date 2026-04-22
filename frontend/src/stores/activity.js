import { defineStore } from 'pinia'
import { api } from 'boot/axios'

export const useActivityStore = defineStore('activity', {
  state: () => ({
    summary:   null,    // { date, operators: [...] }
    timeline:  null,    // { user_id, date, buckets: [...], events: [...] }
    heatmap:   null,    // { date_from, date_to, users, cells }
    events:    null,    // { results, count, ... }
    loading:   {
      summary:  false,
      timeline: false,
      heatmap:  false,
      events:   false,
    },
  }),

  actions: {
    async fetchSummary ({ date, role = 'operator', userIds = null } = {}) {
      this.loading.summary = true
      try {
        const params = { role }
        if (date) params.date = date
        if (userIds && userIds.length) params.user_ids = userIds.join(',')
        const res = await api.get('/activity/summary/', { params })
        this.summary = res.data
        return res.data
      } finally {
        this.loading.summary = false
      }
    },

    async fetchTimeline ({ userId, date, bucket = 5 } = {}) {
      if (!userId) return null
      this.loading.timeline = true
      try {
        const params = { user_id: userId, bucket }
        if (date) params.date = date
        const res = await api.get('/activity/timeline/', { params })
        this.timeline = res.data
        return res.data
      } finally {
        this.loading.timeline = false
      }
    },

    async fetchHeatmap ({ dateFrom, dateTo, userIds = null, role = 'operator', bucket = 30 } = {}) {
      this.loading.heatmap = true
      try {
        const params = { bucket, role }
        if (dateFrom) params.date_from = dateFrom
        if (dateTo)   params.date_to   = dateTo
        if (userIds && userIds.length) params.user_ids = userIds.join(',')
        const res = await api.get('/activity/heatmap/', { params })
        this.heatmap = res.data
        return res.data
      } finally {
        this.loading.heatmap = false
      }
    },

    async fetchEvents ({ userId, date, eventType = null, page = 1, pageSize = 500 } = {}) {
      if (!userId) return null
      this.loading.events = true
      try {
        const params = { user_id: userId, page, page_size: pageSize }
        if (date)       params.date = date
        if (eventType)  params.event_type = eventType
        const res = await api.get('/activity/events/', { params })
        this.events = res.data
        return res.data
      } finally {
        this.loading.events = false
      }
    },
  },
})
