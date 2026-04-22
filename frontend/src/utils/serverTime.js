/**
 * Server-side timezone helpers.
 *
 * The backend stores all timestamps in UTC but operates / aggregates in
 * `Asia/Kolkata` (see Django `TIME_ZONE` setting). Activity buckets, etc.
 * are therefore indexed in IST. To keep the analytics views consistent
 * across operator browsers in any geography, we always render times in
 * the server's own timezone using these helpers instead of relying on
 * the browser's local clock.
 */

export const SERVER_TZ = 'Asia/Kolkata'

const PARTS_FORMATTER = new Intl.DateTimeFormat('en-GB', {
  timeZone: SERVER_TZ,
  year:    'numeric',
  month:   '2-digit',
  day:     '2-digit',
  hour:    '2-digit',
  minute:  '2-digit',
  second:  '2-digit',
  hour12:  false,
})

function toDate (input) {
  if (input instanceof Date) return input
  if (input == null) return null
  const d = new Date(input)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Return numeric Y/M/D/H/M/S in the server timezone. */
export function getServerParts (input) {
  const d = toDate(input)
  if (!d) return null
  const out = {}
  for (const p of PARTS_FORMATTER.formatToParts(d)) {
    if (p.type === 'literal') continue
    let v = parseInt(p.value, 10)
    if (p.type === 'hour' && v === 24) v = 0  // some engines emit "24" for midnight
    out[p.type] = v
  }
  return out
}

/** Minutes since midnight (server TZ). */
export function getServerMinutes (input) {
  const p = getServerParts(input)
  if (!p) return null
  return p.hour * 60 + p.minute + p.second / 60
}

/** "HH:mm" in server TZ, or "—" for nullish input. */
export function formatServerTime (input, fallback = '—') {
  const p = getServerParts(input)
  if (!p) return fallback
  return `${String(p.hour).padStart(2, '0')}:${String(p.minute).padStart(2, '0')}`
}

/** "Mon DD, HH:mm:ss" in server TZ. */
export function formatServerDateTime (input, fallback = '') {
  const d = toDate(input)
  if (!d) return fallback
  return new Intl.DateTimeFormat(undefined, {
    timeZone: SERVER_TZ,
    month:    'short',
    day:      '2-digit',
    hour:     '2-digit',
    minute:   '2-digit',
    second:   '2-digit',
    hour12:   false,
  }).format(d)
}

/** Calendar date (YYYY-MM-DD) in the server timezone. */
export function getServerDate (input = new Date()) {
  const p = getServerParts(input)
  if (!p) return null
  return `${p.year}-${String(p.month).padStart(2, '0')}-${String(p.day).padStart(2, '0')}`
}
