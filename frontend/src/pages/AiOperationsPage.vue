<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6 text-weight-bold">Background Operations</div>
      <q-space />
      <q-btn
        outline
        dense
        size="sm"
        color="primary"
        icon="refresh"
        :loading="loading"
        label="Refresh"
        @click="load"
      />
    </div>

    <div class="text-caption text-grey-7 q-mb-md" style="max-width:840px;">
      Single source of truth for every process the CRM does on its own —
      AI generation, data syncs from external systems (Asana, external CRM)
      and maintenance routines. Each card shows what the job does, when it
      runs next, when it last ran, what it produced, and lets you trigger it
      on demand. If a job stops working it shows up here as
      <span class="ai-pill ai-pill--err">Error</span> or
      <span class="ai-pill ai-pill--never">Never ran</span> instead of silently
      missing data on user-facing pages.
    </div>

    <!-- Top-line health banner -->
    <div v-if="jobs.length" class="ai-overall row items-center q-mb-md">
      <div class="ai-overall-pill ai-overall-pill--ok">
        <q-icon name="check_circle" size="14px" /> {{ overall.ok }} healthy
      </div>
      <div v-if="overall.err" class="ai-overall-pill ai-overall-pill--err">
        <q-icon name="error" size="14px" /> {{ overall.err }} with errors
      </div>
      <div v-if="overall.run" class="ai-overall-pill ai-overall-pill--run">
        <q-icon name="autorenew" size="14px" /> {{ overall.run }} running now
      </div>
      <div v-if="overall.never" class="ai-overall-pill ai-overall-pill--never">
        <q-icon name="hourglass_empty" size="14px" /> {{ overall.never }} never ran
      </div>
    </div>

    <!-- Dead-ended items banner: rows that hit MAX_RETRIES and stopped retrying -->
    <q-banner
      v-if="deadTotal"
      class="ai-dead-banner q-mb-md"
      rounded
    >
      <template v-slot:avatar>
        <q-icon name="report_problem" color="white" />
      </template>
      <div>
        <div class="text-weight-bold">
          {{ deadTotal }} item{{ deadTotal === 1 ? '' : 's' }} stopped retrying after {{ maxRetries }} consecutive failures
        </div>
        <div class="text-caption" style="opacity:.95;">
          To protect OpenAI tokens the self-healer gives up after {{ maxRetries }} consecutive failures per row.
          Investigate the error, fix the root cause, then click <b>Reset</b> to put the item back on the retry queue.
        </div>
      </div>
      <template v-slot:action>
        <q-btn flat color="white" no-caps label="View dead-ended" @click="openDeadDialog" />
      </template>
    </q-banner>

    <div v-if="loading && !jobs.length" class="text-center q-pa-lg text-grey-6">
      <q-spinner color="primary" size="32px" /> Loading…
    </div>

    <template v-else v-for="cat in CATEGORIES" :key="cat.id">
      <div v-if="grouped[cat.id]?.length" class="ai-cat-header q-mt-md">
        <q-icon :name="cat.icon" size="18px" :color="cat.color" />
        <span class="ai-cat-title">{{ cat.label }}</span>
        <span class="ai-cat-sub">{{ cat.sub }}</span>
        <q-space />
        <span class="ai-cat-count">{{ grouped[cat.id].length }} job{{ grouped[cat.id].length === 1 ? '' : 's' }}</span>
      </div>
      <div v-if="grouped[cat.id]?.length" class="ai-grid">
      <q-card
        v-for="job in grouped[cat.id]"
        :key="job.id"
        flat
        bordered
        class="ai-card"
        :class="`ai-card--${job.health}`"
      >
        <q-card-section class="q-pb-none">
          <div class="row items-center no-wrap">
            <div class="ai-status-dot" :class="`ai-status-dot--${job.health}`" />
            <div class="text-subtitle1 text-weight-bold ellipsis">{{ job.name }}</div>
            <q-space />
            <span class="ai-pill" :class="healthClass(job.health)">{{ healthLabel(job.health) }}</span>
          </div>
          <div class="text-caption text-grey-7 q-mt-xs">{{ job.description }}</div>
        </q-card-section>

        <q-card-section class="q-pt-sm">
          <div class="ai-meta-row">
            <q-icon name="schedule" size="14px" color="grey-7" />
            <span class="ai-meta-label">Schedule:</span>
            <span class="ai-meta-value">{{ job.schedule_human }}</span>
          </div>
          <div class="ai-meta-row">
            <q-icon name="event" size="14px" color="grey-7" />
            <span class="ai-meta-label">Next run:</span>
            <span class="ai-meta-value">{{ fmtFuture(job.next_run) }}</span>
          </div>
          <div class="ai-meta-row">
            <q-icon name="history" size="14px" color="grey-7" />
            <span class="ai-meta-label">Last run:</span>
            <span class="ai-meta-value">
              <template v-if="job.last_run">
                {{ fmtPast(job.last_run.started_at) }}
                <span class="text-grey-6">·</span>
                <span :class="runStatusClass(job.last_run.status)">{{ job.last_run.status }}</span>
                <span v-if="job.last_run.duration_ms" class="text-grey-6">
                  · {{ (job.last_run.duration_ms / 1000).toFixed(1) }}s
                </span>
              </template>
              <span v-else class="text-grey-5">never</span>
            </span>
          </div>
          <div v-if="job.last_run && job.last_run.summary" class="ai-summary">
            {{ job.last_run.summary }}
          </div>
          <div v-if="job.last_run && job.last_run.status === 'error' && job.last_run.error_message"
               class="ai-error">
            {{ truncate(job.last_run.error_message, 240) }}
          </div>
          <div class="ai-meta-row q-mt-sm">
            <q-icon name="insights" size="14px" color="grey-7" />
            <span class="ai-meta-label">Last 7d:</span>
            <span class="ai-meta-value">
              <span class="ai-stat ai-stat--ok">{{ job.last_7d_counts.success }} ok</span>
              <span v-if="job.last_7d_counts.error"
                    class="ai-stat ai-stat--err">{{ job.last_7d_counts.error }} err</span>
              <span v-if="job.last_7d_counts.running"
                    class="ai-stat ai-stat--run">{{ job.last_7d_counts.running }} running</span>
            </span>
          </div>
        </q-card-section>

        <q-card-actions align="between" class="q-pt-none">
          <q-btn
            v-if="job.artifact_path"
            flat
            dense
            no-caps
            size="sm"
            color="primary"
            icon="open_in_new"
            :label="job.artifact || 'Open'"
            :to="job.artifact_path"
          />
          <q-space />
          <q-btn
            outline
            dense
            no-caps
            size="sm"
            color="primary"
            icon="bolt"
            label="Run now"
            :loading="running[job.id]"
            @click="runNow(job)"
          />
          <q-btn
            flat
            dense
            no-caps
            size="sm"
            color="grey-7"
            icon="list"
            label="History"
            @click="openHistory(job)"
          />
        </q-card-actions>
      </q-card>
      </div>
    </template>

    <!-- Dead-ended items dialog -->
    <q-dialog v-model="deadOpen">
      <q-card style="min-width:760px;max-width:1100px;">
        <q-card-section class="row items-center q-pb-none">
          <div class="text-subtitle1 text-weight-bold">
            Dead-ended items — gave up after {{ maxRetries }} consecutive failures
          </div>
          <q-space />
          <q-btn flat dense round icon="refresh" :loading="deadLoading" @click="loadDead" />
          <q-btn flat dense round icon="close" v-close-popup />
        </q-card-section>
        <q-card-section class="text-caption text-grey-7">
          Each row is permanently in <code>failed</code> state and will not be retried until you click <b>Reset</b>.
          Use <b>Reset</b> after fixing the underlying problem (e.g. corrupt audio, OpenAI quota, prompt bug).
        </q-card-section>
        <q-separator />
        <q-card-section style="max-height:65vh;overflow:auto;" class="q-pt-sm">
          <div v-if="deadLoading" class="text-grey-6 q-pa-md text-center">
            <q-spinner /> Loading…
          </div>
          <template v-else>
            <div class="text-weight-bold q-mb-xs">
              Transcriptions <span class="text-grey-6">({{ dead.transcriptions.length }})</span>
            </div>
            <div v-if="!dead.transcriptions.length" class="text-grey-5 q-mb-md">— none —</div>
            <q-list v-else dense separator class="q-mb-md">
              <q-item v-for="row in dead.transcriptions" :key="`t-${row.id}`">
                <q-item-section>
                  <q-item-label>
                    <b>#{{ row.id }}</b> · {{ row.partner }}
                    <span class="text-grey-6 q-ml-sm">{{ fmtAbsolute(row.date) }}</span>
                  </q-item-label>
                  <q-item-label caption class="text-red-7">{{ row.last_error }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn outline dense no-caps size="sm" color="primary"
                         icon="restart_alt" label="Reset"
                         :loading="resetting[`t-${row.id}`]"
                         @click="resetItem('transcription', row.id)" />
                </q-item-section>
              </q-item>
            </q-list>

            <div class="text-weight-bold q-mb-xs">
              Summaries <span class="text-grey-6">({{ dead.summaries.length }})</span>
            </div>
            <div v-if="!dead.summaries.length" class="text-grey-5 q-mb-md">— none —</div>
            <q-list v-else dense separator class="q-mb-md">
              <q-item v-for="row in dead.summaries" :key="`s-${row.id}`">
                <q-item-section>
                  <q-item-label>
                    <b>#{{ row.id }}</b> · {{ row.partner }}
                    <span class="text-grey-6 q-ml-sm">{{ fmtAbsolute(row.date) }}</span>
                  </q-item-label>
                  <q-item-label caption class="text-red-7">{{ row.last_error }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn outline dense no-caps size="sm" color="primary"
                         icon="restart_alt" label="Reset"
                         :loading="resetting[`s-${row.id}`]"
                         @click="resetItem('summary', row.id)" />
                </q-item-section>
              </q-item>
            </q-list>

            <div class="text-weight-bold q-mb-xs">
              Operator feedback <span class="text-grey-6">({{ dead.feedback.length }})</span>
            </div>
            <div v-if="!dead.feedback.length" class="text-grey-5 q-mb-md">— none —</div>
            <q-list v-else dense separator>
              <q-item v-for="row in dead.feedback" :key="`f-${row.id}`">
                <q-item-section>
                  <q-item-label>
                    <b>#{{ row.id }}</b> · {{ row.operator }} · {{ row.feedback_type }} · {{ row.period_start }}
                  </q-item-label>
                  <q-item-label caption class="text-red-7">{{ row.last_error }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn outline dense no-caps size="sm" color="primary"
                         icon="restart_alt" label="Reset"
                         :loading="resetting[`f-${row.id}`]"
                         @click="resetItem('feedback', row.id)" />
                </q-item-section>
              </q-item>
            </q-list>
          </template>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- History dialog -->
    <q-dialog v-model="historyOpen">
      <q-card style="min-width:640px;max-width:920px;">
        <q-card-section class="row items-center q-pb-none">
          <div class="text-subtitle1 text-weight-bold">{{ historyJob?.name }}</div>
          <q-space />
          <q-btn flat dense round icon="close" v-close-popup />
        </q-card-section>
        <q-card-section class="text-caption text-grey-7">
          {{ historyJob?.description }}
        </q-card-section>
        <q-separator />
        <q-card-section style="max-height:60vh;overflow:auto;">
          <div v-if="!historyJob?.history?.length" class="text-grey-6 q-pa-md text-center">
            No runs recorded yet.
          </div>
          <q-list v-else dense separator>
            <q-item v-for="r in historyJob.history" :key="r.id">
              <q-item-section avatar style="min-width:24px;">
                <span class="ai-status-dot ai-status-dot--small"
                      :class="`ai-status-dot--${runHealth(r.status)}`" />
              </q-item-section>
              <q-item-section>
                <q-item-label>
                  <span :class="runStatusClass(r.status)">{{ r.status }}</span>
                  <span class="text-grey-6 q-ml-sm">{{ fmtAbsolute(r.started_at) }}</span>
                  <span v-if="r.duration_ms" class="text-grey-6 q-ml-sm">
                    · {{ (r.duration_ms / 1000).toFixed(1) }}s
                  </span>
                  <span v-if="r.trigger" class="ai-trigger-tag q-ml-sm">{{ r.trigger }}</span>
                  <span v-if="r.triggered_by" class="text-grey-6 q-ml-xs">by {{ r.triggered_by }}</span>
                </q-item-label>
                <q-item-label v-if="r.summary" caption>{{ r.summary }}</q-item-label>
                <q-item-label v-if="r.error_message" caption class="text-red-7">
                  {{ truncate(r.error_message, 320) }}
                </q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useQuasar } from 'quasar'
import { api } from 'boot/axios'

const $q      = useQuasar()
const loading = ref(false)
const jobs    = ref([])
const running = reactive({})
const historyOpen = ref(false)
const historyJob  = ref(null)
const deadOpen    = ref(false)
const deadLoading = ref(false)
const dead        = ref({ transcriptions: [], summaries: [], feedback: [] })
const deadCounts  = ref({ transcriptions: 0, summaries: 0, feedback: 0 })
const maxRetries  = ref(5)
const resetting   = reactive({})
let pollTimer = null

const deadTotal = computed(() =>
  (deadCounts.value.transcriptions || 0)
  + (deadCounts.value.summaries || 0)
  + (deadCounts.value.feedback || 0)
)

const CATEGORIES = [
  { id: 'data_sync',   label: 'Data Sync',   sub: 'External APIs → CRM database',
    icon: 'cloud_download', color: 'indigo' },
  { id: 'ai_reports',  label: 'AI Reports',  sub: 'Producer & brand intelligence',
    icon: 'auto_awesome',   color: 'deep-purple' },
  { id: 'ai_feedback', label: 'AI Feedback', sub: 'Personalised operator coaching',
    icon: 'psychology',     color: 'teal' },
  { id: 'maintenance', label: 'Maintenance', sub: 'Self-healing & retry routines',
    icon: 'build',          color: 'orange' },
]

const grouped = computed(() => {
  const map = {}
  for (const c of CATEGORIES) map[c.id] = []
  for (const j of jobs.value) {
    const k = map[j.category] ? j.category : 'ai_reports'
    map[k].push(j)
  }
  return map
})

const overall = computed(() => {
  const o = { ok: 0, err: 0, run: 0, never: 0 }
  for (const j of jobs.value) {
    if (j.health === 'ok')        o.ok++
    else if (j.health === 'error')   o.err++
    else if (j.health === 'running') o.run++
    else                              o.never++
  }
  return o
})

async function load() {
  loading.value = true
  try {
    const res = await api.get('/ai-operations/')
    jobs.value = res.data.jobs || []
    if (res.data.dead_ended) deadCounts.value = res.data.dead_ended
    if (res.data.max_retries) maxRetries.value = res.data.max_retries
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Failed to load AI operations' })
  } finally {
    loading.value = false
  }
}

async function loadDead() {
  deadLoading.value = true
  try {
    const res = await api.get('/ai-operations/dead-ended/')
    dead.value = res.data
    deadCounts.value = {
      transcriptions: res.data.transcriptions.length,
      summaries:      res.data.summaries.length,
      feedback:       res.data.feedback.length,
    }
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Failed to load dead-ended items' })
  } finally {
    deadLoading.value = false
  }
}

function openDeadDialog() {
  deadOpen.value = true
  loadDead()
}

async function resetItem(kind, id) {
  const key = `${kind[0]}-${id}`
  resetting[key] = true
  try {
    await api.post('/ai-operations/dead-ended/', { kind, id })
    $q.notify({ type: 'positive', message: 'Reset — will retry on next healing pass', timeout: 1800 })
    loadDead()
    setTimeout(load, 500)
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Reset failed' })
  } finally {
    resetting[key] = false
  }
}

async function runNow(job) {
  running[job.id] = true
  try {
    await api.post(`/ai-operations/${job.id}/run-now/`)
    $q.notify({ type: 'positive', message: `Queued: ${job.name}`, timeout: 1500 })
    setTimeout(load, 1500)
    setTimeout(load, 6000)
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.error || 'Failed to start job' })
  } finally {
    running[job.id] = false
  }
}

