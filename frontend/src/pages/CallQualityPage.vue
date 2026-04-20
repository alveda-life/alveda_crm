<template>
  <q-page class="q-pa-md">

    <!-- Filters row -->
    <div class="row items-center q-gutter-sm q-mb-md">
      <q-select
        v-model="filters.operator"
        :options="operatorOptions"
        emit-value map-options outlined dense clearable
        placeholder="All Operators"
        style="min-width:180px;"
        @update:model-value="loadCalls"
      />
      <q-select
        v-model="filters.minScore"
        :options="scoreFilterOptions"
        emit-value map-options outlined dense clearable
        placeholder="All Scores"
        style="min-width:160px;"
        @update:model-value="loadCalls"
      />
      <q-input
        v-model="filters.dateFrom"
        type="date" outlined dense
        label="From"
        style="min-width:150px;"
        @update:model-value="loadCalls"
      />
      <q-input
        v-model="filters.dateTo"
        type="date" outlined dense
        label="To"
        style="min-width:150px;"
        @update:model-value="loadCalls"
      />
      <q-btn
        :outline="!onlyMine"
        :color="onlyMine ? 'primary' : 'grey-7'"
        :icon="onlyMine ? 'person' : 'person_outline'"
        label="Assigned to Me"
        dense unelevated no-caps
        style="border-radius:8px;font-size:13px;"
        @click="toggleMine"
      />
      <q-space />
      <q-chip icon="phone" color="primary" text-color="white">
        {{ calls.length }} calls
      </q-chip>
    </div>

    <!-- Table -->
    <q-table
      flat bordered
      :rows="calls"
      :columns="columns"
      row-key="id"
      :loading="loading"
      :pagination="{ rowsPerPage: 25 }"
      style="border-radius:12px;"
      @row-click="(evt, row) => openDetail(row)"
      class="quality-table"
    >
      <template #body-cell-partner_name="props">
        <q-td :props="props">
          <router-link :to="`/partners/${props.row.partner}`" class="text-primary text-weight-medium"
            style="text-decoration:none;" @click.stop>
            {{ props.value }}
          </router-link>
        </q-td>
      </template>

      <template #body-cell-partner_type="props">
        <q-td :props="props">
          <q-chip dense size="xs" :color="props.value === 'Medic' ? 'teal-2' : 'blue-grey-1'"
            :text-color="props.value === 'Medic' ? 'teal-9' : 'blue-grey-8'">
            {{ props.value }}
          </q-chip>
        </q-td>
      </template>

      <template #body-cell-call_number="props">
        <q-td :props="props" class="text-center">
          <span style="font-weight:600;">#{{ props.value }}</span>
        </q-td>
      </template>

      <template #body-cell-partner_paid_orders="props">
        <q-td :props="props" class="text-center">
          <span :style="props.value > 0 ? 'color:#2E7D32; font-weight:600;' : 'color:#BDBDBD;'">{{ props.value }}</span>
        </q-td>
      </template>

      <template #body-cell-partner_sets="props">
        <q-td :props="props" class="text-center">
          <span :style="props.value > 0 ? 'color:#1565C0; font-weight:600;' : 'color:#BDBDBD;'">{{ props.value }}</span>
        </q-td>
      </template>

      <template #body-cell-quality_survey="props">
        <q-td :props="props">
          <span v-if="props.value != null" class="score-badge" :style="scoreStyle(props.value)">{{ props.value }}</span>
          <span v-else class="text-grey-4">—</span>
        </q-td>
      </template>
      <template #body-cell-quality_explanation="props">
        <q-td :props="props">
          <span v-if="props.value != null" class="score-badge" :style="scoreStyle(props.value)">{{ props.value }}</span>
          <span v-else class="text-grey-4">—</span>
        </q-td>
      </template>
      <template #body-cell-quality_overall="props">
        <q-td :props="props">
          <span v-if="props.value != null" class="score-badge" :style="scoreStyle(props.value)">{{ props.value }}</span>
          <span v-else class="text-grey-4">—</span>
        </q-td>
      </template>
      <template #body-cell-avg="props">
        <q-td :props="props">
          <span v-if="props.value" class="score-badge" :style="scoreStyle(props.value)"
            style="font-size:13px; padding:3px 10px;">
            {{ props.value }}
          </span>
          <span v-else class="text-grey-4">—</span>
        </q-td>
      </template>
      <template #body-cell-summary_status="props">
        <q-td :props="props">
          <q-chip v-if="props.value === 'done'" dense size="xs" color="green-1" text-color="green-9">Done</q-chip>
          <q-chip v-else-if="props.value === 'processing' || props.value === 'pending'" dense size="xs" color="blue-1" text-color="blue-9">
            <q-spinner-dots size="10px" class="q-mr-xs" /> Processing
          </q-chip>
          <q-chip v-else-if="props.value === 'failed'" dense size="xs" color="red-1" text-color="red-9">Failed</q-chip>
          <span v-else class="text-grey-4">—</span>
        </q-td>
      </template>
      <template #body-cell-duration="props">
        <q-td :props="props">
          {{ props.value ? fmtDuration(props.value) : '—' }}
        </q-td>
      </template>
    </q-table>

    <!-- Detail dialog -->
    <q-dialog v-model="showDetail" maximized transition-show="slide-up" transition-hide="slide-down">
      <q-card v-if="detailCall" style="max-width:900px; margin:auto;">
        <q-bar class="bg-primary text-white">
          <q-icon name="analytics" />
          <span>Call Quality — {{ detailCall.partner_name }}</span>
          <q-space />
          <q-btn flat dense icon="close" @click="showDetail = false" />
        </q-bar>

        <q-card-section class="q-pa-lg" style="max-height:calc(100vh - 50px); overflow-y:auto;">
          <!-- Header info -->
          <div class="row items-center q-gutter-md q-mb-lg">
            <div>
              <div class="text-h6 text-weight-bold">{{ detailCall.partner_name }}</div>
              <div class="text-caption text-grey-6">
                {{ fmtDate(detailCall.date) }}
                <span v-if="detailCall.created_by_detail"> · {{ detailCall.created_by_detail.full_name }}</span>
                <span v-if="detailCall.call_duration"> · {{ fmtDuration(detailCall.call_duration) }}</span>
                · Call #{{ detailCall.call_number }}
              </div>
            </div>
          </div>

          <!-- Partner info -->
          <div class="q-mb-lg" style="display:flex; gap:12px; flex-wrap:wrap;">
            <q-chip dense icon="person" :color="detailCall.partner_type === 'Medic' ? 'teal-2' : 'blue-grey-1'"
              :text-color="detailCall.partner_type === 'Medic' ? 'teal-9' : 'blue-grey-8'">
              {{ detailCall.partner_type || '—' }}
            </q-chip>
            <q-chip dense icon="category" color="grey-2" text-color="grey-8">
              {{ detailCall.partner_category || '—' }}
            </q-chip>
            <q-chip dense icon="sell" color="green-1" text-color="green-9">
              Sales: {{ detailCall.partner_paid_orders ?? 0 }}
            </q-chip>
            <q-chip dense icon="inventory_2" color="blue-1" text-color="blue-9">
              Sets: {{ detailCall.partner_sets ?? 0 }}
            </q-chip>
            <q-chip dense icon="flag" color="orange-1" text-color="orange-9">
              {{ detailCall.partner_stage || '—' }}
            </q-chip>
          </div>

          <!-- Audio -->
          <div v-if="detailCall.audio_url" class="q-mb-lg">
            <div class="section-label q-mb-xs"><q-icon name="graphic_eq" size="14px" /> Audio Recording</div>
            <audio controls :src="detailCall.audio_url" style="width:100%; height:40px;" />
          </div>

          <!-- Score overview -->
          <div v-if="detailCall.quality_overall != null" class="q-mb-md">
            <div class="section-label q-mb-sm"><q-icon name="analytics" size="14px" /> Quality Scores</div>
            <div class="row q-gutter-md">
              <div v-for="dim in scoreDimensions" :key="dim.key" class="score-card" style="flex:1;">
                <div class="row items-center justify-between q-mb-xs">
                  <div class="row items-center q-gutter-xs">
                    <q-icon :name="dim.icon" size="16px" :style="`color:${dim.color}`" />
                    <span style="font-weight:600; font-size:13px;">{{ dim.label }}</span>
                  </div>
                  <span class="score-badge" :style="scoreStyle(detailCall['quality_' + dim.key])"
                    style="font-size:14px; padding:3px 10px;">
                    {{ detailCall['quality_' + dim.key] }}/10
                  </span>
                </div>
                <div style="font-size:12px; color:#616161; line-height:1.5;">
                  {{ detailCall['quality_' + dim.key + '_comment'] }}
                </div>
              </div>
            </div>
          </div>

          <!-- Errors Found (top of analysis) -->
          <div v-if="detailCall.quality_errors_found" class="q-mb-md">
            <div class="errors-banner">
              <div class="errors-head">
                <q-icon name="error" size="18px" color="red-6" />
                <span>Errors Found in This Call</span>
              </div>
              <div class="errors-body" v-html="renderColored(detailCall.quality_errors_found)" />
            </div>
          </div>

          <!-- Improvement Plan -->
          <div v-if="detailCall.quality_improvement_plan" class="q-mb-md">
            <div class="improve-banner">
              <div class="improve-head">
                <q-icon name="trending_up" size="18px" color="green-7" />
                <span>Improvement Plan</span>
              </div>
              <div class="improve-body" v-html="renderColored(detailCall.quality_improvement_plan)" />
            </div>
          </div>

          <!-- Detailed analysis per criterion -->
          <div v-for="dim in scoreDimensions" :key="'detail-'+dim.key" class="q-mb-md">
            <div v-if="detailCall['quality_' + dim.key + '_detail']">
              <div class="criterion-detail-header" :style="`border-left-color:${dim.color};`">
                <div class="row items-center q-gutter-xs">
                  <q-icon :name="dim.icon" size="18px" :style="`color:${dim.color}`" />
                  <span style="font-weight:700; font-size:14px;">{{ dim.label }} — Detailed Analysis</span>
                  <span class="score-badge q-ml-sm" :style="scoreStyle(detailCall['quality_' + dim.key])"
                    style="font-size:12px; padding:2px 8px;">
                    {{ detailCall['quality_' + dim.key] }}/10
                  </span>
                </div>
              </div>
              <div class="detail-block criterion-detail-body" v-html="renderColored(detailCall['quality_' + dim.key + '_detail'])" />
            </div>
          </div>

          <!-- Operator Recommendations -->
          <div v-if="detailCall.quality_recommendations" class="q-mb-lg">
            <div class="section-label q-mb-xs"><q-icon name="lightbulb" size="14px" color="amber-8" /> Recommendations for Operator</div>
            <div class="detail-block recommendations-block" v-html="renderColored(detailCall.quality_recommendations)" />
          </div>

          <!-- AI Summary -->
          <div v-if="detailCall.summary" class="q-mb-lg">
            <div class="section-label q-mb-xs"><q-icon name="auto_awesome" size="14px" /> AI Summary</div>
            <div class="detail-block" v-html="renderMd(detailCall.summary)" />
          </div>

          <!-- Brief coaching note -->
          <div v-if="detailCall.quality_feedback" class="q-mb-lg">
            <div class="section-label q-mb-xs"><q-icon name="rate_review" size="14px" /> Key Takeaway</div>
            <div class="detail-block feedback-block" v-html="renderMd(detailCall.quality_feedback)" />
          </div>

          <!-- Transcript -->
          <div v-if="detailCall.diarized_transcript || detailCall.transcription">
            <div class="row items-center justify-between q-mb-xs">
              <div class="section-label"><q-icon name="article" size="14px" /> Transcript</div>
              <q-btn flat dense size="sm" :icon="showTranscript ? 'expand_less' : 'expand_more'"
                :label="showTranscript ? 'Hide' : 'Show'"
                color="grey-6" @click="showTranscript = !showTranscript" />
            </div>
            <div v-if="showTranscript" style="max-height:480px; overflow-y:auto; background:#FAFAFA; border-radius:8px; padding:4px;">
              <TranscriptChat
                :diarized="detailCall.diarized_transcript"
                :raw="detailCall.transcription"
                compact
              />
            </div>
          </div>
        </q-card-section>
      </q-card>
    </q-dialog>

  </q-page>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from 'boot/axios'
