<template>
  <div class="activity-scatter" ref="rootEl">
    <div v-if="!events.length" class="empty">No events for this day</div>

    <template v-else>
      <div v-if="showLegend" class="legend">
        <div v-for="t in usedTypes" :key="t" class="legend-item">
          <span class="legend-dot" :style="`background:${colorOf(t)}`" />
          <span>{{ typeLabel(t) }}</span>
        </div>
      </div>

      <svg :viewBox="`0 0 ${VW} ${VH}`" width="100%" preserveAspectRatio="none"
           style="display:block;cursor:crosshair"
           @mousemove="onMove" @mouseleave="hovEvent = null">
        <!-- horizontal lanes (one per event_type) -->
        <line v-for="(t, i) in usedTypes" :key="`lane${t}`"
              :x1="PL" :x2="VW - PR"
              :y1="laneY(i)" :y2="laneY(i)"
              stroke="#EEEEEE" stroke-width="1" />
        <text v-for="(t, i) in usedTypes" :key="`lbl${t}`"
              :x="PL - 6" :y="laneY(i) + 3"
              text-anchor="end" font-size="9" fill="#9E9E9E">
          {{ typeLabel(t) }}
        </text>

        <!-- hour gridlines along x -->
        <g pointer-events="none">
          <line v-for="h in hourTicks" :key="`g${h}`"
                :x1="hourX(h)" :x2="hourX(h)"
                :y1="PT" :y2="VH - PB"
                stroke="#F5F5F5" stroke-width="1" />
          <text v-for="h in hourLabels" :key="`hl${h}`"
                :x="hourX(h)" :y="VH - 6"
                text-anchor="middle" font-size="9" fill="#BDBDBD">
            {{ h }}h
          </text>
        </g>

        <!-- event dots -->
        <circle v-for="(e, i) in laidOutEvents" :key="e.id"
                :cx="e.x" :cy="e.y" :r="hovEvent?.id === e.id ? 5 : 3"
                :fill="colorOf(e.event_type)" stroke="#fff" stroke-width="1"
                style="cursor:pointer"
                @mouseenter="hovEvent = e" />
      </svg>
    </template>

    <div v-if="hovEvent" class="sc-tooltip" :style="tooltipStyle">
      <div class="sc-tooltip__time">{{ formatTime(hovEvent.created_at) }}</div>
      <div class="sc-tooltip__row">
        <span class="sc-tooltip__dot" :style="`background:${colorOf(hovEvent.event_type)}`" />
        <strong>{{ typeLabel(hovEvent.event_type) }}</strong>
      </div>
      <div v-if="hovEvent.path" class="sc-tooltip__path">{{ hovEvent.path }}</div>
      <div v-if="hovEvent.object_type" class="sc-tooltip__path">
        {{ hovEvent.object_type }}{{ hovEvent.object_id ? `#${hovEvent.object_id}` : '' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { getServerMinutes, formatServerDateTime } from 'src/utils/serverTime'

const props = defineProps({
  events:     { type: Array,   default: () => [] },
  showLegend: { type: Boolean, default: true },
  startHour:  { type: Number,  default: 7 },
  endHour:    { type: Number,  default: 21 },
})

const windowHours = computed(() => Math.max(1, props.endHour - props.startHour))
const hourTicks = computed(() => {
  const arr = []
  for (let h = props.startHour; h <= props.endHour; h++) arr.push(h)
  return arr
})
const hourLabels = computed(() => {
  const arr = []
  const step = windowHours.value <= 8 ? 1 : 2
  for (let h = props.startHour; h <= props.endHour; h += step) arr.push(h)
  return arr
})

const VW = 960
const VH = 280
const PL = 110
const PR = 16
const PT = 16
const PB = 22

const rootEl   = ref(null)
const hovEvent = ref(null)
const mouseX   = ref(0)
const mouseY   = ref(0)

const TYPE_COLORS = {
  page_view:      '#9E9E9E',
  partner_open:   '#2E7D32',
  partner_close:  '#A5D6A7',
  contact_create: '#1565C0',
  task_create:    '#6A1B9A',
  task_complete:  '#4527A0',
  note_create:    '#EF6C00',
  status_change:  '#00838F',
  call_log:       '#C62828',
  heartbeat:      '#CFD8DC',
  login:          '#43A047',
  logout:         '#E53935',
  other:          '#757575',
}

const TYPE_LABELS = {
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

function colorOf (t) { return TYPE_COLORS[t] || '#757575' }
function typeLabel (t) { return TYPE_LABELS[t] || t }

const usedTypes = computed(() => {
  const winStart = props.startHour * 60
  const winEnd   = props.endHour   * 60
  const set = new Set()
  for (const e of props.events) {
    const m = getServerMinutes(e.created_at)
    if (m !== null && m >= winStart && m <= winEnd) set.add(e.event_type)
  }
  return Object.keys(TYPE_COLORS).filter(t => set.has(t))
})

function laneY (i) {
  const n = Math.max(1, usedTypes.value.length)
  const h = VH - PT - PB
  return PT + (h * (i + 0.5)) / n
}

function hourX (h) {
  const ratio = (h - props.startHour) / windowHours.value
  return PL + ratio * (VW - PL - PR)
}

function eventX (e) {
  const minute = getServerMinutes(e.created_at) ?? 0
  const offset = minute - props.startHour * 60
  const total  = windowHours.value * 60
  const ratio  = Math.max(0, Math.min(1, offset / total))
  return PL + ratio * (VW - PL - PR)
}

const laidOutEvents = computed(() => {
  const typeIdx = new Map(usedTypes.value.map((t, i) => [t, i]))
  const winStart = props.startHour * 60
  const winEnd   = props.endHour   * 60
  return props.events
    .filter(e => {
      const m = getServerMinutes(e.created_at)
      return m !== null && m >= winStart && m <= winEnd
    })
    .map(e => ({
      ...e,
      x: eventX(e),
      y: laneY(typeIdx.get(e.event_type) ?? 0),
    }))
})

function onMove (e) {
  const r = e.currentTarget.getBoundingClientRect()
  mouseX.value = e.clientX - r.left
  mouseY.value = e.clientY - r.top
}

function formatTime (iso) {
  return formatServerDateTime(iso)
}

const tooltipStyle = computed(() => {
  let left = mouseX.value + 12
  if (left + 220 > (rootEl.value?.clientWidth || 9999)) {
    left = mouseX.value - 220 - 8
  }
  return `left:${Math.max(0, left)}px;top:${Math.max(0, mouseY.value - 10)}px`
})
</script>

<style scoped>
.activity-scatter {
  position: relative;
}
.empty {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #BDBDBD;
  font-size: 12px;
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 6px;
  padding-left: 4px;
  font-size: 11px;
  color: #616161;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}
.legend-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
}
.sc-tooltip {
  position: absolute;
  background: rgba(33, 33, 33, 0.92);
  color: #fff;
  border-radius: 6px;
  padding: 6px 10px;
  pointer-events: none;
  font-size: 11px;
  max-width: 240px;
  z-index: 5;
}
.sc-tooltip__time {
  font-weight: 700;
  margin-bottom: 3px;
  border-bottom: 1px solid rgba(255,255,255,0.15);
  padding-bottom: 3px;
}
.sc-tooltip__row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}
.sc-tooltip__dot {
  width: 8px; height: 8px;
  border-radius: 50%;
}
.sc-tooltip__path {
  margin-top: 3px;
  color: #BDBDBD;
  word-break: break-all;
}
</style>
