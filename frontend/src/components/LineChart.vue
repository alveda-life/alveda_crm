<template>
  <div style="position:relative" ref="rootEl">
    <div v-if="showLegend && series.length > 1" class="row q-gutter-lg q-mb-sm q-pl-xs">
      <div v-for="s in series" :key="s.key" class="row items-center" style="gap:6px">
        <div :style="`width:18px;height:3px;border-radius:2px;background:${s.color}`" />
        <span style="font-size:11px;color:#9E9E9E">{{ s.label }}</span>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="isEmpty" style="height:180px;display:flex;align-items:center;justify-content:center;color:#BDBDBD;font-size:12px;flex-direction:column;gap:6px">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="#E0E0E0">
        <path d="M3.5 18.5l6-6 4 4 7-8" stroke="#BDBDBD" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      No data for this period
    </div>

    <svg v-else
      :viewBox="`0 0 ${VW} ${VH}`" width="100%"
      style="display:block;overflow:visible;cursor:crosshair"
      @mousemove="onMouseMove"
      @mouseleave="onMouseLeave"
      ref="svgEl"
    >
      <defs>
        <linearGradient v-for="s in series" :key="s.key" :id="`g${uid}_${s.key}`" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="s.color" stop-opacity="0.2" />
          <stop offset="100%" :stop-color="s.color" stop-opacity="0" />
        </linearGradient>
      </defs>

      <!-- Horizontal grid lines -->
      <line v-for="yv in gridYs" :key="`gy${yv}`"
        :x1="PL" :x2="VW - PR" :y1="yPx(yv)" :y2="yPx(yv)"
        stroke="#EEEEEE" stroke-width="1"
      />
      <text v-for="yv in gridYs" :key="`gyt${yv}`"
        :x="PL - 5" :y="yPx(yv) + 4"
        text-anchor="end" font-size="9" fill="#BDBDBD"
      >{{ yv }}</text>

      <!-- Area fills -->
      <path v-for="s in series" :key="`area${s.key}`"
        :d="areaPath(s.key)" :fill="`url(#g${uid}_${s.key})`"
        pointer-events="none"
      />

      <!-- Lines -->
      <path v-for="s in series" :key="`line${s.key}`"
        :d="linePath(s.key)" :stroke="s.color"
        stroke-width="2.5" fill="none"
        stroke-linecap="round" stroke-linejoin="round"
        pointer-events="none"
      />

      <!-- Dots -->
      <g v-for="s in series" :key="`dots${s.key}`" pointer-events="none">
        <circle
          v-for="(pt, i) in pts(s.key)" :key="i"
          :cx="pt.x" :cy="pt.y"
          :r="hovIdx === i ? 5 : 3.5"
          :fill="s.color" stroke="#fff"
          :stroke-width="hovIdx === i ? 2 : 1.5"
          style="transition:r 0.1s"
        />
      </g>

      <!-- Hover crosshair -->
      <line v-if="hovIdx !== null"
        :x1="xPx(hovIdx)" :x2="xPx(hovIdx)"
        :y1="PT" :y2="VH - PB"
        stroke="#BDBDBD" stroke-width="1" stroke-dasharray="3 3"
        pointer-events="none"
      />

      <!-- X-axis labels -->
      <text v-for="item in xItems" :key="`xl${item.i}`"
        :x="xPx(item.i)" :y="VH - 5"
        text-anchor="middle" font-size="9" fill="#BDBDBD"
        pointer-events="none"
      >{{ item.label }}</text>

      <!-- Transparent hit areas (one per data point) -->
      <rect
        v-for="(d, i) in data" :key="`hit${i}`"
        :x="hitX(i)" :y="PT"
        :width="hitW" :height="VH - PT - PB"
        fill="transparent"
        @mouseenter="hovIdx = i"
      />
    </svg>

    <!-- Tooltip -->
    <div
      v-if="hovIdx !== null"
      class="lc-tooltip"
      :style="tooltipStyle"
    >
      <div class="lc-tooltip__label">{{ data[hovIdx][labelKey] }}</div>
      <div v-for="s in series" :key="s.key" class="lc-tooltip__row">
        <span class="lc-tooltip__dot" :style="`background:${s.color}`" />
        <span class="lc-tooltip__name">{{ s.label }}</span>
        <span class="lc-tooltip__val">{{ data[hovIdx][s.key] ?? 0 }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  data:       { type: Array,   default: () => [] },
  series:     { type: Array,   default: () => [] }, // [{key, label, color}]
  labelKey:   { type: String,  default: 'label' },
  showLegend: { type: Boolean, default: true },
})

const uid = Math.random().toString(36).slice(2, 8)
const VW = 560, VH = 180
const PL = 36, PR = 14, PT = 12, PB = 28

