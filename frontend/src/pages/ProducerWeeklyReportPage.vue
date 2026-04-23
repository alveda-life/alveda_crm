<template>
  <q-page class="q-pa-md">
    <div class="row items-start q-mb-md q-gutter-sm">
      <div class="col">
        <div class="text-h6 q-mb-xs row items-center">
          <q-icon name="event_note" class="q-mr-sm text-deep-orange-7" />
          Producer Weekly Report
        </div>
        <div class="text-caption text-grey-7">
          AI-generated snapshot of the onboarding funnel since the previous run.
          Trivial follow-ups (reminders, "called again", contact requests) are
          filtered out — only material changes are surfaced.
        </div>
      </div>
      <q-space />
    </div>

    <q-card flat bordered class="q-mb-md" style="border-radius:12px;">
      <q-card-section class="q-py-sm row items-center q-gutter-sm">
        <q-chip dense outline icon="event">
          {{ fmtDate(report?.period_from) }} → {{ fmtDate(report?.period_to) }}
        </q-chip>
        <q-chip dense outline icon="add" color="green-2" text-color="green-9">
          {{ report?.total_new_producers ?? 0 }} new
        </q-chip>
        <q-chip dense outline icon="trending_up" color="blue-2" text-color="blue-9">
          {{ report?.total_changed_producers ?? 0 }} significant changes
        </q-chip>
        <q-chip dense outline icon="forum" color="grey-3" text-color="grey-9">
          {{ report?.total_comments_considered ?? 0 }} comments analysed
        </q-chip>
        <q-chip dense outline :color="statusColor(report?.status)" :text-color="statusText(report?.status)">
          <q-spinner-dots
            v-if="report?.status === 'pending' || report?.status === 'processing'"
            size="10px" class="q-mr-xs"
          />
          {{ report?.status || '—' }}
        </q-chip>
        <q-chip v-if="report?.triggered_by" dense outline icon="schedule">
          {{ report.triggered_by === 'scheduled' ? 'Scheduled' : 'Manual' }}
        </q-chip>
        <q-space />
        <q-select
          v-if="history.length > 1"
          v-model="selectedId"
          :options="historyOptions"
          option-label="label" option-value="value"
          map-options emit-value
          dense outlined hide-bottom-space
          style="min-width: 280px"
          @update:model-value="loadById"
        />
        <span class="text-caption text-grey-6 q-ml-xs">
          Built {{ fmtRelative(report?.completed_at) }}
        </span>
      </q-card-section>
    </q-card>

    <div v-if="loading && !report" class="q-pa-xl text-center">
      <q-spinner-dots color="deep-orange-7" size="40px" />
      <div class="text-caption text-grey-7 q-mt-sm">Loading…</div>
    </div>

    <div v-else-if="report?.status === 'pending' || report?.status === 'processing'" class="q-pa-xl text-center">
      <q-spinner-dots color="deep-orange-7" size="40px" />
      <div class="text-caption text-grey-7 q-mt-sm">
        Building report — usually completes in &lt;1 min. Auto-refreshing…
      </div>
    </div>

    <div v-else-if="report?.status === 'failed'">
      <q-banner class="bg-red-1 text-red-9" rounded>
        <template #avatar><q-icon name="error" /></template>
        Generation failed: <code>{{ report?.last_error || 'unknown' }}</code>
        <template #action>
          <q-btn flat color="negative" no-caps label="Retry" @click="retry" />
        </template>
      </q-banner>
    </div>

    <div v-else-if="!report" class="q-pa-xl text-center text-grey-6">
      No reports yet — the first one will be generated automatically on Friday at 16:00 IST.
    </div>

    <template v-else>
      <q-card v-if="report.summary_text" flat bordered class="q-mb-md">
        <q-card-section class="q-py-sm">
          <div class="text-subtitle2 q-mb-xs">Executive summary</div>
          <div style="white-space:pre-wrap;">{{ report.summary_text }}</div>
        </q-card-section>
      </q-card>

      <div v-if="(report.new_producers_json || []).length" class="q-mb-lg">
        <div class="text-subtitle2 q-mb-sm row items-center">
          <q-icon name="add_business" class="q-mr-xs text-green-7" />
          New producers
          <q-chip dense color="green-2" text-color="green-9" class="q-ml-sm">
            {{ report.new_producers_json.length }}
          </q-chip>
        </div>
        <div
          v-for="card in report.new_producers_json"
          :key="`new-${card.producer_id}`"
          class="report-card report-card--new q-mb-sm"
        >
          <div class="row items-center no-wrap">
            <q-icon name="add_circle" size="20px" class="q-mr-sm text-green-7" />
            <div class="col">
              <div class="text-body1 text-weight-medium">{{ card.headline }}</div>
              <div class="text-caption text-grey-7">
                <router-link :to="`/producers/${card.producer_id}`" class="producer-link">
                  {{ card.producer_name || card.producer_company || `Producer #${card.producer_id}` }}
                </router-link>
                <span v-if="card.producer_company && card.producer_name !== card.producer_company">
                  · {{ card.producer_company }}
                </span>
                <span v-if="card.assigned_to"> · @{{ card.assigned_to }}</span>
              </div>
            </div>
            <q-chip
              dense outline
              :color="stageColor(card.stage_now)"
              :text-color="stageColor(card.stage_now)"
            >
              {{ stageLabel(card.stage_now) }}
            </q-chip>
          </div>
          <div v-if="card.detail" class="q-mt-xs text-body2" style="white-space:pre-wrap;">
            {{ card.detail }}
          </div>
        </div>
      </div>

      <div v-if="(report.changes_json || []).length" class="q-mb-lg">
        <div class="text-subtitle2 q-mb-sm row items-center">
          <q-icon name="auto_awesome" class="q-mr-xs text-blue-7" />
          Significant changes
          <q-chip dense color="blue-2" text-color="blue-9" class="q-ml-sm">
            {{ report.changes_json.length }}
          </q-chip>
        </div>
        <div
          v-for="card in report.changes_json"
          :key="`chg-${card.producer_id}`"
          class="report-card q-mb-sm"
          :style="{ borderLeftColor: kindColor(card.kind) }"
        >
          <div class="row items-center no-wrap">
            <q-icon :name="kindIcon(card.kind)" size="20px" class="q-mr-sm" :style="{ color: kindColor(card.kind) }" />
            <div class="col">
              <div class="text-body1 text-weight-medium">{{ card.headline }}</div>
              <div class="text-caption text-grey-7">
                <router-link :to="`/producers/${card.producer_id}`" class="producer-link">
                  {{ card.producer_name || card.producer_company || `Producer #${card.producer_id}` }}
                </router-link>
                <span v-if="card.producer_company && card.producer_name !== card.producer_company">
                  · {{ card.producer_company }}
                </span>
                <span v-if="card.assigned_to"> · @{{ card.assigned_to }}</span>
                · <q-badge :color="kindBadgeColor(card.kind)" outline class="q-mx-xs">{{ kindLabel(card.kind) }}</q-badge>
              </div>
            </div>
            <div v-if="card.stage_change && (card.stage_change.from || card.stage_change.to)" class="q-ml-md text-right">
              <div class="text-caption text-grey-7">stage</div>
              <div class="text-body2">
                <span v-if="card.stage_change.from">{{ stageLabel(card.stage_change.from) }}</span>
                <q-icon v-if="card.stage_change.from && card.stage_change.to" name="arrow_forward" size="14px" class="q-mx-xs" />
                <span v-if="card.stage_change.to" :style="{ color: stageColor(card.stage_change.to), fontWeight: 600 }">
                  {{ stageLabel(card.stage_change.to) }}
                </span>
              </div>
            </div>
            <q-chip
              v-else
              dense outline
              :color="stageColor(card.stage_now)"
              :text-color="stageColor(card.stage_now)"
              class="q-ml-md"
            >
              {{ stageLabel(card.stage_now) }}
            </q-chip>
          </div>
          <div v-if="card.detail" class="q-mt-xs text-body2" style="white-space:pre-wrap;">
            {{ card.detail }}
          </div>
        </div>
      </div>

      <div
        v-if="!report.new_producers_json?.length && !report.changes_json?.length"
        class="q-pa-xl text-center text-grey-6"
      >
        No significant changes in this period.
      </div>
    </template>
  </q-page>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useQuasar } from 'quasar'
