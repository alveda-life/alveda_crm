<template>
  <q-page class="q-pa-md">

    <AiAutoGenBanner v-if="feedbackType === 'daily'"   job-id="operator_daily_feedback" />
    <AiAutoGenBanner v-if="feedbackType === 'weekly'"  job-id="operator_weekly_feedback" />

    <!-- Filters -->
    <div class="row items-center q-gutter-sm q-mb-md">
      <q-btn-toggle
        v-model="feedbackType"
        :options="[
          { label: 'Daily', value: 'daily' },
          { label: 'Weekly', value: 'weekly' },
          { label: 'Per Call', value: 'per_call' },
        ]"
        toggle-color="primary"
        rounded unelevated dense
        @update:model-value="onTypeChange"
      />
      <q-select
        v-if="authStore.isAdmin"
        v-model="selectedOperator"
        :options="operatorOptions"
        emit-value map-options outlined dense clearable
        placeholder="All Operators"
        style="min-width:200px;"
        @update:model-value="onTypeChange"
      />
      <q-space />
      <q-btn v-if="authStore.isAdmin && feedbackType !== 'per_call'" unelevated color="primary" icon="auto_awesome" label="Generate"
        @click="showGenerateDialog = true" style="border-radius:8px;" />
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex flex-center q-pa-xl">
      <q-spinner-dots size="40px" color="primary" />
    </div>

    <!-- ═══ Per-call view ═══ -->
    <template v-else-if="feedbackType === 'per_call'">
      <div v-if="!calls.length" class="flex flex-center q-pa-xl" style="min-height:300px;">
        <div class="text-center">
          <q-icon name="phone_missed" size="64px" color="grey-4" />
          <div class="text-h6 text-grey-5 q-mt-md">No calls found</div>
        </div>
      </div>

      <div v-else class="call-feedback-list">
        <div v-for="call in calls" :key="call.id"
          class="call-fb-card q-mb-sm"
          :class="call.summary_status === 'done' ? 'call-fb-ready' : 'call-fb-pending'"
          @click="call.summary_status === 'done' ? openCallDetail(call) : null"
          :style="call.summary_status === 'done' ? 'cursor:pointer' : 'cursor:default'"
        >
          <div class="row items-center q-gutter-sm">
            <q-icon :name="call.summary_status === 'done' ? 'check_circle' : 'hourglass_empty'"
              :color="call.summary_status === 'done' ? 'green' : 'orange'" size="20px" />

            <span class="text-caption text-grey-7">{{ fmtDatetimeIST(call.date) }}</span>

            <router-link :to="`/partners/${call.partner}`" @click.stop class="partner-link">
              {{ call.partner_name }}
            </router-link>

            <q-chip v-if="authStore.isAdmin && call.created_by_detail" dense size="sm" color="grey-2" text-color="grey-8">
              {{ call.created_by_detail.full_name || call.created_by_detail.username }}
            </q-chip>

            <q-chip v-if="call.call_duration" dense size="sm" outline color="grey-5" style="font-size:11px;">
              {{ fmtDuration(call.call_duration) }}
            </q-chip>

            <q-space />

            <!-- Scores or pending badge -->
            <template v-if="call.summary_status === 'done' && call.quality_overall != null">
              <div class="row q-gutter-xs">
                <div v-for="dim in callScoreDims" :key="dim.key" class="call-score-chip"
                  :style="showScores ? scoreStyle(call['quality_' + dim.key]) : 'color:#546E7A;background:#ECEFF1'">
                  <q-icon :name="dim.icon" size="11px" :class="showScores ? 'q-mr-xs' : ''" />
                  <span v-if="showScores">{{ call['quality_' + dim.key] ?? '—' }}</span>
                  <q-tooltip>{{ dim.label }}<template v-if="showScores">: {{ call['quality_' + dim.key + '_comment'] || '—' }}</template></q-tooltip>
                </div>
              </div>
            </template>
            <q-chip v-else-if="call.summary_status === 'processing'" dense size="sm" color="blue-1" text-color="blue-8">
              <q-spinner-dots size="10px" class="q-mr-xs" /> Processing…
            </q-chip>
            <q-chip v-else dense size="sm" color="orange-1" text-color="orange-9">
              Awaiting feedback
            </q-chip>
          </div>

          <!-- Brief feedback preview -->
          <div v-if="call.quality_feedback && call.summary_status === 'done'"
            class="text-body2 text-grey-7 q-mt-xs q-ml-lg" style="font-size:12px; max-height:36px; overflow:hidden;
            -webkit-mask-image:linear-gradient(to bottom, black 50%, transparent 100%);">
            {{ humanize(call.quality_feedback, call.created_by_detail) }}
          </div>
        </div>
      </div>
    </template>

    <!-- Empty state (daily/weekly) -->
    <div v-else-if="!feedbacks.length" class="flex flex-center q-pa-xl" style="min-height:300px;">
      <div class="text-center">
        <q-icon name="rate_review" size="64px" color="grey-4" />
        <div class="text-h6 text-grey-5 q-mt-md">No feedback yet</div>
        <div class="text-body2 text-grey-4">Feedback is generated daily based on analyzed calls</div>
      </div>
    </div>

    <!-- Feedback list (daily/weekly) -->
    <div v-else class="feedback-list">
      <div v-for="fb in feedbacks" :key="fb.id"
        class="feedback-card q-mb-md"
        :class="{
          'feedback-ack': fb.acknowledged,
          'feedback-unack': !fb.acknowledged,
        }"
        @click="openDetail(fb)"
      >
        <div class="row items-center q-gutter-sm">
          <!-- Type badge -->
          <q-chip dense size="sm" :color="fb.feedback_type === 'weekly' ? 'deep-purple-1' : 'blue-1'"
            :text-color="fb.feedback_type === 'weekly' ? 'deep-purple-9' : 'blue-9'">
            <q-icon :name="fb.feedback_type === 'weekly' ? 'date_range' : 'today'" size="12px" class="q-mr-xs" />
            {{ fb.feedback_type === 'weekly' ? 'Week' : 'Day' }}
          </q-chip>

          <!-- Period -->
          <span class="text-weight-bold" style="font-size:14px;">
            {{ fmtDate(fb.period_start) }}
            <template v-if="fb.period_start !== fb.period_end"> — {{ fmtDate(fb.period_end) }}</template>
          </span>

          <!-- Operator name (admin only) -->
          <q-chip v-if="authStore.isAdmin && fb.operator_detail" dense size="sm" color="grey-2" text-color="grey-8">
            <q-icon name="person" size="12px" class="q-mr-xs" />
            {{ fb.operator_detail.full_name }}
          </q-chip>

          <q-space />

          <!-- Stats -->
          <span class="text-caption text-grey-6">
            {{ fb.calls_analyzed }} calls<template v-if="showScores"> · avg {{ fb.avg_score }}/10</template>
          </span>

          <!-- Acknowledged status -->
          <q-icon v-if="fb.acknowledged" name="check_circle" color="green" size="20px">
            <q-tooltip>Acknowledged {{ fb.acknowledged_at ? fmtDateTime(fb.acknowledged_at) : '' }}</q-tooltip>
          </q-icon>
          <q-icon v-else name="pending" color="orange" size="20px">
            <q-tooltip>Not acknowledged yet</q-tooltip>
          </q-icon>
        </div>

        <!-- Preview -->
        <div class="text-body2 text-grey-7 q-mt-xs" style="max-height:50px; overflow:hidden;
          -webkit-mask-image:linear-gradient(to bottom, black 50%, transparent 100%);">
          {{ humanize(stripMd(fb.content), fb.operator_detail).substring(0, 200) }}
        </div>
      </div>
    </div>

    <!-- Detail dialog -->
    <q-dialog v-model="showDetail" maximized transition-show="slide-up" transition-hide="slide-down">
      <q-card v-if="detailFb" style="max-width:800px; margin:auto;">
        <q-bar class="bg-primary text-white">
          <q-icon name="rate_review" />
          <span>{{ detailFb.feedback_type === 'weekly' ? 'Weekly' : 'Daily' }} Feedback —
            {{ detailFb.operator_detail?.full_name || '' }}
          </span>
          <q-space />
          <q-btn flat dense icon="close" @click="showDetail = false" />
        </q-bar>

        <q-card-section class="q-pa-lg" style="max-height:calc(100vh - 50px); overflow-y:auto;">
          <!-- Header -->
          <div class="row items-center q-gutter-sm q-mb-md">
            <q-chip dense :color="detailFb.feedback_type === 'weekly' ? 'deep-purple-1' : 'blue-1'"
              :text-color="detailFb.feedback_type === 'weekly' ? 'deep-purple-9' : 'blue-9'">
              {{ detailFb.feedback_type === 'weekly' ? 'Week' : 'Day' }}
            </q-chip>
            <span class="text-h6 text-weight-bold">
              {{ fmtDate(detailFb.period_start) }}
              <template v-if="detailFb.period_start !== detailFb.period_end"> — {{ fmtDate(detailFb.period_end) }}</template>
            </span>
            <q-space />
            <span class="text-caption text-grey-6">
              {{ detailFb.calls_analyzed }} calls<template v-if="showScores"> · avg {{ detailFb.avg_score }}/10</template>
            </span>
          </div>

          <!-- Content -->
          <div class="feedback-content" v-html="renderMd(humanize(detailFb.content, detailFb.operator_detail))" />

          <!-- Acknowledge button -->
          <div v-if="!detailFb.acknowledged" class="q-mt-lg text-center">
            <q-btn unelevated color="primary" icon="check" label="Mark as read"
              :loading="ackLoading" @click="acknowledge(detailFb)"
              style="border-radius:8px; padding:8px 32px;" />
          </div>
          <div v-else class="q-mt-lg text-center">
            <q-chip icon="check_circle" color="green-1" text-color="green-9">
              Acknowledged {{ detailFb.acknowledged_at ? fmtDateTime(detailFb.acknowledged_at) : '' }}
            </q-chip>
          </div>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- Per-call detail dialog -->
    <q-dialog v-model="showCallDetail" maximized transition-show="slide-up" transition-hide="slide-down">
      <q-card v-if="detailCall" style="max-width:800px; margin:auto; display:flex; flex-direction:column;">
        <div style="display:flex; align-items:center; gap:8px; padding:8px 16px;
          background:linear-gradient(135deg, #1A237E 0%, #283593 100%); flex-shrink:0;">
          <q-icon name="phone" size="18px" color="white" />
          <span style="font-size:14px; font-weight:700; color:white;">{{ detailCall.partner_name }}</span>
          <q-chip dense size="sm" color="white" text-color="grey-9">{{ fmtDatetimeIST(detailCall.date) }}</q-chip>
          <q-chip v-if="detailCall.call_duration" dense size="sm" color="rgba(255,255,255,0.15)" text-color="white">
            {{ fmtDuration(detailCall.call_duration) }}
          </q-chip>
          <q-space />
          <q-btn flat round dense icon="close" color="white" @click="showCallDetail = false" />
        </div>

        <!-- Audio -->
        <div v-if="detailCall.audio_url" style="padding:6px 16px; background:#ECEFF1; border-bottom:1px solid #CFD8DC;">
          <audio controls :src="detailCall.audio_url" style="width:100%;height:36px;" />
        </div>

        <q-card-section class="q-pa-lg" style="flex:1; overflow-y:auto;">
          <!-- Score cards (admin only) -->
          <div v-if="showScores && detailCall.quality_overall != null" class="row q-gutter-md q-mb-lg">
            <div v-for="dim in callScoreDims" :key="dim.key" class="col"
              style="background:#FAFAFA; border-radius:8px; padding:10px 14px;"
              :style="`border-left:3px solid ${dim.color}`">
              <div class="row items-center justify-between">
                <span style="font-size:12px; font-weight:700; color:#37474F;">
                  <q-icon :name="dim.icon" size="13px" :style="`color:${dim.color}`" class="q-mr-xs" />
                  {{ dim.label }}
                </span>
                <span style="font-size:20px; font-weight:800;" :style="scoreStyle(detailCall['quality_' + dim.key])">
                  {{ detailCall['quality_' + dim.key] }}<span style="font-size:11px;opacity:.5">/10</span>
                </span>
              </div>
              <div style="font-size:12px; color:#78909C; margin-top:4px; line-height:1.5;">
                {{ humanize(detailCall['quality_' + dim.key + '_comment'], detailCall.created_by_detail) }}
              </div>
            </div>
          </div>

          <!-- Operator-only soft criterion summary (no scores) -->
          <div v-else-if="detailCall.quality_overall != null" class="row q-gutter-md q-mb-lg">
            <div v-for="dim in callScoreDims" :key="dim.key" class="col"
              style="background:#FAFAFA; border-radius:8px; padding:10px 14px;"
              :style="`border-left:3px solid ${dim.color}`">
              <span style="font-size:12px; font-weight:700; color:#37474F;">
                <q-icon :name="dim.icon" size="13px" :style="`color:${dim.color}`" class="q-mr-xs" />
                {{ dim.label }}
              </span>
              <div style="font-size:12px; color:#78909C; margin-top:6px; line-height:1.5;">
                {{ humanize(detailCall['quality_' + dim.key + '_comment'], detailCall.created_by_detail) }}
              </div>
            </div>
          </div>

          <!-- Detailed analysis per criterion -->
          <template v-for="dim in callScoreDims" :key="'det-'+dim.key">
            <div v-if="detailCall['quality_' + dim.key + '_detail']" class="q-mb-md">
              <div class="section-title" :style="`color:${dim.color}`">
                <q-icon :name="dim.icon" size="14px" /> {{ dim.label }} — Detailed Analysis
              </div>
              <div class="md-block" v-html="renderMd(humanize(detailCall['quality_' + dim.key + '_detail'], detailCall.created_by_detail))" />
            </div>
          </template>

          <!-- Recommendations -->
          <div v-if="detailCall.quality_recommendations" class="q-mb-lg">
            <div class="section-title" style="color:#7B1FA2;">
              <q-icon name="tips_and_updates" size="14px" /> Recommendations
            </div>
            <div class="md-block reco-block" v-html="renderMd(humanize(detailCall.quality_recommendations, detailCall.created_by_detail))" />
          </div>

          <!-- Summary -->
          <div v-if="detailCall.summary" class="q-mb-lg">
            <div class="section-title"><q-icon name="auto_awesome" size="14px" /> Summary</div>
            <div style="font-size:13px; line-height:1.7; background:#F9FBE7; border-left:3px solid #AED581;
              border-radius:0 8px 8px 0; padding:12px 16px; color:#37474F;">
              {{ humanize(detailCall.summary, detailCall.created_by_detail) }}
            </div>
          </div>

          <!-- Key takeaway -->
          <div v-if="detailCall.quality_feedback" class="q-mb-lg">
            <div class="section-title"><q-icon name="lightbulb" size="14px" color="amber-8" /> Key Takeaway</div>
            <div style="font-size:13px; line-height:1.6; background:#FFF8E1; border-left:3px solid #FFD54F;
              border-radius:0 8px 8px 0; padding:10px 14px; color:#5D4037;">
              {{ humanize(detailCall.quality_feedback, detailCall.created_by_detail) }}
            </div>
          </div>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- Generate dialog (admin) -->
    <q-dialog v-model="showGenerateDialog">
      <q-card style="min-width:350px; border-radius:12px;">
        <q-card-section>
          <div class="text-h6">Generate Feedback</div>
        </q-card-section>
        <q-card-section>
          <q-select v-model="genType" :options="[
            { label: 'Daily', value: 'daily' },
            { label: 'Weekly', value: 'weekly' },
          ]" emit-value map-options outlined dense label="Type" class="q-mb-sm" />
          <q-input v-model="genDate" type="date" outlined dense label="Date" class="q-mb-sm" />
          <q-select v-model="genOperator" :options="operatorOptions" emit-value map-options
            outlined dense clearable label="Operator (all if empty)" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" @click="showGenerateDialog = false" />
          <q-btn unelevated color="primary" label="Generate" :loading="genLoading" @click="doGenerate" />
        </q-card-actions>
      </q-card>
    </q-dialog>

  </q-page>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from 'boot/axios'
