<template>
  <q-page class="q-pa-md">

    <!-- Toolbar -->
    <div class="row items-center q-mb-md q-gutter-sm">
      <q-select
        v-model="filterFunnel"
        :options="funnelOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="Both funnels"
        style="min-width:160px"
      />

      <q-btn
        :outline="!onlyMine"
        :color="onlyMine ? 'primary' : 'grey-7'"
        :icon="onlyMine ? 'person' : 'person_outline'"
        label="Assigned to Me"
        dense unelevated no-caps
        style="border-radius:8px;font-size:13px;"
        @click="onlyMine = !onlyMine"
      />

      <q-space />

      <template v-if="!isPending && currentJob && currentJob.status === 'done'">
        <q-chip dense icon="person_off" color="deep-orange-1" text-color="deep-orange-8" style="font-weight:700">
          {{ filteredResults.length }} abandoned
        </q-chip>
        <q-chip v-if="criticalCount > 0" dense icon="warning" color="red-1" text-color="red-8" style="font-weight:700">
          {{ criticalCount }} critical (&gt;30d)
        </q-chip>
        <div class="text-caption text-grey-5 q-ml-sm">
          {{ currentJob.total_analyzed }} analyzed · {{ fmtTime(currentJob.completed_at) }}
        </div>
      </template>

      <q-btn unelevated color="primary" icon="manage_search" label="Analyze"
        :loading="isPending" dense style="border-radius:8px;height:36px;"
        @click="startAnalysis" />
    </div>

    <!-- Main layout: history sidebar + content -->
    <div class="row q-gutter-md" style="align-items:flex-start">

      <!-- History sidebar -->
      <div v-if="history.length" style="width:200px;flex-shrink:0;">
        <div class="text-caption text-grey-5 q-mb-xs" style="font-weight:600;text-transform:uppercase;letter-spacing:.5px;">History</div>
        <div
          v-for="job in history" :key="job.job_id"
          class="history-item"
          :class="currentJob && currentJob.job_id === job.job_id ? 'history-item--active' : ''"
          @click="loadJob(job.job_id)"
        >
          <div class="row items-center justify-between q-mb-xs" style="gap:4px;">
            <span style="font-size:11px;font-weight:600;color:#37474F;">{{ fmtDate(job.created_at) }}</span>
            <q-chip v-if="job.status === 'done'" dense size="xs"
              :color="job.abandoned_count > 0 ? 'deep-orange-1' : 'green-1'"
              :text-color="job.abandoned_count > 0 ? 'deep-orange-8' : 'green-8'"
              style="font-weight:700;height:16px;font-size:10px;">
              {{ job.abandoned_count }}
            </q-chip>
            <q-chip v-else-if="job.status === 'error'" dense size="xs" color="red-1" text-color="red-8"
              style="font-weight:700;height:16px;font-size:10px;">err</q-chip>
          </div>
          <div style="font-size:10px;color:#90A4AE;">
            {{ job.total_analyzed || '—' }} analyzed
            <span v-if="job.funnel_filter"> · {{ job.funnel_filter }}</span>
          </div>
        </div>
      </div>

      <!-- Content area -->
      <div style="flex:1;min-width:0;">

        <!-- Initial state — no history, not running -->
        <div v-if="!history.length && !isPending" class="flex flex-center column q-mt-xl" style="gap:16px;">
          <q-icon name="smart_toy" size="64px" color="grey-4" />
          <div class="text-grey-5 text-body2 text-center" style="max-width:400px;">
            AI looks through producer cards to find ones that might need a little extra attention.
          </div>
          <q-btn unelevated color="primary" icon="manage_search" label="Analyze Now"
            style="border-radius:8px;" @click="startAnalysis" />
        </div>

        <!-- Pending / Running -->
        <div v-else-if="isPending" class="flex flex-center column q-mt-xl" style="gap:16px;">
          <q-spinner-dots color="primary" size="64px" />
          <div class="text-grey-5 text-body2">Analyzing producer cards with AI…</div>
          <div class="text-caption text-grey-4">You can navigate away — results will be waiting when you return.</div>
        </div>

        <!-- Error on current job -->
        <q-banner v-else-if="currentJob && currentJob.status === 'error'" rounded
          class="bg-red-1 text-red-8 q-mb-md" style="border-radius:10px;">
          <template #avatar><q-icon name="error_outline" color="red-7" /></template>
          AI analysis failed: {{ currentJob.error_message || 'unknown error' }}
          <template #action>
            <q-btn flat dense label="Retry" color="red-8" @click="startAnalysis" />
          </template>
        </q-banner>

        <!-- No abandoned -->
        <div v-else-if="currentJob && currentJob.status === 'done' && !results.length"
          class="flex flex-center column q-mt-xl" style="gap:12px;">
          <q-icon name="check_circle" size="64px" color="green-5" />
          <div class="text-grey-5 text-body2">No abandoned cards found</div>
          <div class="text-caption text-grey-4">{{ currentJob.total_analyzed }} cards analyzed</div>
        </div>

        <!-- Results table -->
        <q-card v-else-if="results.length" flat bordered style="border-radius:12px;overflow:hidden">
          <q-table
            :rows="filteredResults"
            :columns="columns"
            row-key="id"
            flat
            :pagination="{ rowsPerPage: 25 }"
            style="cursor:pointer;"
            @row-click="(_, row) => $router.push(`/producers/${row.id}`)"
          >
            <template #body-cell-name="props">
              <q-td :props="props">
                <div style="font-weight:600; font-size:13px; color:#212121;">{{ props.row.name }}</div>
                <div v-if="props.row.company" class="text-caption text-grey-6">{{ props.row.company }}</div>
              </q-td>
            </template>

            <template #body-cell-funnel="props">
              <q-td :props="props">
                <q-chip dense size="xs"
                  :color="props.row.funnel === 'onboarding' ? 'blue-1' : 'green-1'"
                  :text-color="props.row.funnel === 'onboarding' ? 'blue-9' : 'green-9'"
                  style="font-weight:600;">
                  {{ props.row.funnel_display }}
                </q-chip>
              </q-td>
            </template>

            <template #body-cell-stage="props">
              <q-td :props="props">
                <span style="font-size:12px;">{{ props.row.stage_display }}</span>
              </q-td>
            </template>

            <template #body-cell-stage_since="props">
              <q-td :props="props">
                <span :style="`font-size:12px; font-weight:600; color:${staleDaysColor(props.row.stage_since)};`">
                  {{ staleDaysLabel(props.row.stage_since) }}
                </span>
              </q-td>
            </template>

            <template #body-cell-assigned_to_name="props">
              <q-td :props="props">
                <span class="text-caption text-grey-7">{{ props.row.assigned_to_name || '—' }}</span>
              </q-td>
            </template>

            <template #body-cell-ai_reason="props">
              <q-td :props="props" style="max-width:340px; white-space:normal;">
                <span style="font-size:12px; color:#546E7A; line-height:1.4;">{{ props.row.ai_reason }}</span>
              </q-td>
            </template>
          </q-table>
        </q-card>

        <!-- Waiting for selection -->
        <div v-else-if="history.length && !isPending" class="flex flex-center q-mt-xl text-grey-4 text-body2">
          Select an analysis from the history
        </div>

      </div>
    </div>

  </q-page>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from 'boot/axios'
