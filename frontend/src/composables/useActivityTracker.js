/**
 * Activity tracker — buffers user activity events and ships them to
 * `POST /api/activity/events/` in batches.
 *
 * Designed to be cheap on the network (max 1 request per FLUSH_INTERVAL_MS or
 * MAX_BATCH_SIZE events) and resilient to tab close (uses `sendBeacon`).
 *
 * Public API:
 *   const tracker = getActivityTracker()
 *   tracker.start()                                  // call after login
 *   tracker.stop()                                   // call on logout
 *   tracker.track('partner_open', { object_id: 7 }) // log an event
 *
 * Auth: relies on the access_token in localStorage (the same one axios uses).
 */

import { api } from 'boot/axios'

const FLUSH_INTERVAL_MS  = 10_000
const HEARTBEAT_INTERVAL_MS = 30_000
const HEARTBEAT_IDLE_MS  = 60_000  // stop sending heartbeats after this idle
const MAX_BATCH_SIZE     = 20
const SESSION_STORAGE_KEY = 'activity_session_key'

const VALID_EVENT_TYPES = new Set([
  'page_view', 'partner_open', 'partner_close',
  'contact_create', 'task_create', 'task_complete',
  'note_create', 'status_change', 'call_log',
  'heartbeat', 'login', 'logout', 'other',
])

function getOrCreateSessionKey () {
  try {
    let key = sessionStorage.getItem(SESSION_STORAGE_KEY)
    if (!key) {
      // crypto.randomUUID is available in all evergreen browsers; fall back
      // to a v4-shaped UUID using Math.random for older environments.
      key = (typeof crypto !== 'undefined' && crypto.randomUUID)
        ? crypto.randomUUID()
        : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
            const r = Math.random() * 16 | 0
            const v = c === 'x' ? r : (r & 0x3 | 0x8)
            return v.toString(16)
          })
      sessionStorage.setItem(SESSION_STORAGE_KEY, key)
    }
    return key
  } catch {
    return null
  }
}

function makeTracker () {
  const state = {
    buffer:        [],
    sessionKey:    null,
    flushTimer:    null,
    heartbeatTimer: null,
    lastInputAt:   Date.now(),
    started:       false,
    inputListenersAttached: false,
    visibilityListenerAttached: false,
    unloadListenerAttached: false,
  }

  function markInput () {
    state.lastInputAt = Date.now()
  }

  function attachInputListeners () {
    if (state.inputListenersAttached || typeof window === 'undefined') return
    const opts = { passive: true, capture: true }
    window.addEventListener('mousemove', markInput, opts)
    window.addEventListener('mousedown', markInput, opts)
    window.addEventListener('keydown',   markInput, opts)
    window.addEventListener('scroll',    markInput, opts)
    window.addEventListener('touchstart', markInput, opts)
    state.inputListenersAttached = true
  }

  function attachVisibilityListener () {
    if (state.visibilityListenerAttached || typeof document === 'undefined') return
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        flushSync()
      } else {
        markInput()
      }
    })
    state.visibilityListenerAttached = true
  }

  function attachUnloadListener () {
    if (state.unloadListenerAttached || typeof window === 'undefined') return
    // pagehide fires more reliably than beforeunload on mobile / bfcache.
    window.addEventListener('pagehide', () => flushSync())
    window.addEventListener('beforeunload', () => flushSync())
    state.unloadListenerAttached = true
  }

  function track (eventType, payload = {}) {
    if (!state.started) return
    if (!VALID_EVENT_TYPES.has(eventType)) {
      // Don't fail loudly — just downgrade to "other" so we still log something.
      payload = { ...payload, original_type: eventType }
      eventType = 'other'
    }
    const event = {
      event_type:  eventType,
      object_type: payload.object_type || '',
      object_id:   payload.object_id ?? null,
      path:        payload.path || (typeof window !== 'undefined'
                      ? window.location.hash || window.location.pathname
                      : ''),
      metadata:    payload.metadata || {},
      session_key: state.sessionKey,
      client_ts:   new Date().toISOString(),
    }
    state.buffer.push(event)
    markInput()
    if (state.buffer.length >= MAX_BATCH_SIZE) {
      flush()
    }
  }

  async function flush () {
    if (!state.buffer.length) return
    const batch = state.buffer.splice(0, state.buffer.length)
    try {
      await api.post('/activity/events/', batch)
    } catch (err) {
      // Network / 5xx: drop the batch — these are non-critical analytics events
      // and we don't want to risk an unbounded queue. 401 is also dropped (the
      // axios interceptor will redirect to /login).
      if (err?.response?.status && err.response.status !== 401) {
        // eslint-disable-next-line no-console
        console.warn('[activity] flush failed:', err.response.status)
      }
    }
  }

  function flushSync () {
    if (!state.buffer.length) return
    const batch = state.buffer.splice(0, state.buffer.length)
    try {
      const token = localStorage.getItem('access_token')
      const url = '/api/activity/events/'
      // sendBeacon doesn't carry custom headers, so it can't authenticate via
      // Bearer token. Fall back to a synchronous-style fetch with `keepalive`
      // when we have a token (this is the recommended replacement and works
      // during pagehide / unload).
      if (token && typeof fetch !== 'undefined') {
        fetch(url, {
          method:  'POST',
          headers: {
            'Content-Type':  'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body:      JSON.stringify(batch),
          keepalive: true,
        }).catch(() => {})
        return
      }
      if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
        const blob = new Blob([JSON.stringify(batch)], { type: 'application/json' })
        navigator.sendBeacon(url, blob)
      }
    } catch {
      // Best effort — never throw from a tab-close handler.
    }
  }

  function startTimers () {
    if (!state.flushTimer) {
      state.flushTimer = setInterval(flush, FLUSH_INTERVAL_MS)
    }
    if (!state.heartbeatTimer) {
      state.heartbeatTimer = setInterval(() => {
        if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return
        if (Date.now() - state.lastInputAt > HEARTBEAT_IDLE_MS) return
        track('heartbeat')
      }, HEARTBEAT_INTERVAL_MS)
    }
  }

  function stopTimers () {
    if (state.flushTimer) {
      clearInterval(state.flushTimer)
      state.flushTimer = null
    }
    if (state.heartbeatTimer) {
      clearInterval(state.heartbeatTimer)
      state.heartbeatTimer = null
    }
  }

  function start () {
    if (state.started) return
    state.sessionKey = getOrCreateSessionKey()
    state.started = true
    state.lastInputAt = Date.now()
    attachInputListeners()
    attachVisibilityListener()
    attachUnloadListener()
    startTimers()
  }

  function stop ({ flushImmediate = true } = {}) {
    if (!state.started) return
    state.started = false
    stopTimers()
    if (flushImmediate) flushSync()
  }

  return { start, stop, track, flush, flushSync }
}

let _instance = null

export function getActivityTracker () {
  if (!_instance) {
    _instance = makeTracker()
  }
  return _instance
}
