<template>
  <div class="donut-wrap">
    <!-- Empty state -->
    <div v-if="!slices.length" class="donut-empty">
      <svg :width="size" :height="size" :viewBox="`${-size/2} ${-size/2} ${size} ${size}`">
        <circle cx="0" cy="0" :r="outerR" fill="none" stroke="#EEEEEE" :stroke-width="thickness" />
      </svg>
      <div class="donut-no-data">No data</div>
    </div>

    <template v-else>
      <div class="donut-inner">
        <!-- SVG ring -->
        <svg :width="size" :height="size" :viewBox="`${-size/2} ${-size/2} ${size} ${size}`" style="flex-shrink:0">
          <path
            v-for="(s, i) in slices"
            :key="i"
            :d="s.d"
            :fill="s.color"
            :opacity="hovIdx === null ? 1 : hovIdx === i ? 1 : 0.35"
            style="transition:opacity 0.15s;cursor:pointer"
            @mouseenter="hovIdx = i"
            @mouseleave="hovIdx = null"
          />
          <!-- Center text -->
          <text x="0" y="-6" text-anchor="middle" :font-size="centerFontSize" font-weight="700" fill="#212121">
            {{ total }}
          </text>
          <text x="0" y="10" text-anchor="middle" font-size="9" fill="#9E9E9E">
            {{ centerLabel }}
          </text>
        </svg>

        <!-- Legend — shows ALL items including 0-count ones -->
        <div class="donut-legend">
          <div
            v-for="(item, i) in legendItems"
            :key="i"
            class="donut-legend-item"
            :style="[
              item.value === 0 ? 'opacity:0.4' : '',
              hovIdx === item.sliceIdx ? 'opacity:1' : hovIdx !== null && item.sliceIdx !== null ? 'opacity:0.45' : '',
              'transition:opacity 0.15s'
            ]"
            @mouseenter="item.sliceIdx !== null && (hovIdx = item.sliceIdx)"
            @mouseleave="hovIdx = null"
          >
            <div class="donut-dot" :style="`background:${item.color}`" />
            <span class="donut-lbl">{{ item.label }}</span>
            <span class="donut-val">{{ item.value }}</span>
            <span class="donut-pct">{{ item.value > 0 ? item.pct + '%' : '—' }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  items:       { type: Array,  default: () => [] },  // [{label, value, color}]
  size:        { type: Number, default: 160 },
  thickness:   { type: Number, default: 30 },
  centerLabel: { type: String, default: 'Total' },
})

const hovIdx = ref(null)

const outerR = computed(() => props.size / 2 - 4)
const innerR = computed(() => outerR.value - props.thickness)

const centerFontSize = computed(() => {
  const t = total.value
  if (t >= 10000) return 14
  if (t >= 1000)  return 17
  return 20
})

function polar(deg, r) {
  const rad = (deg - 90) * Math.PI / 180
  return { x: +(r * Math.cos(rad)).toFixed(3), y: +(r * Math.sin(rad)).toFixed(3) }
}

function arcPath(startDeg, endDeg, outerR, innerR) {
  if (endDeg - startDeg >= 360) endDeg = startDeg + 359.99
  const s = polar(startDeg, outerR), e = polar(endDeg, outerR)
  const si = polar(startDeg, innerR), ei = polar(endDeg, innerR)
  const large = (endDeg - startDeg) > 180 ? 1 : 0
  return `M ${s.x} ${s.y} A ${outerR} ${outerR} 0 ${large} 1 ${e.x} ${e.y} L ${ei.x} ${ei.y} A ${innerR} ${innerR} 0 ${large} 0 ${si.x} ${si.y} Z`
}

const total = computed(() => props.items.reduce((s, i) => s + (i.value || 0), 0))

const slices = computed(() => {
  const active = props.items.filter(i => i.value > 0)
  if (!active.length || !total.value) return []
  const t = total.value
  let startDeg = 0
  return active.map(item => {
    const pct = Math.round(item.value / t * 100)
    const sweep = (item.value / t) * 360
    const endDeg = startDeg + sweep
    const d = arcPath(startDeg, endDeg, outerR.value, innerR.value)
    startDeg = endDeg
    return { label: item.label, value: item.value, color: item.color, pct, d }
  })
})

// Legend includes ALL items; maps each to its slice index (or null if 0-count)
const legendItems = computed(() => {
  const t = total.value || 1
  let sliceIdx = 0
  return props.items.map(item => {
    const pct = Math.round(item.value / t * 100)
    const idx = item.value > 0 ? sliceIdx++ : null
    return { ...item, pct, sliceIdx: idx }
  })
})
</script>

<style scoped>
.donut-wrap {
  display: flex;
  align-items: center;
}
.donut-empty {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}
.donut-no-data {
  position: absolute;
  font-size: 11px;
  color: #BDBDBD;
  text-align: center;
}
.donut-inner {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
}
.donut-legend {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.donut-legend-item {
  display: flex;
  align-items: center;
  gap: 7px;
  cursor: default;
}
.donut-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}
.donut-lbl {
  flex: 1;
  font-size: 11px;
  color: #424242;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.donut-val {
  font-size: 11px;
  font-weight: 700;
  color: #212121;
  flex-shrink: 0;
}
.donut-pct {
  font-size: 10px;
  color: #9E9E9E;
  flex-shrink: 0;
  min-width: 30px;
  text-align: right;
}
</style>
