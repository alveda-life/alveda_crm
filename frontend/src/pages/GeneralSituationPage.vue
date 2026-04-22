<template>
  <q-page class="gs-page">
    <AiAutoGenBanner job-id="brand_situation_weekly" class="gs-banner" />

    <!-- ── Header ── -->
    <div class="gs-header">
      <div>
        <div class="gs-title">General Situation</div>
        <div class="gs-subtitle">
          Weekly snapshot of every active brand • auto-generated every Friday 15:00 IST
        </div>
      </div>

      <div class="gs-actions">
        <q-select
          v-model="selectedReportId"
          :options="reportOptions"
          dense outlined emit-value map-options
          label="Week"
          style="min-width: 240px"
        />
        <q-btn
          v-if="authStore.isAdmin"
          color="primary"
          icon="auto_awesome"
          label="Regenerate now"
          unelevated
          :loading="generating"
          @click="regenerate"
        />
      </div>
    </div>

    <!-- ── Status banner ── -->
    <q-banner
      v-if="currentReport && currentReport.status !== 'done'"
      class="gs-banner bg-orange-1 text-orange-9"
      rounded
    >
      <template #avatar>
        <q-spinner v-if="['pending','generating'].includes(currentReport.status)" color="orange" />
        <q-icon v-else name="error" color="negative" />
      </template>
      <span v-if="currentReport.status === 'pending'">Report queued — generation will start shortly.</span>
      <span v-else-if="currentReport.status === 'generating'">Generating snapshot — this can take a few minutes.</span>
      <span v-else>Generation failed: {{ currentReport.error_message || 'unknown error' }} (will auto-retry)</span>
    </q-banner>

    <!-- ── Loading ── -->
    <div v-if="loading && !currentReport" class="gs-empty">
      <q-spinner color="primary" size="40px" />
      <div class="q-mt-md">Loading…</div>
    </div>

    <!-- ── Empty ── -->
    <div v-else-if="!currentReport" class="gs-empty">
      <q-icon name="inbox" size="64px" color="grey-5" />
      <div class="q-mt-md text-grey-7">No reports yet</div>
      <q-btn
        v-if="authStore.isAdmin"
        class="q-mt-md"
        color="primary"
        icon="auto_awesome"
        label="Generate first report"
        unelevated
        :loading="generating"
        @click="regenerate"
      />
    </div>

    <!-- ── Brand list ── -->
    <div v-else class="gs-brands">
      <!-- Filter / group by stage -->
      <div class="gs-filters">
        <q-btn-toggle
          v-model="stageFilter"
          dense unelevated
          :options="stageOptions"
          color="grey-3"
          text-color="grey-9"
          toggle-color="primary"
          toggle-text-color="white"
        />
        <div class="gs-legend">
          <span class="gs-legend-dot gs-legend-dot--green" /> Real progress
          <span class="gs-legend-dot gs-legend-dot--red q-ml-md" /> No update — on us
          <span class="gs-legend-dot gs-legend-dot--orange q-ml-md" /> Blocked by partner
        </div>
      </div>

      <div
        v-for="brand in filteredBrands"
        :key="brand.id"
        class="gs-brand-card"
      >
        <!-- Brand header row -->
        <div class="gs-brand-head">
          <a
            class="gs-brand-name gs-brand-name--link"
            :href="`/producers/${brand.id}`"
            @click.prevent="openProducer(brand.id)"
            :title="`Open ${brand.name} card`"
          >
            {{ brand.name }}
            <q-icon name="open_in_new" size="14px" class="gs-brand-name-icon" />
          </a>
          <div class="gs-brand-meta">
            <div class="gs-readiness" v-if="brand.readiness_percent != null">
              <div class="gs-readiness-bar">
                <div
                  class="gs-readiness-fill"
                  :style="{ width: brand.readiness_percent + '%', background: readinessColor(brand.readiness_percent) }"
                />
              </div>
              <span class="gs-readiness-num">{{ brand.readiness_percent }}%</span>
            </div>
            <q-chip
              dense
              :color="stageColor(brand.stage_key)"
              text-color="white"
              class="gs-brand-stage"
            >
              {{ brand.stage }}
            </q-chip>
          </div>
        </div>

        <!-- Timeline -->
        <div class="gs-timeline">
          <div
            v-for="(w, i) in brand.timeline"
            :key="w.week"
            class="gs-week"
          >
            <q-tooltip max-width="440px" anchor="top middle" self="bottom middle" class="gs-tooltip">
              <div class="gs-tooltip-title">
                Week of {{ formatWeek(w.week) }}
                <span class="gs-tooltip-tag" :class="`gs-tooltip-tag--${w.kind}`">
                  {{ kindLabel(w.kind) }}
                </span>
              </div>
              <div class="gs-tooltip-body">{{ w.summary || kindLabel(w.kind) }}</div>
            </q-tooltip>

            <div
              class="gs-dot"
              :class="[
                `gs-dot--${w.kind}`,
                { 'gs-dot--current': i === brand.timeline.length - 1 },
              ]"
            />
            <div
              v-if="i < brand.timeline.length - 1"
              class="gs-line"
              :class="`gs-line--${w.kind}`"
            />
          </div>
        </div>

        <!-- Current status -->
        <div class="gs-current">
          <span class="gs-current-label">Now:</span>
          <span class="gs-current-text">{{ brand.current_status || '—' }}</span>
        </div>
      </div>
    </div>
  </q-page>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from 'boot/axios'