import { usePartnersStore } from 'src/stores/partners'
import { useAuthStore } from 'src/stores/auth'
import TranscriptChat from 'src/components/TranscriptChat.vue'

const partnersStore = usePartnersStore()
const authStore     = useAuthStore()

const calls = ref([])
const loading = ref(false)
const showDetail = ref(false)
const detailCall = ref(null)
const showTranscript = ref(false)
const onlyMine = ref(false)

const filters = ref({
  operator: null,
  minScore: null,
  dateFrom: '',
  dateTo: '',
})

function toggleMine() {
  onlyMine.value = !onlyMine.value
  filters.value.operator = onlyMine.value ? authStore.user?.id : null
  loadCalls()
}

const scoreDimensions = [
  { key: 'survey', label: 'Survey', icon: 'record_voice_over', color: '#1565C0' },
  { key: 'explanation', label: 'Explanation', icon: 'school', color: '#E65100' },
  { key: 'overall', label: 'Overall', icon: 'star', color: '#2E7D32' },
]

const scoreFilterOptions = [
  { label: 'Low (1–4)', value: 'low' },
  { label: 'Medium (5–7)', value: 'medium' },
  { label: 'High (8–10)', value: 'high' },
]

const operatorOptions = computed(() =>
  partnersStore.users.map(u => ({ label: u.full_name || u.username, value: u.id }))
)