import { useAuthStore } from 'src/stores/auth'

const authStore = useAuthStore()

const JOB_KEY = 'abandoned_job_id'

const isPending   = ref(false)
const filterFunnel = ref(null)
const onlyMine    = ref(false)
const history     = ref([])   // list of job summaries
const currentJob  = ref(null) // full job data (with results)
const results     = ref([])
let pollTimer     = null

const filteredResults = computed(() => {
  if (!onlyMine.value) return results.value
  const uid = authStore.user?.id
  return results.value.filter(r => r.assigned_to === uid || r.assigned_to_id === uid)
})

const funnelOptions = [
  { label: 'Onboarding', value: 'onboarding' },
  { label: 'Support',    value: 'support' },
]

const columns = [
  { name: 'name',             label: 'Producer',      field: 'name',             align: 'left', sortable: true },
  { name: 'funnel',           label: 'Funnel',        field: 'funnel',           align: 'left' },
  { name: 'stage',            label: 'Stage',         field: 'stage_display',    align: 'left', sortable: true },
  { name: 'stage_since',      label: 'Stuck since',   field: 'stage_since',      align: 'left', sortable: true },
  { name: 'assigned_to_name', label: 'Responsible',   field: 'assigned_to_name', align: 'left', sortable: true },
  { name: 'ai_reason',        label: 'AI Assessment', field: 'ai_reason',        align: 'left' },
]