import { useAuthStore } from 'src/stores/auth'
import { usePartnersStore } from 'src/stores/partners'
import AiAutoGenBanner from 'components/AiAutoGenBanner.vue'

const authStore = useAuthStore()
const partnersStore = usePartnersStore()

const feedbacks = ref([])
const calls = ref([])
const loading = ref(false)
const feedbackType = ref('daily')
const selectedOperator = ref(null)
const showDetail = ref(false)
const detailFb = ref(null)
const ackLoading = ref(false)
const showCallDetail = ref(false)
const detailCall = ref(null)

const showGenerateDialog = ref(false)
const genType = ref('daily')
const genDate = ref(new Date().toISOString().split('T')[0])
const genOperator = ref(null)
const genLoading = ref(false)

const operatorOptions = computed(() =>
  partnersStore.users.map(u => ({ label: u.full_name || u.username, value: u.id }))
)

// Operators must NOT see numeric scores at all (their own or anyone's).
const showScores = computed(() => authStore.isAdmin)

// Display name for the operator who owns the call/feedback.
// Falls back: full_name → username → 'the operator'.
function operatorDisplayName (detail) {
  if (!detail) {
    if (!authStore.isAdmin) {
      return authStore.user?.full_name || authStore.user?.username || 'the operator'
    }
    return 'the operator'
  }
  return detail.full_name || detail.username || 'the operator'
}

