/**
 * Single source of truth for "where should this user land?".
 * Used by the post-login redirect, the root-path redirect, and the route guard
 * (when bouncing a user away from a section they cannot view).
 */

const ROLE_LANDING = {
  admin:               '/kanban',
  operator:            '/kanban',
  producer_operator:   '/producers/onboarding',
  producer_onboarding: '/producers/onboarding',
  producer_support:    '/producers/support',
}

const PERMISSION_FALLBACK = [
  ['partners',             '/kanban'],
  ['producers_onboarding', '/producers/onboarding'],
  ['producers_support',    '/producers/support'],
  ['tasks',                '/tasks'],
  ['reports',              '/ai-report'],
]

export function getLandingPath(authStore) {
  const role = authStore?.user?.role
  if (role && ROLE_LANDING[role]) return ROLE_LANDING[role]

  if (authStore && typeof authStore.can === 'function') {
    for (const [section, path] of PERMISSION_FALLBACK) {
      if (authStore.can(section, 'view')) return path
    }
  }

  return '/my-feedback'
}
