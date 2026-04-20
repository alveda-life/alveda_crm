<template>
  <q-page class="q-pa-lg operator-stats-page">

    <!-- Header row -->
    <div class="row items-center justify-between q-mb-lg">
      <div>
        <div class="text-h5 text-weight-bold text-dark">Operator Statistics</div>
        <div class="text-caption text-grey-6 q-mt-xs">Monitor operator activity and workload</div>
      </div>
      <div class="row items-center q-gutter-sm">
        <q-btn
          flat
          round
          icon="refresh"
          color="grey-6"
          size="sm"
          :loading="loading"
          @click="load"
        >
          <q-tooltip>Refresh</q-tooltip>
        </q-btn>
      </div>
    </div>

    <!-- Period tabs -->
    <q-tabs
      v-model="period"
      dense
      class="q-mb-lg"
      active-color="primary"
      indicator-color="primary"
      align="left"
    >
      <q-tab name="today" label="Today" />
      <q-tab name="week" label="Last 7 Days" />
      <q-tab name="month" label="Last 30 Days" />
      <q-tab name="all" label="All Time" />
    </q-tabs>

    <!-- Loading -->
    <div v-if="loading" class="row justify-center q-py-xl">
      <q-spinner-dots color="primary" size="40px" />
    </div>

    <!-- No operators -->
    <div v-else-if="!operators.length" class="text-center text-grey-5 q-py-xl">
      <q-icon name="people_outline" size="48px" class="q-mb-sm" />
      <div>No operators found</div>
    </div>

    <!-- Operator cards grid -->
    <div v-else class="operator-grid">
      <div
        v-for="op in operators"
        :key="op.id"
        class="operator-card"
        :class="{ 'operator-card--expanded': expandedIds.has(op.id) }"
      >
        <!-- Card header -->
        <div class="op-header row items-center q-gutter-sm q-mb-md">
          <q-avatar size="42px" color="primary" text-color="white" class="op-avatar">
            {{ initials(op.name) }}
          </q-avatar>
          <div style="flex:1; min-width:0;">
            <div class="text-weight-bold text-dark ellipsis">{{ op.name }}</div>
            <div class="text-caption text-grey-5">@{{ op.username }}</div>
          </div>
          <div class="column items-end">
            <q-badge
              :color="activityColor(op)"
              :label="activityLabel(op)"
              style="font-size:11px;"
            />
            <div v-if="op.last_activity" class="text-caption text-grey-5 q-mt-xs">
              last: {{ fromNow(op.last_activity) }}
            </div>
            <div v-else class="text-caption text-grey-6 q-mt-xs">no activity</div>
          </div>
        </div>

        <!-- Main metrics row -->
        <div class="metrics-row q-mb-md">
          <div class="metric-box">
            <div class="metric-value text-primary">{{ op.total_calls }}</div>
            <div class="metric-label">Calls</div>
          </div>
          <div class="metric-box">
            <div class="metric-value text-orange-8">{{ op.missed_calls }}</div>
            <div class="metric-label">Missed</div>
          </div>
          <div class="metric-box">
            <div class="metric-value text-blue-7">{{ op.callbacks }}</div>
            <div class="metric-label">Callbacks</div>
          </div>
          <div class="metric-box">
            <div class="metric-value text-purple-7">{{ op.audio_uploads }}</div>
            <div class="metric-label">Audio</div>
          </div>
        </div>

        <!-- Partners summary -->
        <div class="partners-row q-mb-sm">
          <div class="partners-total">
            <q-icon name="people" size="16px" color="grey-6" class="q-mr-xs" />
            <span class="text-body2 text-dark text-weight-medium">{{ op.assigned_partners }}</span>
            <span class="text-caption text-grey-6 q-ml-xs">assigned</span>
          </div>
          <div class="row q-gutter-xs">
            <q-chip
              dense
              :color="op.active_partners > 0 ? 'green-1' : 'grey-2'"
              :text-color="op.active_partners > 0 ? 'green-9' : 'grey-6'"
              size="sm"
            >
              <q-icon name="trending_up" size="12px" class="q-mr-xs" />
              {{ op.active_partners }} active
            </q-chip>
            <q-chip
              dense
              :color="op.dead_partners > 0 ? 'red-1' : 'grey-2'"
              :text-color="op.dead_partners > 0 ? 'red-9' : 'grey-6'"
              size="sm"
            >
              <q-icon name="trending_down" size="12px" class="q-mr-xs" />
              {{ op.dead_partners }} dead
            </q-chip>
            <q-chip
              v-if="op.overdue_partners > 0"
              dense
              color="amber-2"
              text-color="amber-10"
              size="sm"
            >
              <q-icon name="schedule" size="12px" class="q-mr-xs" />
              {{ op.overdue_partners }} overdue
            </q-chip>
          </div>
        </div>

        <!-- Stage progress bar -->
        <div class="stage-bar q-mb-sm" v-if="op.assigned_partners > 0">
          <div
            v-for="seg in stageSegments(op)"
            :key="seg.key"
            :style="`width:${seg.pct}%; background:${seg.color};`"
            class="stage-segment"
          >
            <q-tooltip>{{ seg.label }}: {{ seg.count }}</q-tooltip>
          </div>
        </div>
        <div v-if="op.assigned_partners === 0" class="stage-bar-empty q-mb-sm" />

        <!-- Expand toggle -->
        <div class="row justify-end">
          <q-btn
            flat
            dense
            size="sm"
            :icon="expandedIds.has(op.id) ? 'expand_less' : 'expand_more'"
            :label="expandedIds.has(op.id) ? 'Less' : 'Stage details'"
            color="grey-6"
            @click="toggleExpand(op.id)"
          />
        </div>

        <!-- Stage breakdown (expandable) -->
        <q-slide-transition>
          <div v-if="expandedIds.has(op.id)" class="stage-breakdown q-mt-sm">
            <q-separator class="q-mb-sm" />
            <div
              v-for="(info, key) in STAGE_INFO"
              :key="key"
              class="row items-center justify-between stage-row"
            >
              <div class="row items-center q-gutter-xs">
                <div
                  :style="`width:10px; height:10px; border-radius:50%; background:${info.color}; flex-shrink:0;`"
                />
                <span class="text-caption text-grey-7">{{ info.label }}</span>
              </div>
              <div class="row items-center q-gutter-sm">
                <span class="text-caption text-weight-bold text-dark">
                  {{ op.partners_by_stage[key] || 0 }}
                </span>
                <q-linear-progress
                  :value="stageRatio(op, key)"
                  :color="info.qColor"
                  track-color="grey-3"
                  size="6px"
                  style="width: 80px;"
                  rounded
                />
              </div>
            </div>
          </div>
        </q-slide-transition>
      </div>
    </div>

    <!-- Summary footer -->
    <div v-if="operators.length" class="summary-bar q-mt-xl">
      <div class="summary-item">
        <span class="summary-value">{{ totals.total_calls }}</span>
        <span class="summary-label">total calls</span>
      </div>
      <div class="summary-sep" />
      <div class="summary-item">
        <span class="summary-value text-orange-8">{{ totals.missed_calls }}</span>
        <span class="summary-label">missed</span>
      </div>
      <div class="summary-sep" />
      <div class="summary-item">
        <span class="summary-value text-blue-7">{{ totals.callbacks }}</span>
        <span class="summary-label">callbacks</span>
      </div>
      <div class="summary-sep" />
      <div class="summary-item">
        <span class="summary-value text-purple-7">{{ totals.audio_uploads }}</span>
        <span class="summary-label">audio files</span>
      </div>
      <div class="summary-sep" />
      <div class="summary-item">
        <span class="summary-value">{{ totals.assigned_partners }}</span>
        <span class="summary-label">total assigned</span>
      </div>
      <div class="summary-sep" />
      <div class="summary-item">
        <span class="summary-value text-amber-8">{{ totals.overdue_partners }}</span>
        <span class="summary-label">overdue</span>
      </div>
    </div>

  </q-page>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { usePartnersStore } from 'src/stores/partners'