// Replace generic "Operator" labels (and any leaked numeric scores for non-admins)
// inside AI-generated text so the operator sees their own name and no marks.
function humanize (text, detail) {
  if (!text) return ''
  let out = String(text)
  const name = operatorDisplayName(detail)

  // Replace standalone role tokens. Order matters — handle compound forms first.
  // "Operator's"
  out = out.replace(/\bOperator['\u2019]s\b/g, `${name}'s`)
  // "Operator:" at start of a quoted/labelled line
  out = out.replace(/(^|[\s>(\[\-\*])Operator:/g, `$1${name}:`)
  // "The operator …" / "the operator …"
  out = out.replace(/\bThe operator\b/g, name)
  out = out.replace(/\bthe operator\b/g, name)
  // Bare "Operator " inside running text
  out = out.replace(/\bOperator\b/g, name)

  if (!showScores.value) {
    // Strip patterns like "6/10", "6 / 10", "Score: 6/10", "(6/10)".
    out = out.replace(/\(?\s*\b\d{1,2}\s*\/\s*10\b\s*\)?/g, '')
    out = out.replace(/\b(Score|Rating)\s*[:\-]?\s*\d{1,2}(\s*\/\s*10)?/gi, '')
    // collapse double spaces left behind
    out = out.replace(/[ \t]{2,}/g, ' ').replace(/\s+([.,;:!?])/g, '$1')
  }

  return out
}

const callScoreDims = [
  { key: 'survey',      label: 'Survey',      icon: 'quiz',      color: '#1565C0' },
  { key: 'explanation', label: 'Explanation',  icon: 'school',    color: '#E65100' },
  { key: 'overall',     label: 'Overall',      icon: 'star_rate', color: '#2E7D32' },
]

function fmtDate(dt) {
  return new Date(dt + 'T00:00:00').toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
}

function fmtDateTime(dt) {
  return new Date(dt).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function stripMd(text) {
  if (!text) return ''
  return text.replace(/[#*_>`\[\]]/g, '').replace(/\n+/g, ' ').trim()
}

