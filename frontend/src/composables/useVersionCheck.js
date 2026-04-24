/**
 * Version check — polls /version.json (written by quasar.config.js afterBuild)
 * and flips `updateAvailable` to true when the deployed build differs from the
 * one the SPA was loaded with.
 *
 * Used by App.vue to render a banner that asks the operator to refresh after
 * a deploy. Without this, browsers keep running the old hashed JS bundles
 * referenced by the previously cached index.html and operators don't know
 * they need to hard-reload.
 *
 * Failures (404 in dev, network errors) are swallowed — we never want a
 * flaky version probe to surface as a UI error.
 */

import { ref, onMounted, onBeforeUnmount } from 'vue'

const POLL_INTERVAL_MS = 60_000
const VERSION_URL = '/version.json'

async function fetchVersion () {
  // Cache-busting query string defends against any intermediate cache that
  // ignores Cache-Control (corporate proxies, service workers, etc).
  const res = await fetch(`${VERSION_URL}?t=${Date.now()}`, {
    cache: 'no-store',
    credentials: 'omit',
  })
  if (!res.ok) {
    throw new Error(`version.json HTTP ${res.status}`)
  }
  const data = await res.json()
  if (!data || typeof data.version !== 'string') {
    throw new Error('version.json missing "version" field')
  }
  return data.version
}

export function useVersionCheck () {
  const updateAvailable = ref(false)
  let initialVersion = null
  let timer = null

  const check = async () => {
    if (updateAvailable.value) return
    try {
      const current = await fetchVersion()
      if (initialVersion === null) {
        initialVersion = current
        return
      }
      if (current !== initialVersion) {
        updateAvailable.value = true
        if (timer) {
          clearInterval(timer)
          timer = null
        }
      }
    } catch (_) {
      // Ignore — keep polling, don't bother the operator.
    }
  }

  const onVisibility = () => {
    if (document.visibilityState === 'visible') {
      check()
    }
  }

  onMounted(() => {
    check()
    timer = setInterval(check, POLL_INTERVAL_MS)
    document.addEventListener('visibilitychange', onVisibility)
  })

  onBeforeUnmount(() => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    document.removeEventListener('visibilitychange', onVisibility)
  })

  const reload = () => {
    window.location.reload()
  }

  return { updateAvailable, reload }
}
