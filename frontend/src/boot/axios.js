import { boot } from 'quasar/wrappers'
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export default boot(({ app, router }) => {
  // Attach token to every request
  api.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })

  // Handle 401 → redirect to login
  api.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true
        const refreshToken = localStorage.getItem('refresh_token')
        if (refreshToken) {
          try {
            const res = await axios.post('/api/auth/refresh/', { refresh: refreshToken })
            localStorage.setItem('access_token', res.data.access)
            if (res.data.refresh) {
              localStorage.setItem('refresh_token', res.data.refresh)
            }
            originalRequest.headers.Authorization = `Bearer ${res.data.access}`
            return api(originalRequest)
          } catch {
            localStorage.clear()
            router.push('/login')
          }
        } else {
          localStorage.clear()
          router.push('/login')
        }
      }
      return Promise.reject(error)
    }
  )

  app.config.globalProperties.$axios = axios
  app.config.globalProperties.$api = api
})

export { api }