const store = usePartnersStore()

const STAGE_INFO = {
  new:          { label: 'New',               color: '#F44336', qColor: 'red' },
  trained:      { label: 'Agreed to Create First Set', color: '#FFB300', qColor: 'amber' },
  set_created:  { label: 'Set Created',       color: '#29B6F6', qColor: 'light-blue' },
  has_sale:     { label: 'Has Sale',          color: '#43A047', qColor: 'green' },
  no_answer:    { label: 'Dead (No Answer)',  color: '#546E7A', qColor: 'blue-grey' },
  declined:     { label: 'Dead (Declined)',   color: '#B71C1C', qColor: 'deep-red' },
  no_sales:     { label: 'Dead (No Sales)',   color: '#E65100', qColor: 'deep-orange' },
}

const period = ref('week')
const operators = ref([])
const loading = ref(false)
const expandedIds = ref(new Set())

async function load() {
  loading.value = true
  try {
    operators.value = await store.fetchOperatorStats(period.value)
  } finally {
    loading.value = false
  }
}

watch(period, load, { immediate: true })

function initials(name) {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

function fromNow(iso) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function activityColor(op) {
  const total = op.total_calls + op.missed_calls + op.callbacks
  if (total === 0) return 'grey-5'
  if (total >= 5) return 'green-7'
  if (total >= 2) return 'amber-7'
  return 'orange-7'
}

function activityLabel(op) {
  const total = op.total_calls + op.missed_calls + op.callbacks
  if (total === 0) return 'idle'
  if (total >= 5) return 'active'
  if (total >= 2) return 'low'
  return 'minimal'
}

function stageSegments(op) {
  const total = op.assigned_partners
  if (!total) return []
  return Object.entries(STAGE_INFO).map(([key, info]) => ({
    key,
    label: info.label,
    color: info.color,
    count: op.partners_by_stage[key] || 0,
    pct: ((op.partners_by_stage[key] || 0) / total) * 100,
  })).filter(s => s.pct > 0)
}

function stageRatio(op, key) {
  if (!op.assigned_partners) return 0
  return (op.partners_by_stage[key] || 0) / op.assigned_partners
}

function toggleExpand(id) {
  const s = new Set(expandedIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  expandedIds.value = s
}

const totals = computed(() => ({
  total_calls: operators.value.reduce((s, o) => s + o.total_calls, 0),
  missed_calls: operators.value.reduce((s, o) => s + o.missed_calls, 0),
  callbacks: operators.value.reduce((s, o) => s + o.callbacks, 0),
  audio_uploads: operators.value.reduce((s, o) => s + o.audio_uploads, 0),
  assigned_partners: operators.value.reduce((s, o) => s + o.assigned_partners, 0),
  overdue_partners: operators.value.reduce((s, o) => s + o.overdue_partners, 0),
}))
</script>

<style scoped>
.operator-stats-page {
  max-width: 1100px;
}

.operator-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.operator-card {
  background: #fff;
  border: 1px solid #E0E0E0;
  border-radius: 12px;
  padding: 20px;
  transition: box-shadow 0.2s;
}

.operator-card:hover {
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.metric-box {
  background: #F5F5F5;
  border-radius: 8px;
  padding: 10px 6px;
  text-align: center;
}

.metric-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.1;
}

.metric-label {
  font-size: 11px;
  color: #9E9E9E;
  margin-top: 2px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.partners-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
}

.partners-total {
  display: flex;
  align-items: center;
}

.stage-bar {
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  background: #EEE;
}

.stage-bar-empty {
  height: 6px;
  border-radius: 3px;
  background: #EEE;
}

.stage-segment {
  transition: width 0.3s;
}

.stage-breakdown {
  padding-top: 4px;
}

.stage-row {
  padding: 4px 0;
}

/* Summary footer */
.summary-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0;
  background: #fff;
  border: 1px solid #E0E0E0;
  border-radius: 12px;
  padding: 16px 24px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 20px;
}

.summary-value {
  font-size: 22px;
  font-weight: 700;
  color: #212121;
}

.summary-label {
  font-size: 11px;
  color: #9E9E9E;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 2px;
}

.summary-sep {
  width: 1px;
  height: 36px;
  background: #E0E0E0;
}
</style>