const columns = [
  { name: 'date', label: 'Date', field: 'date', sortable: true, format: v => {
    const d = new Date(v)
    return d.toLocaleDateString('en-US', { day:'numeric', month:'short', year:'numeric', timeZone:'Asia/Kolkata' })
      + ' ' + d.toLocaleTimeString('en-US', { hour:'2-digit', minute:'2-digit', hour12:false, timeZone:'Asia/Kolkata' })
  }},
  { name: 'partner_name', label: 'Partner', field: 'partner_name', sortable: true },
  { name: 'partner_type', label: 'Type', field: 'partner_type', sortable: true },
  { name: 'partner_category', label: 'Category', field: 'partner_category', sortable: true },
  { name: 'call_number', label: 'Call #', field: 'call_number', sortable: true, align: 'center' },
  { name: 'partner_paid_orders', label: 'Sales', field: 'partner_paid_orders', sortable: true, align: 'center' },
  { name: 'partner_sets', label: 'Sets', field: 'partner_sets', sortable: true, align: 'center' },
  { name: 'operator', label: 'Operator', field: r => r.created_by_detail?.full_name || '—', sortable: true },
  { name: 'duration', label: 'Duration', field: 'call_duration', sortable: true },
  { name: 'quality_survey', label: 'Survey', field: 'quality_survey', sortable: true, align: 'center' },
  { name: 'quality_explanation', label: 'Expl.', field: 'quality_explanation', sortable: true, align: 'center' },
  { name: 'quality_overall', label: 'Overall', field: 'quality_overall', sortable: true, align: 'center' },
  { name: 'avg', label: 'Avg', field: r => avgScore(r), sortable: true, align: 'center' },
  { name: 'summary_status', label: 'Status', field: 'summary_status', sortable: true, align: 'center' },
]