const criticalCount = computed(() =>
  filteredResults.value.filter(r => {
    if (!r.stage_since) return false
    return Math.floor((new Date() - new Date(r.stage_since)) / 86400000) >= 30
  }).length
)

// ── History ────────────────────────────────────────────────────────────────
const fetchHistory = async () => {
  try {
    const res = await api.get('/producers/abandoned-history/')
    history.value = res.data
  } catch (_) {}
}

const loadJob = async (jobId) => {
  try {
    const res = await api.get('/producers/abandoned-status/', { params: { job_id: jobId } })
    currentJob.value = { ...res.data, job_id: jobId }
    results.value    = res.data.results || []
  } catch (_) {}
}

// ── Start new analysis ─────────────────────────────────────────────────────
const startAnalysis = async () => {
  stopPolling()
  isPending.value  = true
  currentJob.value = null
  results.value    = []

  try {
    const payload = {}
    if (filterFunnel.value) payload.funnel = filterFunnel.value
    const res = await api.post('/producers/abandoned/', payload)
    const jobId = res.data.job_id
    localStorage.setItem(JOB_KEY, String(jobId))
    startPolling(jobId)
  } catch (e) {
    isPending.value = false
  }
}

// ── Polling ────────────────────────────────────────────────────────────────
const startPolling = (jobId) => {
  stopPolling()
  isPending.value = true
  pollStatus(jobId)
  pollTimer = setInterval(() => pollStatus(jobId), 3000)
}

const pollStatus = async (jobId) => {
  try {
    const res = await api.get('/producers/abandoned-status/', { params: { job_id: jobId } })
    const data = res.data

    if (data.status === 'done' || data.status === 'error') {
      stopPolling()
      localStorage.removeItem(JOB_KEY)
      isPending.value  = false
      currentJob.value = { ...data, job_id: jobId }
      results.value    = data.results || []
      await fetchHistory()
    }
  } catch (e) {
    if (e.response?.status === 404) {
      stopPolling()
      localStorage.removeItem(JOB_KEY)
      isPending.value = false
    }
  }
}

const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

// ── Mount ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  await fetchHistory()

  // Resume in-progress job
  const savedJobId = localStorage.getItem(JOB_KEY)
  if (savedJobId) {
    startPolling(Number(savedJobId))
    return
  }

  // Load the most recent completed job automatically
  const latest = history.value.find(j => j.status === 'done' || j.status === 'error')
  if (latest) {
    await loadJob(latest.job_id)
  }
})

onUnmounted(() => stopPolling())

// ── Helpers ────────────────────────────────────────────────────────────────
const fmtDate = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: '2-digit' })
}

const fmtTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
    + ' ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

const staleDaysColor = (since) => {
  if (!since) return '#9E9E9E'
  const days = Math.floor((new Date() - new Date(since)) / 86400000)
  if (days >= 30) return '#C62828'
  if (days >= 14) return '#E65100'
  return '#F57F17'
}

const staleDaysLabel = (since) => {
  if (!since) return '—'
  const days = Math.floor((new Date() - new Date(since)) / 86400000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7)  return `${days}d ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  return `${Math.floor(days / 30)}mo ago`
}
</script>

<style scoped>
.history-item {
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid #ECEFF1;
  background: #FAFAFA;
  transition: background 0.1s;
}
.history-item:hover { background: #F0F4F8; }
.history-item--active {
  background: #E8EAF6;
  border-color: #9FA8DA;
}
</style>
