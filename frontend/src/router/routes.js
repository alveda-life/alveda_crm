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
      { path: 'abandoned', component: () => import('pages/AbandonedPage.vue') },
    ],
  },
  {
    path: '/:catchAll(.*)*',
    redirect: '/',
  },
]

export default routes