const rootEl = ref(null)
const svgEl  = ref(null)
const hovIdx = ref(null)
const mouseX = ref(0)
const mouseY = ref(0)

const isEmpty = computed(() => {
  const vals = props.series.flatMap(s => props.data.map(d => Number(d[s.key]) || 0))
  return vals.every(v => v === 0)
})

const niceMax = computed(() => {
  const vals = props.series.flatMap(s => props.data.map(d => Number(d[s.key]) || 0))
  const mx = Math.max(...vals, 1)
  const STEPS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000]
  const step = STEPS.find(s => s >= mx / 4) || 1000
  return Math.ceil(mx / step) * step
})

const gridYs = computed(() => {
  const m = niceMax.value
  const STEPS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000]
  const step = STEPS.find(s => s >= m / 4) || 1000
  const lines = []
  for (let v = step; v <= m; v += step) lines.push(v)
  return lines.length ? lines : [m]
})

function xPx(i) {
  const n = props.data.length
  if (n <= 1) return PL + (VW - PL - PR) / 2
  return PL + (i / (n - 1)) * (VW - PL - PR)
}

function yPx(v) {
  const h = VH - PT - PB
  const clamped = Math.min(Math.max(Number(v) || 0, 0), niceMax.value)
  return PT + h - (clamped / niceMax.value) * h
}

function pts(key) {
  return props.data.map((d, i) => ({
    x: xPx(i),
    y: yPx(Number(d[key]) || 0),
    v: Number(d[key]) || 0,
  }))
}

function linePath(key) {
  const p = pts(key)
  if (!p.length) return ''
  if (p.length === 1) return `M${p[0].x},${p[0].y}`
  let d = `M${p[0].x},${p[0].y}`
  for (let i = 1; i < p.length; i++) {
    const cp = (p[i - 1].x + p[i].x) / 2
    d += ` C${cp},${p[i - 1].y} ${cp},${p[i].y} ${p[i].x},${p[i].y}`
  }
  return d
}

function areaPath(key) {
  const p = pts(key)
  if (!p.length) return ''
  const base = yPx(0)
  if (p.length === 1) return `M${p[0].x},${base} L${p[0].x},${p[0].y} Z`
  let d = `M${p[0].x},${p[0].y}`
  for (let i = 1; i < p.length; i++) {
    const cp = (p[i - 1].x + p[i].x) / 2
    d += ` C${cp},${p[i - 1].y} ${cp},${p[i].y} ${p[i].x},${p[i].y}`
  }
  d += ` L${p[p.length - 1].x},${base} L${p[0].x},${base} Z`
  return d
}

const xItems = computed(() => {
  const n = props.data.length
  const maxShow = 10
  const step = Math.ceil(n / maxShow)
  return props.data.reduce((acc, d, i) => {
    if (i % step === 0 || i === n - 1) acc.push({ i, label: d[props.labelKey] })
    return acc
  }, [])
})

// Hit areas
const hitW = computed(() => {
  const n = props.data.length
  if (n <= 1) return VW - PL - PR
  return (VW - PL - PR) / (n - 1)
})
function hitX(i) {
  const n = props.data.length
  if (n <= 1) return PL
  const step = (VW - PL - PR) / (n - 1)
  return xPx(i) - step / 2
}

function onMouseMove(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  mouseX.value = e.clientX - rect.left
  mouseY.value = e.clientY - rect.top
}

function onMouseLeave() {
  hovIdx.value = null
}

const tooltipStyle = computed(() => {
  if (!rootEl.value || hovIdx.value === null) return ''
  const svgRect = svgEl.value?.getBoundingClientRect()
  const rootRect = rootEl.value.getBoundingClientRect()
  if (!svgRect || !rootRect) return ''

  const svgWidth = svgRect.width
  const relMouseX = mouseX.value
  const relMouseY = mouseY.value

  // x: follow dot x position in rendered pixels
  const n = props.data.length
  const dotXRatio = n <= 1 ? 0.5 : hovIdx.value / (n - 1)
  const dotPxX = PL / VW * svgWidth + dotXRatio * ((VW - PL - PR) / VW) * svgWidth

  let left = dotPxX + 12
  let top = relMouseY - 10

  // flip left if too close to right edge
  if (left + 160 > svgWidth) left = dotPxX - 160 - 8

  return `left:${left}px;top:${Math.max(0, top)}px`
})
</script>

<style scoped>
.lc-tooltip {
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
.lc-tooltip__label {
  font-weight: 700;
  margin-bottom: 5px;
  color: #E0E0E0;
  font-size: 11px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding-bottom: 4px;
}
.lc-tooltip__row {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 3px;
}
.lc-tooltip__dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.lc-tooltip__name {
  flex: 1;
  color: #BDBDBD;
  font-size: 11px;
}
.lc-tooltip__val {
  font-weight: 700;
  color: #fff;
}
</style>
