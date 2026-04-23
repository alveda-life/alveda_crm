import { route } from 'quasar/wrappers'
import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from 'src/stores/auth'
import { getLandingPath } from 'src/utils/landing'

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
      { path: '', redirect: () => getLandingPath(useAuthStore()) },
      { path: 'kanban',           component: () => import('pages/KanbanPage.vue'),           meta: { section: 'partners' } },
      { path: 'partners',         component: () => import('pages/PartnersPage.vue'),         meta: { section: 'partners' } },
      { path: 'partners/:id',     component: () => import('pages/PartnerDetailPage.vue'),    meta: { section: 'partners' } },
      { path: 'sales',            component: () => import('pages/SalesPage.vue'),            meta: { section: 'partners' } },
      { path: 'operators',        component: () => import('pages/OperatorStatsPage.vue'),    meta: { section: 'partners' } },
      { path: 'analytics',        component: () => import('pages/AnalyticsPage.vue'),        meta: { section: 'analytics' } },
      { path: 'operator-activity',component: () => import('pages/OperatorActivityPage.vue'), meta: { section: 'operator_activity' } },
      { path: 'abandoned',        component: () => import('pages/AbandonedPage.vue'),        meta: { section: 'partners' } },
      { path: 'tasks',            component: () => import('pages/TasksPage.vue'),            meta: { section: 'tasks' } },
      { path: 'ai-report',        component: () => import('pages/AiReportPage.vue'),         meta: { section: 'reports' } },
      { path: 'transcriptions',   component: () => import('pages/TranscriptionsPage.vue'),   meta: { adminOnly: true } },
      { path: 'call-quality',     component: () => import('pages/CallQualityPage.vue'),      meta: { adminOnly: true } },
      { path: 'my-feedback',      component: () => import('pages/MyFeedbackPage.vue') },
      { path: 'permissions',      component: () => import('pages/PermissionsPage.vue'),      meta: { adminOnly: true } },
      { path: 'admin/users',      component: () => import('pages/AdminUsersPage.vue'),       meta: { adminOnly: true } },
      { path: 'admin/settings',   component: () => import('pages/AdminSettingsPage.vue'),    meta: { adminOnly: true } },
      { path: 'admin/ai-operations', component: () => import('pages/AiOperationsPage.vue'),  meta: { adminOnly: true } },
      { path: 'producers/onboarding',        component: () => import('pages/ProducersKanbanPage.vue'),  props: { funnel: 'onboarding' }, meta: { sections: ['producers_onboarding', 'producers_support'] } },
      { path: 'producers/support',           component: () => import('pages/ProducersSupportPage.vue'), meta: { section: 'producers_support' } },
      { path: 'producers/tasks',             component: () => import('pages/ProducerTasksPage.vue'),    meta: { sections: ['producers_onboarding', 'producers_support'] } },
      { path: 'producers/updates',           component: () => import('pages/ProducerUpdatesPage.vue'),  meta: { sections: ['producers_onboarding', 'producers_support'] } },
      { path: 'producers/abandoned',         component: () => import('pages/ProducerAbandonedPage.vue'),meta: { sections: ['producers_onboarding', 'producers_support'] } },
      { path: 'producers/analytics',         component: () => import('pages/ProducerAnalyticsPage.vue'),meta: { sections: ['producers_onboarding', 'producers_support'] } },
      { path: 'producers/ai-report',         component: () => import('pages/ProducerAiReportPage.vue'), meta: { sections: ['producers_onboarding', 'producers_support'] } },
      { path: 'producers/general-situation', component: () => import('pages/GeneralSituationPage.vue'), meta: { sections: ['producers_onboarding', 'producers_support'] } },
      { path: 'producers/:id',               component: () => import('pages/ProducerDetailPage.vue'),   meta: { sections: ['producers_onboarding', 'producers_support'] } },
    ],
  },
  {
    path: '/:catchAll(.*)*',
    redirect: '/',
  },
]

function checkAccess(auth, meta) {
  if (!meta) return true
  if (meta.adminOnly) return !!auth.isAdmin
  if (meta.section)   return auth.can(meta.section, 'view')
  if (Array.isArray(meta.sections) && meta.sections.length) {
    return meta.sections.some(s => auth.can(s, 'view'))
  }
  return true
}

export default route(function (/* { store, ssrContext } */) {
  const router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createWebHashHistory(),
  })

  router.beforeEach(async (to, from, next) => {
    const token = localStorage.getItem('access_token')

    if (to.meta.requiresAuth && !token) return next('/login')

    if (to.path === '/login' && token) {
      const auth = useAuthStore()
      if (!auth.user) {
        try { await auth.fetchMe() } catch { /* fetchMe handles its own logout */ }
      }
      return next(getLandingPath(auth))
    }

    if (token) {
      const auth = useAuthStore()
      if (!auth.user) {
        try { await auth.fetchMe() } catch { /* fetchMe handles its own logout */ }
      }
      // If fetchMe failed and cleared the token, bounce to login.
      if (!auth.user) return next('/login')

      if (!checkAccess(auth, to.meta)) {
        return next(getLandingPath(auth))
      }
    }

    next()
  })

  return router
})
