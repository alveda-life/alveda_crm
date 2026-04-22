import { boot } from 'quasar/wrappers'

import { getActivityTracker } from 'src/composables/useActivityTracker'

/**
 * Wire the activity tracker into the router.
 *
 * - Starts on boot if there's already an access token in localStorage
 *   (e.g. user is returning to the page).
 * - Logs every successful navigation as a `page_view` event.
 *
 * Login / logout transitions are also handled here:
 * - On a transition into `/login` we stop the tracker so we don't log noise
 *   while unauthenticated.
 * - The auth store calls tracker.start() right after a successful login.
 */
export default boot(({ router }) => {
  const tracker = getActivityTracker()

  if (typeof localStorage !== 'undefined' && localStorage.getItem('access_token')) {
    tracker.start()
  }

  router.afterEach((to) => {
    if (!to || !to.path) return
    if (to.path === '/login') {
      tracker.stop()
      return
    }
    if (typeof localStorage !== 'undefined' && !localStorage.getItem('access_token')) {
      return
    }
    tracker.start()
    tracker.track('page_view', {
      path:     to.fullPath,
      metadata: {
        name:   to.name || null,
        params: to.params || {},
      },
    })
  })
})