async function openHistory(job) {
  try {
    const res = await api.get(`/ai-operations/${job.id}/`)
    historyJob.value = res.data
    historyOpen.value = true
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Failed to load history' })
  }
}

function healthClass(h) {
  return {
    'ok':        'ai-pill--ok',
    'error':     'ai-pill--err',
    'running':   'ai-pill--run',
    'never_ran': 'ai-pill--never',
    'unknown':   'ai-pill--never',
  }[h] || 'ai-pill--never'
}
function healthLabel(h) {
  return {
    'ok':        'Healthy',
    'error':     'Error',
    'running':   'Running',
    'never_ran': 'Never ran',
    'unknown':   'Unknown',
  }[h] || h
}
function runHealth(s) {
  if (s === 'success') return 'ok'
  if (s === 'error')   return 'error'
  if (s === 'running') return 'running'
  return 'unknown'
}
function runStatusClass(s) {
  return {
    success: 'text-green-8 text-weight-medium',
    error:   'text-red-7 text-weight-medium',
    running: 'text-blue-7 text-weight-medium',
  }[s] || ''
}

function fmtPast(iso) {
  if (!iso) return '—'
  const d  = new Date(iso)
  const ms = Date.now() - d.getTime()
  if (ms < 0) return d.toLocaleString()
  const m  = Math.floor(ms / 60000)
  if (m < 1)   return 'just now'
  if (m < 60)  return `${m}m ago`
  const h  = Math.floor(m / 60)
  if (h < 24)  return `${h}h ago`
  const days = Math.floor(h / 24)
  if (days < 7) return `${days}d ago`
  return d.toLocaleString()
}
function fmtFuture(iso) {
  if (!iso) return '—'
  const d   = new Date(iso)
  const ms  = d.getTime() - Date.now()
  if (ms <= 0) return 'soon'
  const m   = Math.floor(ms / 60000)
  if (m < 60) return `in ${m}m  ·  ${d.toLocaleString()}`
  const h   = Math.floor(m / 60)
  if (h < 48) return `in ${h}h  ·  ${d.toLocaleString()}`
  const days = Math.floor(h / 24)
  return `in ${days}d  ·  ${d.toLocaleString()}`
}
function fmtAbsolute(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}
function truncate(s, n) {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '…' : s
}

