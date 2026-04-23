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
      { path: 'kanban',       component: () => import('pages/KanbanPage.vue'),         meta: { section: 'partners' } },
      { path: 'partners',     component: () => import('pages/PartnersPage.vue'),       meta: { section: 'partners' } },
      { path: 'partners/:id', component: () => import('pages/PartnerDetailPage.vue'),  meta: { section: 'partners' } },
      { path: 'sales',        component: () => import('pages/SalesPage.vue'),          meta: { section: 'partners' } },
      { path: 'operators',    component: () => import('pages/OperatorStatsPage.vue'),  meta: { section: 'partners' } },
      { path: 'abandoned',    component: () => import('pages/AbandonedPage.vue'),      meta: { section: 'partners' } },
    ],
  },
  {
    path: '/:catchAll(.*)*',
    redirect: '/',
  },
]

export default routes