import { api } from 'boot/axios'

const $q = useQuasar()

const loading = ref(false)
const report = ref(null)
const history = ref([])
const selectedId = ref(null)
let pollTimer = null

const historyOptions = computed(() =>
  history.value.map(r => ({
    value: r.id,
    label: `${fmtDate(r.period_from)} → ${fmtDate(r.period_to)}  ·  ${r.status}  ·  ${r.total_new_producers + r.total_changed_producers} items`,
  })),
)

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}
function fmtRelative(iso) {
  if (!iso) return 'never'
  const ms = Date.now() - new Date(iso).getTime()
  if (ms < 60_000) return 'just now'
  const mins = Math.round(ms / 60_000)
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs} h ago`
  const days = Math.round(hrs / 24)
  return `${days} d ago`
}
function statusColor(st) {
  return { done: 'green-2', processing: 'blue-2', pending: 'grey-3', failed: 'red-2' }[st] || 'grey-2'
}
function statusText(st) {
  return { done: 'green-9', processing: 'blue-9', pending: 'grey-8', failed: 'red-9' }[st] || 'grey-8'
}
const STAGE_LABELS = {
  interest: 'Interest',
  in_communication: 'In Communication',
  terms_negotiation: 'Negotiation',
  negotiation: 'Signing Contract',
  contract_signed: 'Contract Signed',
  on_platform: 'On the Platform',
  stopped: 'Stopped',
}
function stageLabel(s) { return STAGE_LABELS[s] || s || '—' }
function stageColor(s) {
  return ({
    interest: 'grey-7',
    in_communication: 'blue-7',
    terms_negotiation: 'amber-9',
    negotiation: 'orange-8',
    contract_signed: 'teal-8',
    on_platform: 'green-8',
    stopped: 'red-8',
  })[s] || 'grey-7'
}
function kindIcon(k) {
  return ({
    new_producer: 'add_circle',
    stage_change: 'trending_up',
    commercial_progress: 'handshake',
    blocker: 'block',
    loss: 'cancel',
    key_decision: 'gavel',
    milestone: 'flag',
    other: 'info',
  })[k] || 'info'
}
function kindColor(k) {
  return ({
    new_producer: '#2E7D32',
    stage_change: '#1565C0',
    commercial_progress: '#5E35B1',
    blocker: '#C62828',
    loss: '#6D4C41',
    key_decision: '#283593',
    milestone: '#00838F',
    other: '#546E7A',
  })[k] || '#546E7A'
}
function kindLabel(k) {
  return ({
    new_producer: 'New',
    stage_change: 'Stage change',
    commercial_progress: 'Commercial progress',
    blocker: 'Blocker',
    loss: 'Loss / refusal',
    key_decision: 'Key decision',
    milestone: 'Milestone',
    other: 'Other',
  })[k] || 'Other'
}
function kindBadgeColor(k) {
  return ({
    new_producer: 'green',
    stage_change: 'blue',
    commercial_progress: 'deep-purple',
    blocker: 'red',
    loss: 'brown',
    key_decision: 'indigo',
    milestone: 'cyan',
    other: 'grey',
  })[k] || 'grey'
}

async function loadLatest() {
  loading.value = true
  try {
    const [latest, list] = await Promise.all([
      api.get('/producer-weekly-reports/latest/').catch(err => {
        if (err.response?.status === 404) return { data: null }
        throw err
      }),
      api.get('/producer-weekly-reports/').then(r => r.data).catch(() => ({ results: [] })),
    ])
    report.value = latest.data
    selectedId.value = latest.data?.id || null
    history.value = (list.results || list || []).filter(r => r && r.id)
    schedulePolling()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Failed to load' })
  } finally {
    loading.value = false
  }
}

async function loadById(id) {
  if (!id) return
  loading.value = true
  try {
    const res = await api.get(`/producer-weekly-reports/${id}/`)
    report.value = res.data
    selectedId.value = id
    schedulePolling()
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Failed to load report' })
  } finally {
    loading.value = false
  }
}

async function retry() {
  if (!report.value) return
  try {
    const res = await api.post(`/producer-weekly-reports/${report.value.id}/retry/`)
    report.value = res.data
    schedulePolling()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Retry failed' })
  }
}

function schedulePolling() {
  clearTimeout(pollTimer)
  if (!report.value) return
  if (report.value.status === 'pending' || report.value.status === 'processing') {
    pollTimer = setTimeout(async () => {
      try {
        const res = await api.get(`/producer-weekly-reports/${report.value.id}/`)
        report.value = res.data
        schedulePolling()
      } catch { /* ignore */ }
    }, 4000)
  }
}

onMounted(loadLatest)
onUnmounted(() => clearTimeout(pollTimer))
</script>

<style scoped>
.report-card {
  background: #FFF;
  border: 1px solid #E0E0E0;
  border-left: 4px solid #546E7A;
  border-radius: 10px;
  padding: 12px 16px;
  transition: box-shadow 150ms ease;
}
.report-card:hover { box-shadow: 0 1px 6px rgba(0, 0, 0, 0.08); }
.report-card--new { border-left-color: #2E7D32; background: #F1F8E9; }
.producer-link {
  color: #2E7D32;
  text-decoration: none;
  font-weight: 500;
}
.producer-link:hover { text-decoration: underline; }
</style>