function renderMd(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/^>\s?(.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/<\/blockquote>\n<blockquote>/g, '<br>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^- \[x\] (.+)$/gm, '<li class="checklist done">✅ $1</li>')
    .replace(/^- \[ \] (.+)$/gm, '<li class="checklist">⬜ $1</li>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`)
    .split(/\n{2,}/)
    .map(b => {
      b = b.trim()
      if (!b) return ''
      if (/^<(h[1-3]|ul|ol|blockquote)/.test(b)) return b
      return `<p>${b.replace(/\n/g, '<br>')}</p>`
    })
    .join('\n')
}

function onTypeChange() {
  if (feedbackType.value === 'per_call') {
    loadCalls()
  } else {
    loadFeedback()
  }
}

async function loadFeedback() {
  loading.value = true
  try {
    const params = { type: feedbackType.value }
    if (selectedOperator.value) params.operator = selectedOperator.value
    const res = await api.get('/operator-feedback/', { params })
    feedbacks.value = res.data
  } finally {
    loading.value = false
  }
}

async function loadCalls() {
  loading.value = true
  try {
    const params = { has_audio: 'true', ordering: '-date', page_size: 100 }
    if (selectedOperator.value) {
      params.created_by = selectedOperator.value
    } else if (!authStore.isAdmin) {
      params.created_by = authStore.user?.id
    }
    const res = await api.get('/contacts/', { params })
    calls.value = res.data.results || res.data
  } finally {
    loading.value = false
  }
}

function openDetail(fb) {
  detailFb.value = fb
  showDetail.value = true
}

function openCallDetail(call) {
  detailCall.value = call
  showCallDetail.value = true
}

function scoreStyle(s) {
  if (s == null) return 'color:#9E9E9E'
  if (s >= 8) return 'color:#2E7D32'
  if (s >= 6) return 'color:#F57F17'
  return 'color:#C62828'
}

function fmtDatetimeIST(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-US', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
    timeZone: 'Asia/Kolkata',
  })
}

