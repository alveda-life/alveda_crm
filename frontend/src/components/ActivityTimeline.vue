<template>
  <div class="activity-timeline" ref="rootEl">
    <svg :viewBox="`0 0 ${VW} ${VH}`" width="100%" preserveAspectRatio="none"
         style="display:block;cursor:crosshair"
         @mousemove="onMove" @mouseleave="hovBucket = null">
      <!-- background (idle) track -->
      <rect :x="0" :y="0" :width="VW" :height="VH" fill="#F5F5F5" />

      <!-- gap highlights (red) inside working window -->
      <rect v-for="(g, i) in gapRects" :key="`gap${i}`"
            :x="g.x" :y="0" :width="g.w" :height="VH"
            fill="#EF5350" opacity="0.18" />

      <!-- active buckets (green) -->
      <rect v-for="(b, i) in activeBuckets" :key="`a${i}`"
            :x="b.x" :y="0" :width="b.w" :height="VH"
            :fill="b.color" />

      <!-- hour gridlines -->
      <line v-for="h in hourTicks" :key="`h${h}`"
            :x1="hourToX(h)" :x2="hourToX(h)"
            :y1="VH - 5" :y2="VH" stroke="#BDBDBD" stroke-width="0.5" />

      <!-- working window markers -->
      <line v-if="firstX !== null"
            :x1="firstX" :x2="firstX" :y1="0" :y2="VH"
            stroke="#1B5E20" stroke-width="1.5" />
      <line v-if="lastX !== null"
            :x1="lastX" :x2="lastX" :y1="0" :y2="VH"
            stroke="#1B5E20" stroke-width="1.5" />

      <!-- hover indicator -->
      <line v-if="hovBucket !== null"
            :x1="hovX" :x2="hovX" :y1="0" :y2="VH"
            stroke="#212121" stroke-width="1" stroke-dasharray="2 2" pointer-events="none" />
    </svg>

    <!-- hour labels -->
    <div class="hour-row">
      <span v-for="h in hourLabels" :key="h"
            :style="`left:${((h - startHour) / windowHours) * 100}%`">{{ h }}h</span>
    </div>

    <div v-if="hovBucket !== null" class="atl-tooltip" :style="tooltipStyle">
      <div class="atl-tooltip__time">{{ hovTimeRange }}</div>
      <div class="atl-tooltip__row">
        <span>Events</span>
        <strong>{{ hovBucket.count }}</strong>
      </div>
      <div v-for="[type, n] in hovBucketTypes" :key="type" class="atl-tooltip__row">
        <span>{{ typeLabel(type) }}</span>
        <strong>{{ n }}</strong>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { getServerMinutes } from 'src/utils/serverTime'

const props = defineProps({
  /** Buckets sparse array: [{ index, ts, count, by_type }] */
  buckets:        { type: Array,  default: () => [] },
  bucketMinutes:  { type: Number, default: 5 },
  /** Highlight gaps wider than this many minutes inside [first, last] window. */
  gapMinutes:     { type: Number, default: 15 },
  /** ISO timestamps for marker rendering (start/end of work window). */
  firstEvent:     { type: String, default: null },
  lastEvent:      { type: String, default: null },
  /** Visible working window (hours of the day). */
  startHour:      { type: Number, default: 7 },
  endHour:        { type: Number, default: 21 },
})

const windowHours   = computed(() => Math.max(1, props.endHour - props.startHour))
const totalMinutes  = computed(() => windowHours.value * 60)
const VW            = computed(() => totalMinutes.value)  // 1 viewBox unit per minute
const VH            = 22

const rootEl    = ref(null)
const hovBucket = ref(null)
const mouseX    = ref(0)

/** Minutes from window start (server TZ), nullable. */
function minutesFromIso (iso) {
  const m = getServerMinutes(iso)
  if (m === null) return null
  return m - props.startHour * 60
}

const firstMin = computed(() => minutesFromIso(props.firstEvent))
const lastMin  = computed(() => minutesFromIso(props.lastEvent))

function clipX (m) {
  if (m === null) return null
  return Math.max(0, Math.min(totalMinutes.value, m))
}

const firstX = computed(() => firstMin.value !== null ? clipX(firstMin.value) : null)
const lastX  = computed(() => lastMin.value  !== null ? clipX(lastMin.value)  : null)

const sortedBuckets = computed(() =>
  [...props.buckets].sort((a, b) => a.index - b.index)
)

const maxCount = computed(() => {
  let m = 1
  for (const b of sortedBuckets.value) if (b.count > m) m = b.count
  return m
})

