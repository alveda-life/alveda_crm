<template>
  <div style="position:relative" ref="rootEl">
    <div v-if="showLegend && series.length > 1" class="row q-gutter-lg q-mb-sm q-pl-xs">
      <div v-for="s in series" :key="s.key" class="row items-center" style="gap:6px">
        <div :style="`width:12px;height:12px;border-radius:3px;background:${s.color}`" />
        <span style="font-size:11px;color:#9E9E9E">{{ s.label }}</span>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="isEmpty" style="height:160px;display:flex;align-items:center;justify-content:center;color:#BDBDBD;font-size:12px;flex-direction:column;gap:6px">
      <q-icon name="bar_chart" size="28px" color="grey-3" />
      No data for this period
    </div>

    <svg v-else
      :viewBox="`0 0 ${VW} ${VH}`" width="100%"
      style="display:block;overflow:visible"
      @mouseleave="onMouseLeave"
      ref="svgEl"
    >
      <!-- Grid -->
      <line v-for="yv in gridYs" :key="`gy${yv}`"
        :x1="PL" :x2="VW - PR" :y1="yPx(yv)" :y2="yPx(yv)"
        stroke="#EEEEEE" stroke-width="1"
      />
      <text v-for="yv in gridYs" :key="`gyt${yv}`"
        :x="PL - 5" :y="yPx(yv) + 4"
        text-anchor="end" font-size="9" fill="#BDBDBD"
      >{{ yv }}</text>

      <!-- Hover column highlight -->
      <rect
        v-if="hovIdx !== null"
        :x="PL + hovIdx * gw" :y="PT"
        :width="gw" :height="VH - PT - PB"
        fill="#F5F5F5"
        rx="2"
        pointer-events="none"
      />

      <!-- Bars -->
      <g v-for="(d, di) in data" :key="di">
        <rect
          v-for="(s, si) in series" :key="si"
          :x="barX(di, si)"
          :y="yPx(Number(d[s.key]) || 0)"
          :width="bw"
          :height="Math.max(0, yPx(0) - yPx(Number(d[s.key]) || 0))"
          :fill="s.color"
          :opacity="hovIdx !== null && hovIdx !== di ? 0.45 : 1"
          rx="2"
          style="transition:opacity 0.15s"
          pointer-events="none"
        />
      </g>

      <!-- X labels -->
      <text v-for="item in xItems" :key="`xl${item.i}`"
        :x="groupCX(item.i)" :y="VH - 5"
        text-anchor="middle" font-size="9" fill="#BDBDBD"
        pointer-events="none"
      >{{ item.label }}</text>

      <!-- Transparent hit areas -->
      <rect
        v-for="(d, i) in data" :key="`hit${i}`"
        :x="PL + i * gw" :y="PT"
        :width="gw" :height="VH - PT - PB"
        fill="transparent"
        style="cursor:crosshair"
        @mouseenter="(e) => onGroupEnter(e, i)"
        @mousemove="onMouseMove"
      />
    </svg>

    <!-- Tooltip -->
    <div
      v-if="hovIdx !== null"
      class="bc-tooltip"
      :style="tooltipStyle"
    >
      <div class="bc-tooltip__label">{{ data[hovIdx][labelKey] }}</div>
      <div v-for="s in series" :key="s.key" class="bc-tooltip__row">
        <span class="bc-tooltip__dot" :style="`background:${s.color}`" />
        <span class="bc-tooltip__name">{{ s.label }}</span>
        <span class="bc-tooltip__val">{{ data[hovIdx][s.key] ?? 0 }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  data:       { type: Array,   default: () => [] },
  series:     { type: Array,   default: () => [] },
  labelKey:   { type: String,  default: 'label' },
  showLegend: { type: Boolean, default: true },
})

const VW = 560, VH = 160
const PL = 36, PR = 14, PT = 12, PB = 28

const rootEl  = ref(null)
const svgEl   = ref(null)
const hovIdx  = ref(null)
const mouseX  = ref(0)
const mouseY  = ref(0)

const isEmpty = computed(() => {
  const vals = props.series.flatMap(s => props.data.map(d => Number(d[s.key]) || 0))
  return vals.every(v => v === 0)
})

const niceMax = computed(() => {
  const vals = props.series.flatMap(s => props.data.map(d => Number(d[s.key]) || 0))
  const mx = Math.max(...vals, 1)
  const STEPS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500]
  const step = STEPS.find(s => s >= mx / 4) || 500
  return Math.ceil(mx / step) * step
})

const gridYs = computed(() => {
  const m = niceMax.value
  const STEPS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500]
  const step = STEPS.find(s => s >= m / 4) || 500
  const lines = []
  for (let v = step; v <= m; v += step) lines.push(v)
  return lines.length ? lines : [m]
})

function yPx(v) {
  const h = VH - PT - PB
  const clamped = Math.min(Math.max(Number(v) || 0, 0), niceMax.value)
  return PT + h - (clamped / niceMax.value) * h
}

const gw = computed(() => (VW - PL - PR) / Math.max(props.data.length, 1))
const bw = computed(() => {
  const numSeries = Math.max(props.series.length, 1)
  return Math.max(2, (gw.value * 0.72) / numSeries - 1)
})

function barX(di, si) {
  const g = gw.value
  const b = bw.value
  const groupStart = PL + di * g + g * 0.14
  return groupStart + si * (b + 1.5)
}

function groupCX(i) {
  return PL + i * gw.value + gw.value / 2
}

const xItems = computed(() => {
  const n = props.data.length
  const step = Math.ceil(n / 10)
  return props.data.reduce((acc, d, i) => {
    if (i % step === 0 || i === n - 1) acc.push({ i, label: d[props.labelKey] })
    return acc
  }, [])
})

function onGroupEnter(e, i) {
  hovIdx.value = i
  const rect = e.currentTarget.closest('svg').getBoundingClientRect()
  mouseX.value = e.clientX - rect.left
  mouseY.value = e.clientY - rect.top
}

function onMouseMove(e) {
  const rect = e.currentTarget.closest('svg').getBoundingClientRect()
  mouseX.value = e.clientX - rect.left
  mouseY.value = e.clientY - rect.top
}

function onMouseLeave() {
  hovIdx.value = null
}

const tooltipStyle = computed(() => {
  if (!rootEl.value || hovIdx.value === null) return ''
  const svgRect = svgEl.value?.getBoundingClientRect()
  if (!svgRect) return ''

  const svgWidth = svgRect.width
  const cx = (PL + hovIdx.value * gw.value + gw.value / 2) / VW * svgWidth

  let left = cx + 10
  let top  = mouseY.value - 10

  if (left + 160 > svgWidth) left = cx - 170

  return `left:${left}px;top:${Math.max(0, top)}px`
})
</script>

<style scoped>
.bc-tooltip {
  position: absolute;
  background: rgba(33, 33, 33, 0.92);
  color: #fff;
  border-radius: 8px;
  padding: 8px 11px;
  pointer-events: none;
  min-width: 130px;
  max-width: 200px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.18);
  z-index: 10;
  font-size: 12px;
}
.bc-tooltip__label {
  font-weight: 700;
  margin-bottom: 5px;
  color: #E0E0E0;
  font-size: 11px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding-bottom: 4px;
}
.bc-tooltip__row {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 3px;
}
.bc-tooltip__dot {
  width: 8px; height: 8px;
  border-radius: 3px;
  flex-shrink: 0;
}
.bc-tooltip__name {
  flex: 1;
  color: #BDBDBD;
  font-size: 11px;
}
.bc-tooltip__val {
  font-weight: 700;
  color: #fff;
}
</style>
