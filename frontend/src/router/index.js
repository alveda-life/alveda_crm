import { route } from 'quasar/wrappers'
import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    component: () => import('pages/LoginPage.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/kanban' },
      { path: 'kanban', component: () => import('pages/KanbanPage.vue') },
      { path: 'partners', component: () => import('pages/PartnersPage.vue') },
      { path: 'partners/:id', component: () => import('pages/PartnerDetailPage.vue') },
      { path: 'sales', component: () => import('pages/SalesPage.vue') },
      { path: 'operators', component: () => import('pages/OperatorStatsPage.vue') },
      { path: 'analytics', component: () => import('pages/AnalyticsPage.vue') },
      { path: 'operator-activity', component: () => import('pages/OperatorActivityPage.vue') },
      { path: 'abandoned', component: () => import('pages/AbandonedPage.vue') },
      { path: 'tasks',    component: () => import('pages/TasksPage.vue') },
      { path: 'ai-report', component: () => import('pages/AiReportPage.vue') },
      { path: 'transcriptions', component: () => import('pages/TranscriptionsPage.vue') },
      { path: 'call-quality', component: () => import('pages/CallQualityPage.vue') },
      { path: 'my-feedback', component: () => import('pages/MyFeedbackPage.vue') },
      { path: 'permissions', component: () => import('pages/PermissionsPage.vue') },
      { path: 'admin/users', component: () => import('pages/AdminUsersPage.vue') },
      { path: 'admin/settings', component: () => import('pages/AdminSettingsPage.vue') },
      { path: 'admin/ai-operations', component: () => import('pages/AiOperationsPage.vue') },
      { path: 'admin/call-insights', component: () => import('pages/InsightsPage.vue') },
      { path: 'admin/general-insights', component: () => import('pages/GeneralInsightsPage.vue') },
      { path: 'producers/onboarding',  component: () => import('pages/ProducersKanbanPage.vue'),    props: { funnel: 'onboarding' } },
      { path: 'producers/support',     component: () => import('pages/ProducersSupportPage.vue') },
      { path: 'producers/tasks',       component: () => import('pages/ProducerTasksPage.vue') },
      { path: 'producers/updates',     component: () => import('pages/ProducerUpdatesPage.vue') },
      { path: 'producers/abandoned',    component: () => import('pages/ProducerAbandonedPage.vue') },
      { path: 'producers/analytics',   component: () => import('pages/ProducerAnalyticsPage.vue') },
      { path: 'producers/ai-report',   component: () => import('pages/ProducerAiReportPage.vue') },
      { path: 'producers/general-situation', component: () => import('pages/GeneralSituationPage.vue') },
      { path: 'producers/weekly-report', component: () => import('pages/ProducerWeeklyReportPage.vue') },
      { path: 'producers/:id',         component: () => import('pages/ProducerDetailPage.vue') },
    ],
  },
  {
    path: '/:catchAll(.*)*',
    redirect: '/',
  },
]

export default route(function (/* { store, ssrContext } */) {
  const router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createWebHashHistory(),
  })

  router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('access_token')
    if (to.meta.requiresAuth && !token) {
      next('/login')
    } else if (to.path === '/login' && token) {
      next('/kanban')
    } else {
      next()
    }
  })

  return router
})