const activeBuckets = computed(() => {
  const out = []
  const winStart = 0
  const winEnd   = totalMinutes.value
  for (const b of sortedBuckets.value) {
    const startAbs = b.index * props.bucketMinutes
    const start    = startAbs - props.startHour * 60
    const end      = start + props.bucketMinutes
    if (end <= winStart || start >= winEnd) continue
    const x = Math.max(winStart, start)
    const w = Math.min(winEnd, end) - x
    const ratio = Math.min(1, b.count / Math.max(3, maxCount.value))
    const lightness = 50 - 18 * ratio
    out.push({ x, w, color: `hsl(122, 50%, ${lightness}%)` })
  }
  return out
})

/** Compute red gap rectangles between consecutive buckets within the
 *  working window. */
const gapRects = computed(() => {
  if (firstMin.value === null || lastMin.value === null) return []
  const sb = sortedBuckets.value
  if (!sb.length) return []
  const winStart = 0
  const winEnd   = totalMinutes.value
  const fStart   = Math.max(winStart, firstMin.value)
  const fEnd     = Math.min(winEnd,   lastMin.value)
  if (fEnd <= fStart) return []
  const rects = []
  let prevEnd = fStart
  for (const b of sb) {
    const startAbs = b.index * props.bucketMinutes
    const start    = startAbs - props.startHour * 60
    if (start > prevEnd) {
      const gap = start - prevEnd
      if (gap >= props.gapMinutes && start <= fEnd) {
        rects.push({
          x: prevEnd,
          w: Math.min(gap, fEnd - prevEnd),
        })
      }
    }
    const end = start + props.bucketMinutes
    if (end > prevEnd) prevEnd = end
  }
  return rects
})

const hourTicks = computed(() => {
  const arr = []
  for (let h = props.startHour + 1; h < props.endHour; h++) arr.push(h)
  return arr
})

const hourLabels = computed(() => {
  const arr = []
  for (let h = props.startHour; h <= props.endHour; h++) {
    if ((h - props.startHour) % 2 === 0) arr.push(h)
  }
  return arr
})

function hourToX (h) {
  return ((h - props.startHour) * 60)
}

function onMove (e) {
  if (!rootEl.value) return
  const svg = e.currentTarget
  const rect = svg.getBoundingClientRect()
  const ratio = (e.clientX - rect.left) / rect.width
  mouseX.value = ratio
  const minute = ratio * totalMinutes.value + props.startHour * 60
  const idx = Math.floor(minute / props.bucketMinutes)
  hovBucket.value = sortedBuckets.value.find(b => b.index === idx) || null
}

const hovX = computed(() => mouseX.value * VW.value)

const hovTimeRange = computed(() => {
  if (!hovBucket.value) return ''
  const startMin = hovBucket.value.index * props.bucketMinutes
  const endMin = startMin + props.bucketMinutes
  return `${fmtTime(startMin)} – ${fmtTime(endMin)}`
})

const hovBucketTypes = computed(() => {
  if (!hovBucket.value?.by_type) return []
  return Object.entries(hovBucket.value.by_type).sort((a, b) => b[1] - a[1])
})

function fmtTime (totalMin) {
  const h = Math.floor(totalMin / 60).toString().padStart(2, '0')
  const m = Math.floor(totalMin % 60).toString().padStart(2, '0')
  return `${h}:${m}`
}

function typeLabel (t) {
  const map = {
    page_view:      'Page view',
    partner_open:   'Partner open',
    partner_close:  'Partner close',
    contact_create: 'Contact added',
    task_create:    'Task created',
    task_complete:  'Task done',
    note_create:    'Note',
    status_change:  'Status change',
    call_log:       'Call',
    heartbeat:      'Heartbeat',
    login:          'Login',
    logout:         'Logout',
    other:          'Other',
  }
  return map[t] || t
}

const tooltipStyle = computed(() => {
  const left = `${Math.max(0, Math.min(85, mouseX.value * 100))}%`
  return `left:${left}`
})
</script>

<style scoped>
.activity-timeline {
  position: relative;
  width: 100%;
}
.hour-row {
  position: relative;
  height: 14px;
  margin-top: 2px;
  font-size: 9px;
  color: #9E9E9E;
}
.hour-row span {
  position: absolute;
  transform: translateX(-50%);
  white-space: nowrap;
}
.atl-tooltip {
  position: absolute;
  bottom: 100%;
  margin-bottom: 6px;
  background: rgba(33, 33, 33, 0.92);
  color: #fff;
  border-radius: 6px;
  padding: 6px 9px;
  pointer-events: none;
  font-size: 11px;
  min-width: 140px;
  z-index: 5;
  transform: translateX(-50%);
}
.atl-tooltip__time {
  font-weight: 700;
  border-bottom: 1px solid rgba(255,255,255,0.15);
  padding-bottom: 3px;
  margin-bottom: 4px;
}
.atl-tooltip__row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
</style>