import { useQuasar } from 'quasar'
import { useAuthStore } from 'stores/auth'
import AiAutoGenBanner from 'components/AiAutoGenBanner.vue'

const $q = useQuasar()
const authStore = useAuthStore()
const router = useRouter()

function openProducer (id) {
  router.push(`/producers/${id}`)
}

const reports = ref([])
const selectedReportId = ref(null)
const loading = ref(false)
const generating = ref(false)
const stageFilter = ref('all')

let pollTimer = null

const stageOptions = [
  { label: 'All',          value: 'all' },
  { label: 'In Comm',      value: 'in_communication' },
  { label: 'Negotiation',  value: 'terms_negotiation' },
  { label: 'Signing',      value: 'negotiation' },
  { label: 'Contract',     value: 'contract_signed' },
]

const reportOptions = computed(() =>
  reports.value.map(r => ({
    label: `${formatWeek(r.week_start)} — ${formatWeek(r.week_end)}` +
           (r.status !== 'done' ? `  (${r.status})` : ''),
    value: r.id,
  })),
)

const currentReport = computed(() =>
  reports.value.find(r => r.id === selectedReportId.value) || null,
)

const STAGE_ORDER = {
  contract_signed:   0,
  negotiation:       1,
  terms_negotiation: 2,
  in_communication:  3,
}

const filteredBrands = computed(() => {
  const r = currentReport.value
  if (!r || !r.brand_data) return []
  const list = Object.entries(r.brand_data).map(([id, b]) => ({
    id,
    ...b,
    timeline: weeksToTimeline(b.weeks),
  }))
  const filtered = stageFilter.value === 'all'
    ? list
    : list.filter(b => b.stage_key === stageFilter.value)
  filtered.sort((a, b) => {
    const sa = STAGE_ORDER[a.stage_key] ?? 99
    const sb = STAGE_ORDER[b.stage_key] ?? 99
    if (sa !== sb) return sa - sb
    const ra = Number(a.readiness_percent ?? 0)
    const rb = Number(b.readiness_percent ?? 0)
    if (rb !== ra) return rb - ra
    return a.name.localeCompare(b.name)
  })
  return filtered
})

function weeksToTimeline (weeks) {
  if (!weeks) return []
  const entries = Object.entries(weeks).sort(([a], [b]) => a.localeCompare(b))
  return entries.map(([week, info]) => {
    const changed = !!(info && info.changed)
    const side = info && info.wasted_side
    let kind = 'ours'
    if (changed) kind = 'green'
    else if (side === 'partner') kind = 'orange'
    else kind = 'red'
    return {
      week,
      kind,
      summary: (info && info.summary) || '',
    }
  })
}

function kindLabel (kind) {
  if (kind === 'green')  return 'PROGRESS'
  if (kind === 'orange') return 'BLOCKED BY PARTNER'
  if (kind === 'red')    return 'NO UPDATE — ON US'
  return ''
}

function formatWeek (iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function readinessColor (pct) {
  if (pct >= 90) return '#16a34a'
  if (pct >= 70) return '#4f46e5'
  if (pct >= 45) return '#a855f7'
  if (pct >= 25) return '#0ea5e9'
  return '#ef4444'
}

function stageColor (stage) {
  if (stage === 'on_platform')       return 'green-7'
  if (stage === 'contract_signed')   return 'indigo-6'
  if (stage === 'negotiation')       return 'deep-purple-5'
  if (stage === 'terms_negotiation') return 'deep-orange-6'
  if (stage === 'in_communication')  return 'blue-grey-6'
  return 'grey-7'
}

async function fetchReports () {
  loading.value = true
  try {
    const res = await api.get('/brand-situation/')
    const data = res.data
    reports.value = Array.isArray(data) ? data : (data?.results || [])
    if (reports.value.length && !selectedReportId.value) {
      selectedReportId.value = reports.value[0].id
    }
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Failed to load reports' })
  } finally {
    loading.value = false
  }
}

async function regenerate () {
  generating.value = true
  try {
    const res = await api.post('/brand-situation/generate/')
    $q.notify({ type: 'positive', message: 'Generation started — refreshing in a moment' })
    selectedReportId.value = res.data.id
    await fetchReports()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.error || 'Failed to start generation' })
  } finally {
    generating.value = false
  }
}

