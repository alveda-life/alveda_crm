<template>
  <div class="activity-heatmap">
    <div v-if="!users.length || !days.length" class="empty">
      No data for this period
    </div>
    <div v-else>
      <div class="hm-hour-row">
        <span class="hm-name-spacer" />
        <div class="hm-hour-cells">
          <span v-for="h in hourLabels" :key="h"
                :style="`left:${((h - startHour) / windowHours) * 100}%`">{{ h }}h</span>
        </div>
      </div>

      <div v-for="user in users" :key="user.user_id" class="hm-user-block">
        <div class="hm-user-name">{{ user.full_name }}</div>
        <div class="hm-user-rows">
          <div v-for="day in days" :key="day" class="hm-row">
            <span class="hm-day">{{ formatDay(day) }}</span>
            <div class="hm-cells" @mouseleave="hovCell = null">
              <div
                v-for="cell in matrix[user.user_id]?.[day] || []"
                :key="cell.bucket_idx"
                class="hm-cell"
                :style="cellStyle(cell, day, user)"
                @mouseenter="hovCell = { ...cell, day, user_id: user.user_id, full_name: user.full_name }"
                @click="$emit('cell-click', { user_id: user.user_id, date: day, bucket_idx: cell.bucket_idx })"
              />
            </div>
          </div>
        </div>
      </div>

      <div v-if="hovCell" class="hm-tooltip">
        {{ hovCell.full_name }} · {{ formatDay(hovCell.day) }} ·
        {{ formatBucket(hovCell.bucket_idx) }} —
        {{ hovCell.count }} event{{ hovCell.count === 1 ? '' : 's' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { SERVER_TZ } from 'src/utils/serverTime'

const props = defineProps({
  users:         { type: Array,  default: () => [] }, // [{user_id, full_name, ...}]
  cells:         { type: Array,  default: () => [] }, // [{user_id, date, bucket_idx, count}]
  bucketMinutes: { type: Number, default: 30 },
  dateFrom:      { type: String, default: null },
  dateTo:        { type: String, default: null },
  startHour:     { type: Number, default: 7 },
  endHour:       { type: Number, default: 21 },
})

const windowHours = computed(() => Math.max(1, props.endHour - props.startHour))
const hourLabels = computed(() => {
  const arr = []
  const step = windowHours.value <= 8 ? 1 : 2
  for (let h = props.startHour; h <= props.endHour; h += step) arr.push(h)
  return arr
})

defineEmits(['cell-click'])

const hovCell = ref(null)

const days = computed(() => {
  if (!props.dateFrom || !props.dateTo) return []
  // Anchor at noon UTC so adding 24h never crosses a DST cusp; we then
  // format back to YYYY-MM-DD via UTC parts (date-only, TZ-irrelevant).
  const out = []
  const start = new Date(`${props.dateFrom}T12:00:00Z`).getTime()
  const end   = new Date(`${props.dateTo}T12:00:00Z`).getTime()
  for (let t = start; t <= end; t += 86_400_000) {
    out.push(new Date(t).toISOString().slice(0, 10))
  }
  return out
})

const matrix = computed(() => {
  /** matrix[user_id][date] = [{bucket_idx, count}, ...] */
  const m = {}
  let max = 1
  const winStart = props.startHour * 60
  const winEnd   = props.endHour   * 60
  for (const c of props.cells) {
    const startMin = c.bucket_idx * props.bucketMinutes
    if (startMin + props.bucketMinutes <= winStart) continue
    if (startMin >= winEnd) continue
    if (!m[c.user_id]) m[c.user_id] = {}
    if (!m[c.user_id][c.date]) m[c.user_id][c.date] = []
    m[c.user_id][c.date].push(c)
    if (c.count > max) max = c.count
  }
  for (const uid of Object.keys(m)) {
    for (const d of Object.keys(m[uid])) {
      m[uid][d] = m[uid][d].map(c => ({ ...c, _max: max }))
      m[uid][d].sort((a, b) => a.bucket_idx - b.bucket_idx)
    }
  }
  return m
})

function cellStyle (cell) {
  const ratio = Math.min(1, cell.count / Math.max(3, cell._max))
  const lightness = 75 - 35 * ratio  // 75% → 40%
  const winMinutes = windowHours.value * 60
  const startMin   = cell.bucket_idx * props.bucketMinutes
  const offset     = startMin - props.startHour * 60
  const widthPct   = (props.bucketMinutes / winMinutes) * 100
  const leftPct    = (offset / winMinutes) * 100
  return `left:${leftPct}%;width:${widthPct}%;background:hsl(122, 55%, ${lightness}%)`
}

function formatDay (iso) {
  // Anchor noon IST so the date doesn't drift across DST boundaries.
  const d = new Date(`${iso}T12:00:00+05:30`)
  return new Intl.DateTimeFormat(undefined, {
    timeZone: SERVER_TZ,
    month:    'short',
    day:      'numeric',
    weekday:  'short',
  }).format(d)
}

function formatBucket (idx) {
  const startMin = idx * props.bucketMinutes
  const endMin   = startMin + props.bucketMinutes
  const fmt = m => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
  return `${fmt(startMin)}–${fmt(endMin)}`
}
</script>

<style scoped>
.activity-heatmap {
  position: relative;
  font-size: 12px;
}
.empty {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #BDBDBD;
  font-size: 12px;
}
.hm-hour-row {
  display: flex;
  margin-bottom: 4px;
}
.hm-name-spacer {
  width: 160px;
  flex-shrink: 0;
}
.hm-hour-cells {
  position: relative;
  flex: 1;
  height: 12px;
  font-size: 10px;
  color: #9E9E9E;
  margin-left: 64px;
}
.hm-hour-cells span {
  position: absolute;
  transform: translateX(-50%);
}
.hm-user-block {
  display: flex;
  align-items: stretch;
  margin-bottom: 6px;
  border-bottom: 1px solid #F5F5F5;
  padding-bottom: 4px;
}
.hm-user-name {
  width: 160px;
  flex-shrink: 0;
  font-weight: 600;
  font-size: 12px;
  color: #424242;
  padding-right: 8px;
  align-self: center;
}
.hm-user-rows {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.hm-row {
  display: flex;
  align-items: center;
}
.hm-day {
  width: 64px;
  font-size: 10px;
  color: #9E9E9E;
  flex-shrink: 0;
}
.hm-cells {
  position: relative;
  flex: 1;
  height: 14px;
  background: #F5F5F5;
  border-radius: 2px;
  overflow: hidden;
}
.hm-cell {
  position: absolute;
  top: 0;
  bottom: 0;
  cursor: pointer;
  transition: filter 0.1s;
}
.hm-cell:hover {
  filter: brightness(1.15);
}
.hm-tooltip {
  position: sticky;
  bottom: 8px;
  margin-top: 12px;
  background: rgba(33, 33, 33, 0.92);
  color: #fff;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 11px;
  width: fit-content;
}
</style>