function avgScore(row) {
  const vals = [row.quality_survey, row.quality_explanation, row.quality_overall].filter(v => v != null)
  if (!vals.length) return null
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length * 10) / 10
}

function scoreStyle(score) {
  if (score == null) return ''
  if (score >= 8) return 'color:#2E7D32; background:#E8F5E9;'
  if (score >= 5) return 'color:#E65100; background:#FFF3E0;'
  return 'color:#C62828; background:#FFEBEE;'
}

function fmtDuration(secs) {
  if (!secs) return ''
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function fmtDate(dt) {
  return new Date(dt).toLocaleString('en-US', { day:'numeric', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' })
}

function renderMd(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/^&gt;\s?(.+)$/gm, '<blockquote>$1</blockquote>')
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

// Renders text that contains :::ok / :::bad / :::fix semantic blocks
// into colored callouts. Each block is converted to a styled div, then
// the surrounding text is rendered with renderMd().
const BLOCK_META = {
  ok:  { cls: 'qb qb-ok',  icon: '✅', label: 'What worked' },
  bad: { cls: 'qb qb-bad', icon: '❌', label: 'What went wrong' },
  fix: { cls: 'qb qb-fix', icon: '💡', label: 'Say this instead' },
}

function renderColored(text) {
  if (!text) return ''
  const blocks = []
  const placeholder = i => `@@QB_BLOCK_${i}@@`

  // Allow the markers to be indented (AI nests them inside markdown lists).
  // Match an opening "[indent]:::kind" line and a closing "[indent]:::" line,
  // then dedent the body so the inner markdown renders properly.
  const re = /(^|\n)([ \t]*):::[ \t]*(ok|bad|fix)[ \t]*\n([\s\S]*?)\n[ \t]*:::[ \t]*(?=\n|$)/g

  const stripped = text.replace(re, (_, lead, indent, kind, rawBody) => {
    const meta = BLOCK_META[kind] || BLOCK_META.ok
    // Strip the same leading indent from each body line (best-effort dedent)
    const dedent = indent ? new RegExp('^' + indent.replace(/[\\^$.*+?()[\]{}|]/g, '\\$&'), 'gm') : null
    const body = dedent ? rawBody.replace(dedent, '') : rawBody
    const inner = renderMd(body.trim())
    const html = `<div class="${meta.cls}"><div class="qb-head"><span class="qb-ico">${meta.icon}</span><span class="qb-label">${meta.label}</span></div><div class="qb-body">${inner}</div></div>`
    blocks.push(html)
    return `${lead}${placeholder(blocks.length - 1)}`
  })

  let html = renderMd(stripped)
  blocks.forEach((blk, i) => {
    // The placeholder may end up wrapped in <p>, <li>, etc. — unwrap defensively.
    html = html
      .replace(new RegExp(`<p>\\s*${placeholder(i)}\\s*</p>`, 'g'), blk)
      .replace(new RegExp(placeholder(i), 'g'), blk)
  })
  return html
}

async function loadCalls() {
  loading.value = true
  try {
    const params = { has_audio: 'true', ordering: '-date' }
    if (filters.value.operator) params.created_by = filters.value.operator
    if (filters.value.dateFrom) params.date_after = filters.value.dateFrom
    if (filters.value.dateTo) params.date_before = filters.value.dateTo
    const res = await api.get('/contacts/', { params })
    let data = res.data.results || res.data

    if (filters.value.minScore === 'low') data = data.filter(c => c.quality_overall != null && c.quality_overall <= 4)
    else if (filters.value.minScore === 'medium') data = data.filter(c => c.quality_overall != null && c.quality_overall >= 5 && c.quality_overall <= 7)
    else if (filters.value.minScore === 'high') data = data.filter(c => c.quality_overall != null && c.quality_overall >= 8)

    calls.value = data
  } finally {
    loading.value = false
  }
}

function openDetail(row) {
  detailCall.value = row
  showTranscript.value = false
  showDetail.value = true
}

onMounted(() => {
  loadCalls()
  if (!partnersStore.users.length) partnersStore.fetchUsers()
})
</script>

<style scoped>
.score-badge {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  min-width: 28px;
  text-align: center;
}
.score-card {
  background: #FAFAFA;
  border: 1px solid #E0E0E0;
  border-radius: 10px;
  padding: 12px 14px;
}
.section-label {
  font-size: 12px;
  font-weight: 700;
  color: #616161;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.detail-block {
  background: #FAFAFA;
  border-radius: 8px;
  padding: 14px 16px;
  font-size: 14px;
  line-height: 1.7;
  color: #212121;
}
.detail-block :deep(h1), .detail-block :deep(h2), .detail-block :deep(h3) {
  font-size: 14px; font-weight: 700; margin: 12px 0 6px; color: #212121;
}
.detail-block :deep(ul) { margin: 4px 0 8px 18px; padding: 0; }
.detail-block :deep(li) { margin-bottom: 4px; }
.detail-block :deep(strong) { font-weight: 700; }
.detail-block :deep(code) {
  background: #E8EAF6; padding: 1px 5px; border-radius: 3px; font-size: 13px; color: #283593;
}
.detail-block :deep(p) { margin: 0 0 8px; }
.detail-block :deep(p:last-child) { margin-bottom: 0; }
.criterion-detail-header {
  border-left: 4px solid #1565C0;
  padding: 8px 12px;
  background: #FAFAFA;
  border-radius: 0 8px 0 0;
  margin-bottom: 0;
}
.criterion-detail-body {
  border-radius: 0 0 8px 8px;
  border-top: none;
  margin-bottom: 4px;
}
.criterion-detail-body :deep(blockquote) {
  border-left: 3px solid #90CAF9;
  margin: 6px 0 6px 8px;
  padding: 4px 10px;
  background: #E3F2FD;
  border-radius: 0 6px 6px 0;
  font-style: italic;
  color: #1565C0;
  font-size: 13px;
}
.recommendations-block {
  background: #E8F5E9;
  border-left: 3px solid #43A047;
}
.recommendations-block :deep(blockquote) {
  border-left: 3px solid #81C784;
  margin: 6px 0 6px 8px;
  padding: 4px 10px;
  background: #C8E6C9;
  border-radius: 0 6px 6px 0;
  font-style: italic;
  color: #2E7D32;
  font-size: 13px;
}
.recommendations-block :deep(.checklist) {
  list-style: none;
  margin-left: -18px;
}
.feedback-block {
  background: #FFF8E1;
  border-left: 3px solid #FFB300;
}
.detail-block :deep(blockquote) {
  border-left: 3px solid #BDBDBD;
  margin: 6px 0 6px 8px;
  padding: 4px 10px;
  background: #F5F5F5;
  border-radius: 0 6px 6px 0;
  font-style: italic;
  color: #424242;
  font-size: 13px;
}
.quality-table :deep(tbody tr) {
  cursor: pointer;
}
.quality-table :deep(tbody tr:hover) {
  background: #F5F5F5;
}

/* ── Errors Found banner (top of detail dialog) ─────────────────── */
.errors-banner {
  background: #FFEBEE;
  border: 1px solid #EF9A9A;
  border-left: 4px solid #C62828;
  border-radius: 8px;
  padding: 12px 16px;
}
.errors-head {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 700; color: #B71C1C;
  text-transform: uppercase; letter-spacing: 0.4px;
  margin-bottom: 8px;
}
.errors-body {
  font-size: 13.5px; line-height: 1.6; color: #2E2E2E;
}
.errors-body :deep(ol),
.errors-body :deep(ul) { padding-left: 20px; margin: 4px 0; }
.errors-body :deep(li) { margin-bottom: 6px; }
.errors-body :deep(strong) { color: #B71C1C; }

/* ── Improvement Plan banner ────────────────────────────────────── */
.improve-banner {
  background: #E8F5E9;
  border: 1px solid #A5D6A7;
  border-left: 4px solid #2E7D32;
  border-radius: 8px;
  padding: 12px 16px;
}
.improve-head {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 700; color: #1B5E20;
  text-transform: uppercase; letter-spacing: 0.4px;
  margin-bottom: 8px;
}
.improve-body {
  font-size: 13.5px; line-height: 1.6; color: #2E2E2E;
}
.improve-body :deep(strong) { color: #1B5E20; }
.improve-body :deep(h3) {
  font-size: 13px; font-weight: 700; color: #1B5E20;
  margin: 10px 0 6px;
}

/* ── Coloured semantic blocks (:::ok / :::bad / :::fix) ─────────── */
.detail-block :deep(.qb),
.errors-body  :deep(.qb),
.improve-body :deep(.qb),
.recommendations-block :deep(.qb) {
  border-radius: 8px;
  padding: 8px 12px 10px;
  margin: 8px 0;
  border: 1px solid transparent;
}
.detail-block :deep(.qb-head),
.errors-body  :deep(.qb-head),
.improve-body :deep(.qb-head),
.recommendations-block :deep(.qb-head) {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.4px; margin-bottom: 6px; opacity: 0.85;
}
.detail-block :deep(.qb-body),
.errors-body  :deep(.qb-body),
.improve-body :deep(.qb-body),
.recommendations-block :deep(.qb-body) {
  font-size: 13.5px; line-height: 1.55;
}
.detail-block :deep(.qb-body p),
.errors-body  :deep(.qb-body p),
.improve-body :deep(.qb-body p),
.recommendations-block :deep(.qb-body p) {
  margin: 0 0 4px;
}
.detail-block :deep(.qb-body blockquote),
.errors-body  :deep(.qb-body blockquote),
.improve-body :deep(.qb-body blockquote),
.recommendations-block :deep(.qb-body blockquote) {
  background: rgba(255,255,255,0.55);
  border-left-width: 3px;
  margin: 4px 0;
  padding: 4px 10px;
  font-style: normal;
  color: #1F1F1F;
  font-size: 13px;
}

/* OK — light green */
.detail-block :deep(.qb-ok),
.errors-body  :deep(.qb-ok),
.improve-body :deep(.qb-ok),
.recommendations-block :deep(.qb-ok) {
  background: #E8F5E9;
  border-color: #A5D6A7;
  color: #1B5E20;
}
.detail-block :deep(.qb-ok blockquote),
.improve-body :deep(.qb-ok blockquote),
.recommendations-block :deep(.qb-ok blockquote) {
  border-left-color: #66BB6A;
}

/* BAD — light red */
.detail-block :deep(.qb-bad),
.errors-body  :deep(.qb-bad),
.improve-body :deep(.qb-bad),
.recommendations-block :deep(.qb-bad) {
  background: #FFEBEE;
  border-color: #EF9A9A;
  color: #B71C1C;
}
.detail-block :deep(.qb-bad blockquote),
.improve-body :deep(.qb-bad blockquote),
.recommendations-block :deep(.qb-bad blockquote) {
  border-left-color: #E57373;
}

/* FIX — light green with bulb */
.detail-block :deep(.qb-fix),
.errors-body  :deep(.qb-fix),
.improve-body :deep(.qb-fix),
.recommendations-block :deep(.qb-fix) {
  background: #E0F2F1;
  border-color: #80CBC4;
  color: #00695C;
}
.detail-block :deep(.qb-fix blockquote),
.improve-body :deep(.qb-fix blockquote),
.recommendations-block :deep(.qb-fix blockquote) {
  border-left-color: #4DB6AC;
}
</style>