watch(currentReport, (r) => {
  if (r && r.status !== 'done' && !pollTimer) {
    pollTimer = setInterval(fetchReports, 8000)
  }
  if (r && r.status === 'done' && pollTimer) {
    clearInterval(pollTimer); pollTimer = null
  }
})

onMounted(fetchReports)
onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped lang="scss">
.gs-page {
  padding: 24px 32px;
  max-width: 1400px;
  margin: 0 auto;
}

.gs-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  margin-bottom: 24px;
}
.gs-title {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a1a;
}
.gs-subtitle {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}
.gs-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.gs-banner {
  margin-bottom: 16px;
}

.gs-empty {
  text-align: center;
  padding: 80px 0;
  color: #6b7280;
}

.gs-filters {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}
.gs-legend {
  font-size: 12px;
  color: #6b7280;
  display: flex;
  align-items: center;
}
.gs-legend-dot {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
  &--green  { background: #10b981; }
  &--red    { background: #ef4444; }
  &--orange { background: #f59e0b; }
  &--grey   { background: #d1d5db; }
}

.gs-brands {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.gs-brand-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px 20px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
.gs-brand-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.gs-brand-name {
  font-weight: 600;
  font-size: 15px;
  color: #1f2937;
}
.gs-brand-name--link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-decoration: none;
  cursor: pointer;
  border-bottom: 1px dashed transparent;
  transition: color .15s ease, border-color .15s ease;
}
.gs-brand-name--link:hover {
  color: #2563eb;
  border-bottom-color: #93c5fd;
}
.gs-brand-name-icon {
  opacity: 0;
  transition: opacity .15s ease;
}
.gs-brand-name--link:hover .gs-brand-name-icon {
  opacity: 0.7;
}
.gs-brand-stage {
  font-size: 11px;
  font-weight: 600;
}
.gs-brand-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}
.gs-readiness {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 160px;
}
.gs-readiness-bar {
  width: 110px;
  height: 6px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
}
.gs-readiness-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}
.gs-readiness-num {
  font-size: 12px;
  font-weight: 700;
  color: #374151;
  min-width: 40px;
  text-align: right;
}

.gs-timeline {
  display: flex;
  align-items: center;
  overflow-x: auto;
  padding: 4px 0;
}
.gs-week {
  display: flex;
  align-items: center;
  flex: 1 1 auto;
  min-width: 36px;
  position: relative;
}
.gs-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px #e5e7eb;
  cursor: pointer;
  transition: transform .15s ease;
  &:hover { transform: scale(1.4); }
  &--green  { background: #10b981; box-shadow: 0 0 0 1px #059669; }
  &--red    { background: #ef4444; box-shadow: 0 0 0 1px #dc2626; }
  &--orange { background: #f59e0b; box-shadow: 0 0 0 1px #d97706; }
  &--current { box-shadow: 0 0 0 2px #2563eb !important; }
}
.gs-line {
  flex: 1 1 auto;
  height: 2px;
  background: #e5e7eb;
  min-width: 24px;
  &--green  { background: #6ee7b7; }
  &--red    { background: #fca5a5; }
  &--orange { background: #fcd34d; }
}

.gs-tooltip-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 6px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  &--green  { background: #d1fae5; color: #065f46; }
  &--red    { background: #fee2e2; color: #991b1b; }
  &--orange { background: #fef3c7; color: #92400e; }
}

.gs-current {
  font-size: 13px;
  line-height: 1.55;
  background: #f9fafb;
  border-radius: 6px;
  padding: 12px 14px;
  border-left: 3px solid #2563eb;
}
.gs-current-label {
  font-weight: 600;
  color: #2563eb;
  margin-right: 6px;
}
.gs-current-text {
  color: #374151;
}

.gs-tooltip-title {
  font-weight: 600;
  font-size: 12px;
  margin-bottom: 4px;
}
.gs-tooltip-body {
  font-size: 12px;
  line-height: 1.4;
}
</style>
