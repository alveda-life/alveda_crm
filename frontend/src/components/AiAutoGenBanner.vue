<template>
  <div v-if="status" class="ai-banner" :class="`ai-banner--${status.health}`">
    <div class="ai-banner__icon">
      <q-icon :name="iconName" size="18px" />
    </div>
    <div class="ai-banner__body">
      <div class="ai-banner__title">
        {{ title || status.name }}
        <span class="ai-banner__health-tag" :class="`ai-banner__health-tag--${status.health}`">
          {{ healthLabel }}
        </span>
      </div>
      <div class="ai-banner__meta">
        <span class="ai-banner__sched">
          <q-icon name="schedule" size="12px" />
          Auto-runs: {{ status.schedule_human }}
        </span>
        <span class="ai-banner__sep">·</span>
        <span class="ai-banner__last">
          <q-icon name="history" size="12px" />
          Last:
          <template v-if="status.last_run">
            <span :class="lastClass">{{ status.last_run.status }}</span>
            {{ fmtPast(status.last_run.started_at) }}
          </template>
          <span v-else class="text-grey-5">never</span>
        </span>
        <span class="ai-banner__sep">·</span>
        <span class="ai-banner__next">
          <q-icon name="event" size="12px" />
          Next: {{ fmtFuture(status.next_run) }}
        </span>
      </div>
      <div v-if="showError && status.health === 'error'" class="ai-banner__alert">
        Auto-generation is failing — content may be stale. Ask an admin to check
        <router-link to="/admin/ai-operations" class="ai-banner__link">Background Operations</router-link>.
      </div>
    </div>
    <q-btn
      v-if="canTrigger"
      flat dense no-caps size="sm"
      color="primary"
      icon="bolt"
      label="Run now"
      :loading="running"
      class="ai-banner__btn"
      @click="runNow"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useQuasar } from 'quasar'
import { api } from 'boot/axios'
import { useAuthStore } from 'stores/auth'

const props = defineProps({
  jobId:        { type: String, required: true },
  title:        { type: String, default: '' },
  showError:    { type: Boolean, default: true },
  pollMs:       { type: Number, default: 60000 },
})

const $q        = useQuasar()
const authStore = useAuthStore()
const status    = ref(null)
const running   = ref(false)
let timer = null

const canTrigger = computed(() => authStore.isAdmin)

const iconName = computed(() => {
  if (!status.value) return 'autorenew'
  return ({
    ok:        'check_circle',
    error:     'error',
    running:   'autorenew',
    never_ran: 'help_outline',
    unknown:   'help_outline',
  })[status.value.health] || 'autorenew'
})

const healthLabel = computed(() => {
  if (!status.value) return ''
  return ({
    ok:        'Healthy',
    error:     'Failing',
    running:   'Running',
    never_ran: 'Never ran',
    unknown:   'Unknown',
  })[status.value.health] || ''
})

const lastClass = computed(() => {
  const s = status.value?.last_run?.status
  return ({
    success: 'text-green-8 text-weight-medium',
    error:   'text-red-7 text-weight-medium',
    running: 'text-blue-7 text-weight-medium',
  })[s] || ''
})

async function load() {
  try {
    const res = await api.get(`/ai-operations/${props.jobId}/status/`)
    status.value = res.data
  } catch {}
}

async function runNow() {
  running.value = true
  try {
    await api.post(`/ai-operations/${props.jobId}/run-now/`)
    $q.notify({ type: 'positive', message: 'Generation queued', timeout: 1500 })
    setTimeout(load, 1500)
    setTimeout(load, 6000)
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.error || 'Failed' })
  } finally {
    running.value = false
  }
}

function fmtPast(iso) {
  if (!iso) return '—'
  const d  = new Date(iso)
  const ms = Date.now() - d.getTime()
  if (ms < 0) return d.toLocaleString()
  const m  = Math.floor(ms / 60000)
  if (m < 1)  return 'just now'
  if (m < 60) return `${m}m ago`
  const h  = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
function fmtFuture(iso) {
  if (!iso) return '—'
  const d   = new Date(iso)
  const ms  = d.getTime() - Date.now()
  if (ms <= 0) return 'soon'
  const m   = Math.floor(ms / 60000)
  if (m < 60) return `in ${m}m`
  const h   = Math.floor(m / 60)
  if (h < 48) return `in ${h}h`
  return `in ${Math.floor(h / 24)}d`
}

onMounted(() => {
  load()
  if (props.pollMs > 0) timer = setInterval(load, props.pollMs)
})
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.ai-banner {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  background: #fafafa;
  margin-bottom: 12px;
  font-size: 12.5px;
  color: #424242;
}
.ai-banner--ok        { border-color: #c8e6c9; background: #f1f8f3; }
.ai-banner--error     { border-color: #ffcdd2; background: #fff5f5; color: #b71c1c; }
.ai-banner--running   { border-color: #bbdefb; background: #f3f8ff; }
.ai-banner--never_ran { border-color: #cfd8dc; background: #f5f7f8; color: #546e7a; }

.ai-banner__icon { line-height: 0; padding-top: 2px; }
.ai-banner__body { flex: 1; }
.ai-banner__title {
  font-size: 13px;
  font-weight: 700;
  color: #212121;
  display: flex; align-items: center; gap: 8px;
}
.ai-banner__health-tag {
  font-size: 10.5px; font-weight: 700;
  padding: 1px 7px; border-radius: 10px;
  letter-spacing: .2px;
}
.ai-banner__health-tag--ok        { background: #e8f5e9; color: #2e7d32; }
.ai-banner__health-tag--error     { background: #ffebee; color: #c62828; }
.ai-banner__health-tag--running   { background: #e3f2fd; color: #1565c0; }
.ai-banner__health-tag--never_ran { background: #eceff1; color: #546e7a; }
.ai-banner__health-tag--unknown   { background: #eceff1; color: #546e7a; }

.ai-banner__meta {
  margin-top: 2px;
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 6px;
  color: #616161;
  font-size: 12px;
}
.ai-banner__meta .q-icon { vertical-align: -2px; margin-right: 2px; }
.ai-banner__sep { color: #bdbdbd; }
.ai-banner__alert {
  margin-top: 6px;
  font-size: 12px;
  color: #b71c1c;
  font-weight: 500;
}
.ai-banner__link {
  color: #b71c1c;
  text-decoration: underline;
}
.ai-banner__btn { align-self: center; }
</style>