function fmtDuration(secs) {
  if (!secs) return '—'
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

async function acknowledge(fb) {
  ackLoading.value = true
  try {
    const res = await api.post(`/operator-feedback/${fb.id}/acknowledge/`)
    fb.acknowledged = true
    fb.acknowledged_at = res.data.acknowledged_at
    detailFb.value = { ...fb }
  } finally {
    ackLoading.value = false
  }
}

async function doGenerate() {
  genLoading.value = true
  try {
    await api.post('/operator-feedback/generate/', {
      type: genType.value,
      date: genDate.value,
      operator_id: genOperator.value || undefined,
    })
    showGenerateDialog.value = false
    await loadFeedback()
  } finally {
    genLoading.value = false
  }
}

onMounted(() => {
  loadFeedback()
  if (!partnersStore.users.length) partnersStore.fetchUsers()
})
</script>

<style scoped>
.feedback-card {
  background: #fff;
  border: 1px solid #E0E0E0;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.15s;
}
.feedback-card:hover {
  border-color: #BDBDBD;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.feedback-ack {
  border-left: 4px solid #43A047;
  background: #FAFFF9;
}
.feedback-unack {
  border-left: 4px solid #FF9800;
  background: #FFFCF5;
}
.feedback-content {
  background: #FAFAFA;
  border-radius: 10px;
  padding: 20px 24px;
  font-size: 14px;
  line-height: 1.8;
  color: #212121;
}
.feedback-content :deep(h1), .feedback-content :deep(h2), .feedback-content :deep(h3) {
  font-size: 15px; font-weight: 700; margin: 16px 0 8px; color: #212121;
}
.feedback-content :deep(h2) { font-size: 16px; border-bottom: 1px solid #E0E0E0; padding-bottom: 4px; }
.feedback-content :deep(ul) { margin: 4px 0 12px 18px; padding: 0; }
.feedback-content :deep(li) { margin-bottom: 6px; }
.feedback-content :deep(strong) { font-weight: 700; color: #1565C0; }
.feedback-content :deep(blockquote) {
  border-left: 3px solid #90CAF9;
  margin: 6px 0 6px 8px;
  padding: 4px 10px;
  background: #E3F2FD;
  border-radius: 0 6px 6px 0;
  font-style: italic;
  color: #1565C0;
  font-size: 13px;
}
.feedback-content :deep(code) {
  background: #E8EAF6; padding: 1px 5px; border-radius: 3px; font-size: 13px; color: #283593;
}
.feedback-content :deep(p) { margin: 0 0 10px; }
.feedback-content :deep(p:last-child) { margin-bottom: 0; }

/* Per-call cards */
.call-fb-card {
  background: #fff;
  border: 1px solid #E0E0E0;
  border-radius: 10px;
  padding: 10px 14px;
  transition: all 0.15s;
}
.call-fb-card:hover { border-color: #BDBDBD; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
.call-fb-ready { border-left: 3px solid #43A047; }
.call-fb-pending { border-left: 3px solid #FF9800; opacity: 0.85; }

.call-score-chip {
  display: inline-flex; align-items: center;
  font-size: 11px; font-weight: 700;
  background: #F5F5F5; border-radius: 6px;
  padding: 2px 8px; cursor: default;
}

.partner-link { color: #2E7D32; text-decoration: none; font-size: 13px; font-weight: 600; }
.partner-link:hover { text-decoration: underline; }

.section-title {
  font-size: 12px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .5px; color: #546E7A;
  margin-bottom: 6px;
  display: flex; align-items: center; gap: 5px;
}

.md-block {
  font-size: 13px; line-height: 1.6; color: #37474F;
  background: #F5F5F5; border-radius: 8px; padding: 12px 16px;
}
.md-block :deep(h3), .md-block :deep(h4) { font-size: 14px; margin: 10px 0 4px; color: #263238; }
.md-block :deep(blockquote) {
  border-left: 3px solid #90CAF9; margin: 6px 0; padding: 4px 12px;
  background: #E3F2FD; border-radius: 0 6px 6px 0; color: #1565C0; font-style: italic;
}
.md-block :deep(ul) { padding-left: 16px; margin: 4px 0; }
.md-block :deep(li) { margin: 2px 0; }
.md-block :deep(strong) { color: #263238; }
.md-block :deep(p) { margin: 4px 0; }

.reco-block { background: #F3E5F5; border: 1px solid #CE93D8; }
.reco-block :deep(blockquote) { border-left-color: #AB47BC; background: #EDE7F6; color: #6A1B9A; }
</style>