onMounted(() => {
  load()
  pollTimer = setInterval(load, 30000)
})
onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped>
.ai-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 14px;
}
.ai-card {
  border-radius: 12px;
  border-left: 4px solid #cfd8dc;
  transition: box-shadow .15s ease;
}
.ai-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.05); }
.ai-card--ok        { border-left-color: #43a047; }
.ai-card--error     { border-left-color: #e53935; }
.ai-card--running   { border-left-color: #1e88e5; }
.ai-card--never_ran { border-left-color: #9e9e9e; }
.ai-card--unknown   { border-left-color: #9e9e9e; }

.ai-status-dot {
  width: 10px; height: 10px; border-radius: 50%;
  margin-right: 8px; flex: 0 0 10px;
  background: #9e9e9e;
}
.ai-status-dot--ok        { background: #43a047; box-shadow: 0 0 0 3px rgba(67,160,71,.18); }
.ai-status-dot--error     { background: #e53935; box-shadow: 0 0 0 3px rgba(229,57,53,.18); }
.ai-status-dot--running   { background: #1e88e5; box-shadow: 0 0 0 3px rgba(30,136,229,.18); animation: pulse 1.4s ease-in-out infinite; }
.ai-status-dot--never_ran { background: #9e9e9e; }
.ai-status-dot--small     { width: 8px; height: 8px; }

@keyframes pulse {
  0%,100% { opacity: 1; }
  50%     { opacity: .35; }
}

.ai-pill {
  display: inline-block;
  font-size: 11px; font-weight: 700;
  padding: 2px 8px; border-radius: 12px;
  letter-spacing: .2px;
}
.ai-pill--ok    { background: #e8f5e9; color: #2e7d32; }
.ai-pill--err   { background: #ffebee; color: #c62828; }
.ai-pill--run   { background: #e3f2fd; color: #1565c0; }
.ai-pill--never { background: #eceff1; color: #546e7a; }

.ai-meta-row {
  display: flex; align-items: center; gap: 6px;
  font-size: 12.5px; color: #424242;
  padding: 2px 0;
  flex-wrap: wrap;
}
.ai-meta-label { color: #757575; min-width: 64px; }
.ai-meta-value { color: #212121; }

.ai-summary {
  margin-top: 8px;
  padding: 6px 8px;
  background: #fafafa;
  border-radius: 6px;
  font-size: 12px;
  color: #424242;
}
.ai-error {
  margin-top: 6px;
  padding: 6px 8px;
  background: #ffebee;
  border-radius: 6px;
  font-size: 12px;
  color: #b71c1c;
  font-family: ui-monospace, SFMono-Regular, monospace;
}

.ai-stat {
  display: inline-block;
  margin-right: 6px;
  font-weight: 600;
  font-size: 11.5px;
}
.ai-stat--ok  { color: #2e7d32; }
.ai-stat--err { color: #c62828; }
.ai-stat--run { color: #1565c0; }

.ai-trigger-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 8px;
  background: #eceff1;
  color: #546e7a;
  font-size: 10.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .3px;
}

/* Category headers */
.ai-cat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0 8px 0;
  border-bottom: 1px solid #eceff1;
  margin-bottom: 12px;
}
.ai-cat-title {
  font-size: 14.5px;
  font-weight: 700;
  color: #263238;
}
.ai-cat-sub {
  font-size: 12px;
  color: #78909c;
}
.ai-cat-count {
  font-size: 11.5px;
  font-weight: 600;
  color: #546e7a;
  background: #eceff1;
  padding: 2px 8px;
  border-radius: 10px;
}

/* Top-line overall pills */
.ai-overall {
  gap: 8px;
  flex-wrap: wrap;
}
.ai-overall-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 14px;
  font-size: 12px;
  font-weight: 600;
}
.ai-overall-pill--ok    { background: #e8f5e9; color: #2e7d32; }
.ai-overall-pill--err   { background: #ffebee; color: #c62828; }
.ai-overall-pill--run   { background: #e3f2fd; color: #1565c0; }
.ai-overall-pill--never { background: #eceff1; color: #546e7a; }

.ai-dead-banner {
  background: linear-gradient(90deg, #c62828, #d84315);
  color: #fff;
  padding: 10px 14px;
  border-radius: 10px;
}
.ai-dead-banner :deep(.q-banner__avatar) { color: #fff; }
.ai-dead-banner :deep(.q-banner__actions) { color: #fff; }
</style>
