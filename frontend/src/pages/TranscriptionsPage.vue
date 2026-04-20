<template>
  <q-page class="q-pa-md">

    <!-- Toolbar -->
    <div class="row items-center q-mb-md q-gutter-sm">
      <q-input
        v-model="search"
        outlined dense clearable
        placeholder="Search partner or operator…"
        style="min-width:240px"
        debounce="350"
        @update:model-value="load"
      >
        <template #prepend><q-icon name="search" /></template>
      </q-input>

      <q-select
        v-model="filterStatus"
        :options="statusOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="All statuses"
        style="min-width:160px"
        @update:model-value="load"
      />

      <q-btn
        :outline="!onlyMine"
        :color="onlyMine ? 'primary' : 'grey-7'"
        :icon="onlyMine ? 'person' : 'person_outline'"
        label="Assigned to Me"
        dense unelevated no-caps
        style="border-radius:8px;font-size:13px;"
        @click="onlyMine = !onlyMine; load()"
      />

      <q-space />

      <div class="text-caption text-grey-6">{{ total }} transcriptions</div>
    </div>

    <!-- Table -->
    <q-card flat bordered style="border-radius:12px;overflow:hidden;">
      <q-table
        :rows="rows"
        :columns="columns"
        row-key="id"
        :loading="loading"
        flat
        :rows-per-page-options="[25, 50, 100, 0]"
        v-model:pagination="pagination"
        @request="onRequest"
        binary-state-sort
        no-data-label="No transcriptions yet"
        @row-click="openDetail"
      >
        <template #body-cell-date="props">
          <q-td :props="props">
            <span class="text-caption text-grey-7">{{ fmtDatetime(props.row.date) }}</span>
          </q-td>
        </template>

        <template #body-cell-partner_name="props">
          <q-td :props="props">
            <router-link :to="`/partners/${props.row.partner}`" @click.stop class="partner-link">
              {{ props.row.partner_name }}
            </router-link>
          </q-td>
        </template>

        <template #body-cell-operator="props">
          <q-td :props="props">
            <span class="text-caption">
              {{ props.row.created_by_detail?.full_name || props.row.created_by_detail?.username || '—' }}
            </span>
          </q-td>
        </template>

        <template #body-cell-call_duration="props">
          <q-td :props="props">
            <span v-if="props.row.call_duration" class="text-caption">
              {{ fmtDuration(props.row.call_duration) }}
            </span>
            <span v-else class="text-grey-4">—</span>
          </q-td>
        </template>

        <template #body-cell-transcription_status="props">
          <q-td :props="props">
            <q-chip
              dense size="sm"
              :color="statusColor(props.row.transcription_status)"
              :text-color="statusTextColor(props.row.transcription_status)"
              style="font-size:10px;"
            >
              <q-spinner-dots v-if="props.row.transcription_status === 'processing'" size="10px" class="q-mr-xs" />
              {{ statusLabel(props.row.transcription_status) }}
            </q-chip>
          </q-td>
        </template>

        <template #body-cell-quality_survey="props">
          <q-td :props="props" class="text-center">
            <score-badge :score="props.row.quality_survey" :comment="props.row.quality_survey_comment" />
          </q-td>
        </template>

        <template #body-cell-quality_explanation="props">
          <q-td :props="props" class="text-center">
            <score-badge :score="props.row.quality_explanation" :comment="props.row.quality_explanation_comment" />
          </q-td>
        </template>

        <template #body-cell-quality_overall="props">
          <q-td :props="props" class="text-center">
            <score-badge :score="props.row.quality_overall" :comment="props.row.quality_overall_comment" />
          </q-td>
        </template>

      </q-table>
    </q-card>

    <!-- ═══ Detail dialog ═══ -->
    <q-dialog v-model="detailOpen" maximized transition-show="slide-up" transition-hide="slide-down">
      <q-card v-if="selected" class="detail-card">

        <!-- Top bar -->
        <div class="detail-topbar">
          <div class="row items-center q-gutter-sm" style="flex:1;min-width:0;">
            <q-icon name="mic" size="20px" color="white" />
            <span class="detail-topbar-title ellipsis">{{ selected.partner_name }}</span>
            <q-chip dense size="sm" color="white" text-color="grey-9" class="q-ml-xs">
              {{ fmtDatetime(selected.date) }}
            </q-chip>
            <q-chip v-if="selected.call_duration" dense size="sm" color="rgba(255,255,255,0.15)" text-color="white">
              <q-icon name="schedule" size="12px" class="q-mr-xs" />
              {{ fmtDuration(selected.call_duration) }}
            </q-chip>
            <q-chip v-if="selected.created_by_detail" dense size="sm" color="rgba(255,255,255,0.15)" text-color="white">
              <q-icon name="person" size="12px" class="q-mr-xs" />
              {{ selected.created_by_detail?.full_name || selected.created_by_detail?.username }}
            </q-chip>
          </div>
          <q-btn flat round dense icon="close" color="white" @click="detailOpen = false" />
        </div>

        <!-- Audio player -->
        <div v-if="selected.audio_url" class="audio-bar">
          <audio controls :src="selected.audio_url" style="width:100%;height:36px;" />
        </div>

        <!-- Content -->
        <div class="detail-body">

          <!-- Left: transcript -->
          <div class="detail-left">
            <!-- Sticky toolbar -->
            <div class="tx-toolbar">
              <q-btn-toggle
                v-model="transcriptView"
                :options="[
                  { label: 'Chat', value: 'chat', icon: 'forum' },
                  { label: 'Raw',  value: 'raw',  icon: 'subject' },
                ]"
                no-caps dense unelevated rounded
                toggle-color="primary"
                color="grey-2"
                text-color="grey-8"
                size="sm"
              />

              <q-input
                v-model="transcriptSearch"
                outlined dense clearable
                placeholder="Search transcript…"
                class="tx-search"
                debounce="200"
              >
                <template #prepend><q-icon name="search" size="16px" /></template>
              </q-input>

              <q-space />

              <div class="tx-stats">
                <span class="tx-stat" :title="'Visible transcript characters'">
                  <q-icon name="text_fields" size="13px" />
                  {{ activeText.length.toLocaleString() }} ch · {{ wordCount(activeText).toLocaleString() }} words
                </span>
                <span v-if="lengthDelta !== null"
                      class="tx-stat tx-stat--warn"
                      :class="{ 'tx-stat--bad': lengthDelta < -15 }"
                      title="Diarized vs raw transcript length">
                  <q-icon name="compare_arrows" size="13px" />
                  vs raw: {{ lengthDelta > 0 ? '+' : '' }}{{ lengthDelta }}%
                </span>
              </div>

              <q-btn flat dense round icon="content_copy" size="sm"
                     @click="copyTranscript"
                     :title="`Copy ${transcriptView === 'raw' ? 'raw' : 'diarized'} transcript`" />
              <q-btn v-if="authStore.isAdmin && transcriptView === 'chat'"
                     flat dense round icon="autorenew" size="sm"
                     :loading="rediarizing"
                     title="Re-run diarization & translation"
                     @click="rediarize" />
            </div>

            <!-- Length warning -->
            <div v-if="lengthDelta !== null && lengthDelta < -15" class="tx-warn">
              <q-icon name="warning" size="16px" />
              <div>
                The translated/labeled transcript is <strong>{{ Math.abs(lengthDelta) }}% shorter</strong>
                than the raw Whisper output — content may have been condensed during translation.
                Switch to <strong>Raw</strong> to see the original full text, or
                <span v-if="authStore.isAdmin">click <q-icon name="autorenew" size="12px" /> to re-diarize.</span>
              </div>
            </div>

            <!-- Chat view -->
            <template v-if="transcriptView === 'chat'">
              <div v-if="parsedTurns.length" class="chat-wrap">
                <div
                  v-for="(turn, i) in filteredTurns"
                  :key="i"
                  class="chat-msg"
                  :class="turn.isOperator ? 'chat-msg--op' : 'chat-msg--partner'"
                >
                  <div class="chat-avatar">
                    <q-icon :name="turn.isOperator ? 'headset_mic' : 'person'" size="16px" />
                  </div>
                  <div class="chat-content">
                    <div class="chat-speaker">
                      <span>{{ turn.speaker }}</span>
                      <span class="chat-meta">turn {{ turn.idx + 1 }} · {{ wordCount(turn.text) }} words</span>
                    </div>
                    <div class="chat-text" v-html="highlight(turn.text)" />
                  </div>
                </div>
                <div v-if="!filteredTurns.length" class="tx-empty">
                  <q-icon name="search_off" size="28px" />
                  <div>No turns match "{{ transcriptSearch }}"</div>
                </div>
              </div>
              <div v-else-if="selected.transcription" class="tx-fallback">
                <div class="tx-fallback-hint">
                  <q-icon name="info" size="14px" />
                  No diarized version yet — showing raw Whisper output below.
                </div>
                <pre class="raw-transcript" v-html="highlight(selected.transcription)" />
              </div>
              <div v-else class="tx-empty">
                <q-icon name="hearing_disabled" size="40px" />
                <div>No transcript available</div>
              </div>
            </template>

            <!-- Raw view -->
            <template v-else>
              <pre v-if="selected.transcription" class="raw-transcript" v-html="highlight(selected.transcription)" />
              <div v-else class="tx-empty">
                <q-icon name="hearing_disabled" size="40px" />
                <div>No raw transcript available</div>
              </div>
            </template>
          </div>

          <!-- Right panel -->
          <div class="detail-right">
            <q-tabs v-model="rightTab" dense narrow-indicator active-color="primary" class="detail-tabs">
              <q-tab name="summary" icon="auto_awesome" label="Summary" />
              <q-tab name="quality" icon="analytics" label="Quality" />
            </q-tabs>

            <q-separator />

            <div class="detail-right-content">
              <!-- Summary tab -->
              <div v-if="rightTab === 'summary'">
                <div v-if="selected.summary" class="summary-block" v-html="renderMd(selected.summary)" />
                <div v-else-if="selected.summary_status === 'processing'" class="text-grey-5 text-center q-pa-lg">
                  <q-spinner-dots size="24px" class="q-mb-sm" /><br>Generating summary…
                </div>
                <div v-else class="text-grey-4 text-center q-pa-lg">No summary yet</div>

                <div v-if="selected.quality_feedback" class="q-mt-lg">
                  <div class="section-title"><q-icon name="lightbulb" size="14px" color="amber-8" /> Key Takeaway</div>
                  <div class="takeaway-block">{{ selected.quality_feedback }}</div>
                </div>
              </div>

              <!-- Quality tab -->
              <div v-if="rightTab === 'quality'">
                <div v-if="selected.quality_overall != null">
                  <!-- Score cards -->
                  <div class="scores-grid">
                    <div v-for="dim in scoreDims" :key="dim.key" class="score-card-v2" :style="`border-left: 3px solid ${dim.color}`">
                      <div class="row items-center justify-between q-mb-xs">
                        <div class="score-card-label">
                          <q-icon :name="dim.icon" size="14px" :style="`color:${dim.color}`" />
                          {{ dim.label }}
                        </div>
                        <div class="score-num" :style="scoreStyle(selected['quality_' + dim.key])">
                          {{ selected['quality_' + dim.key] }}<span class="score-of">/10</span>
                        </div>
                      </div>
                      <div class="score-comment">{{ selected['quality_' + dim.key + '_comment'] }}</div>
                    </div>
                  </div>

                  <!-- Detailed breakdowns -->
                  <div v-for="dim in scoreDims" :key="'d-'+dim.key" class="q-mt-md">
                    <div v-if="selected['quality_' + dim.key + '_detail']">
                      <div class="section-title" :style="`color:${dim.color}`">
                        <q-icon :name="dim.icon" size="14px" /> {{ dim.label }} — Details
                      </div>
                      <div class="detail-md-block" v-html="renderMd(selected['quality_' + dim.key + '_detail'])" />
                    </div>
                  </div>

                  <!-- Recommendations -->
                  <div v-if="selected.quality_recommendations" class="q-mt-lg">
                    <div class="section-title" style="color:#7B1FA2;">
                      <q-icon name="tips_and_updates" size="14px" /> Recommendations
                    </div>
                    <div class="detail-md-block reco-block" v-html="renderMd(selected.quality_recommendations)" />
                  </div>
                </div>
                <div v-else class="text-grey-4 text-center q-pa-lg">No quality scores yet</div>
              </div>
            </div>
          </div>

        </div>
      </q-card>
    </q-dialog>

  </q-page>
</template>

<script setup>
import { ref, computed, onMounted, defineComponent, h } from 'vue'
import { api } from 'boot/axios'
import { useQuasar } from 'quasar'
import { useAuthStore } from 'stores/auth'

const $q        = useQuasar()
const authStore = useAuthStore()

const ScoreBadge = defineComponent({
  props: { score: Number, comment: String },
  setup(props) {
    return () => {
      if (props.score == null) return h('span', { class: 'text-grey-4', style: 'font-size:12px' }, '—')
      const s = props.score
      const bg   = s >= 8 ? '#E8F5E9' : s >= 6 ? '#FFF8E1' : '#FFEBEE'
      const col  = s >= 8 ? '#2E7D32' : s >= 6 ? '#F57F17' : '#C62828'
      const chip = h('div', {
        style: `display:inline-flex;align-items:center;justify-content:center;width:32px;height:22px;border-radius:6px;background:${bg};color:${col};font-size:12px;font-weight:800;cursor:${props.comment ? 'pointer' : 'default'}`
      }, String(s))
      if (!props.comment) return chip
      return h('div', {}, [
        chip,
        h('q-tooltip', { style: 'font-size:11px;max-width:220px' }, props.comment),
      ])
    }
  },
})

const rows    = ref([])
const loading = ref(false)
const total   = ref(0)
const search  = ref('')
const filterStatus = ref(null)
const onlyMine     = ref(false)
const detailOpen      = ref(false)
const selected        = ref(null)
const rightTab        = ref('summary')
const transcriptView  = ref('chat')           // 'chat' | 'raw'
const transcriptSearch = ref('')
const rediarizing     = ref(false)

const pagination = ref({
  page: 1, rowsPerPage: 25, rowsNumber: 0, sortBy: 'date', descending: true,
})

const columns = [
  { name: 'date',                 label: 'Date',         field: 'date',                 align: 'left', sortable: true },
  { name: 'partner_name',         label: 'Partner',      field: 'partner_name',         align: 'left', sortable: true },
  { name: 'operator',             label: 'Operator',     field: r => r.created_by_detail?.full_name || '', align: 'left', sortable: false },
  { name: 'call_duration',        label: 'Duration',     field: 'call_duration',        align: 'left', sortable: true },
  { name: 'transcription_status', label: 'Status',       field: 'transcription_status', align: 'left', sortable: false },
  { name: 'quality_survey',       label: 'Survey',       field: 'quality_survey',       align: 'center', sortable: true },
  { name: 'quality_explanation',  label: 'Explanation',  field: 'quality_explanation',  align: 'center', sortable: true },
  { name: 'quality_overall',      label: 'Overall',      field: 'quality_overall',      align: 'center', sortable: true },
]

const statusOptions = [
  { label: 'Done',        value: 'done' },
  { label: 'Processing',  value: 'processing' },
  { label: 'Pending',     value: 'pending' },
  { label: 'Failed',      value: 'failed' },
]

const scoreDims = [
  { key: 'survey',      label: 'Survey / Discovery', icon: 'quiz',          color: '#1565C0' },
  { key: 'explanation', label: 'Explanation',         icon: 'school',        color: '#E65100' },
  { key: 'overall',     label: 'Overall',             icon: 'star_rate',     color: '#2E7D32' },
]

const parsedTurns = computed(() => {
  if (!selected.value?.diarized_transcript) return []
  return selected.value.diarized_transcript
    .split(/\n\n+/)
    .map(l => l.trim())
    .filter(Boolean)
    .map((line, idx) => {
      // backend writes: "**Operator:** text…" — note: colon INSIDE the asterisks
      let m = line.match(/^\*\*\s*(Operator|Partner|Unknown|Speaker\s*\d*)\s*:?\s*\*\*\s*:?\s*([\s\S]*)$/i)
      if (!m) {
        // fallback: "**Operator**: text"
        m = line.match(/^\*\*\s*(Operator|Partner|Unknown|Speaker\s*\d*)\s*\*\*\s*:?\s*([\s\S]*)$/i)
      }
      if (!m) {
        // fallback: "Operator: text" (no asterisks)
        m = line.match(/^(Operator|Partner|Unknown|Speaker\s*\d*)\s*:\s*([\s\S]*)$/i)
      }
      if (m) {
        const raw = m[1].trim()
        const isOp  = /^operator$/i.test(raw)
        const isPt  = /^partner$/i.test(raw)
        const speaker = isOp ? 'Operator' : isPt ? 'Partner' : 'Speaker'
        const text = m[2].replace(/\*\*/g, '').trim()
        return { speaker, text, isOperator: isOp, idx }
      }
      return { speaker: 'Speaker', text: line.replace(/\*\*/g, '').trim(), isOperator: idx % 2 === 0, idx }
    })
})

const filteredTurns = computed(() => {
  const q = transcriptSearch.value?.trim().toLowerCase()
  if (!q) return parsedTurns.value
  return parsedTurns.value.filter(t =>
    t.text.toLowerCase().includes(q) || t.speaker.toLowerCase().includes(q)
  )
})

const activeText = computed(() => {
  if (transcriptView.value === 'raw') return selected.value?.transcription || ''
  return selected.value?.diarized_transcript || selected.value?.transcription || ''
})

const lengthDelta = computed(() => {
  const raw = (selected.value?.transcription || '').length
  const dia = (selected.value?.diarized_transcript || '').length
  if (!raw || !dia) return null
  return Math.round(((dia - raw) / raw) * 100)
})

function wordCount(s) {
  if (!s) return 0
  return s.trim().split(/\s+/).filter(Boolean).length
}

function escapeHtml(s) {
  return (s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
function highlight(text) {
  const safe = escapeHtml(text)
  const q = transcriptSearch.value?.trim()
  if (!q) return safe
  const re = new RegExp(escapeRegExp(escapeHtml(q)), 'gi')
  return safe.replace(re, m => `<mark class="tx-mark">${m}</mark>`)
}

async function copyTranscript() {
  const text = transcriptView.value === 'raw'
    ? (selected.value?.transcription || '')
    : (selected.value?.diarized_transcript || selected.value?.transcription || '')
  try {
    await navigator.clipboard.writeText(text)
    $q.notify({ type: 'positive', message: 'Transcript copied to clipboard', timeout: 1200 })
  } catch {
    $q.notify({ type: 'negative', message: 'Copy failed' })
  }
}

async function rediarize() {
  if (!selected.value) return
  rediarizing.value = true
  try {
    const res = await api.post(`/contacts/${selected.value.id}/rediarize/`)
    Object.assign(selected.value, res.data || {})
    $q.notify({ type: 'positive', message: 'Re-diarization queued/finished', timeout: 1500 })
    setTimeout(load, 4000)
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.error || 'Failed to re-diarize' })
  } finally {
    rediarizing.value = false
  }
}

function scoreStyle(s) {
  if (s == null) return 'color:#9E9E9E'
  if (s >= 8) return 'color:#2E7D32'
  if (s >= 6) return 'color:#F57F17'
  return 'color:#C62828'
}

function renderMd(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/^>\s?(.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/<\/blockquote>\n<blockquote>/g, '<br>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`)
    .split(/\n{2,}/)
    .map(b => {
      b = b.trim()
      if (!b) return ''
      if (/^<(h[1-4]|ul|ol|blockquote)/.test(b)) return b
      return `<p>${b.replace(/\n/g, '<br>')}</p>`
    })
    .join('\n')
}

async function load() {
  loading.value = true
  try {
    const params = {
      has_audio: 'true',
      page:      pagination.value.page,
      page_size: pagination.value.rowsPerPage,
    }
    if (search.value)       params.search = search.value
    if (filterStatus.value) params.transcription_status = filterStatus.value
    if (onlyMine.value)     params.created_by = authStore.user?.id
    if (pagination.value.sortBy) {
      params.ordering = (pagination.value.descending ? '-' : '') + pagination.value.sortBy
    }
    const res = await api.get('/contacts/', { params })
    rows.value  = res.data.results || res.data
    total.value = res.data.count   || rows.value.length
    pagination.value.rowsNumber = total.value
  } finally {
    loading.value = false
  }
}

function onRequest(props) {
  pagination.value = props.pagination
  load()
}

function openDetail(_, row) {
  selected.value         = row
  rightTab.value         = 'summary'
  transcriptView.value   = 'chat'
  transcriptSearch.value = ''
  detailOpen.value       = true
}

function fmtDatetime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function fmtDuration(secs) {
  if (!secs) return '—'
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function statusColor(st) {
  return { done: 'green-2', processing: 'blue-2', pending: 'grey-3', failed: 'red-2' }[st] || 'grey-2'
}
function statusTextColor(st) {
  return { done: 'green-9', processing: 'blue-9', pending: 'grey-7', failed: 'red-9' }[st] || 'grey-7'
}
function statusLabel(st) {
  return { done: 'Done', processing: 'Processing', pending: 'Pending', failed: 'Failed', '': 'No audio' }[st] || st
}

onMounted(load)
</script>

<style scoped>
.partner-link { color: #2E7D32; text-decoration: none; font-size: 13px; font-weight: 500; }
.partner-link:hover { text-decoration: underline; }

/* ═══ Detail dialog ═══ */
.detail-card { display: flex; flex-direction: column; background: #FAFAFA; }

.detail-topbar {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #1A237E 0%, #283593 100%);
  flex-shrink: 0;
}
.detail-topbar-title { font-size: 15px; font-weight: 700; color: white; }

.audio-bar {
  padding: 6px 16px;
  background: #ECEFF1;
  border-bottom: 1px solid #CFD8DC;
  flex-shrink: 0;
}

.detail-body { display: flex; flex: 1; overflow: hidden; }

.detail-left {
  flex: 1; overflow-y: auto; padding: 0;
  background: #FAFAFA;
  border-right: 1px solid #E0E0E0;
  display: flex; flex-direction: column;
}

/* Sticky toolbar above transcript */
.tx-toolbar {
  position: sticky; top: 0; z-index: 5;
  display: flex; align-items: center; gap: 10px;
  padding: 10px 18px;
  background: #FFFFFFEE;
  backdrop-filter: blur(8px);
  border-bottom: 1px solid #ECEFF1;
  flex-wrap: wrap;
}
.tx-search { min-width: 220px; max-width: 320px; }
.tx-search :deep(.q-field__control) { height: 32px; min-height: 32px; font-size: 12.5px; }
.tx-search :deep(.q-field__marginal) { height: 32px; }

.tx-stats {
  display: flex; align-items: center; gap: 10px;
  font-size: 11.5px; color: #607D8B;
  white-space: nowrap;
}
.tx-stat { display: inline-flex; align-items: center; gap: 4px; }
.tx-stat--warn { color: #EF6C00; font-weight: 600; }
.tx-stat--bad  { color: #C62828; font-weight: 700; }

.tx-warn {
  display: flex; align-items: flex-start; gap: 8px;
  margin: 12px 18px 0;
  padding: 10px 14px;
  background: #FFF3E0;
  border-left: 3px solid #FB8C00;
  border-radius: 0 8px 8px 0;
  color: #BF360C;
  font-size: 12.5px;
  line-height: 1.5;
}
.tx-warn .q-icon { color: #EF6C00; flex-shrink: 0; margin-top: 1px; }

/* Chat-style transcript — readable full-width rows */
.chat-wrap {
  display: flex; flex-direction: column; gap: 12px;
  padding: 16px 24px 32px;
  max-width: 920px; width: 100%; margin: 0 auto;
}

.chat-msg {
  display: flex; gap: 12px;
  animation: fadeIn 0.15s ease;
}

.chat-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; margin-top: 4px;
  border: 1px solid transparent;
}
.chat-msg--op      .chat-avatar { background: #E3F2FD; color: #1565C0; border-color: #BBDEFB; }
.chat-msg--partner .chat-avatar { background: #E8F5E9; color: #2E7D32; border-color: #C8E6C9; }

.chat-content { flex: 1; min-width: 0; }

.chat-speaker {
  display: flex; align-items: baseline; gap: 8px;
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .6px; margin-bottom: 4px;
}
.chat-msg--op      .chat-speaker { color: #1565C0; }
.chat-msg--partner .chat-speaker { color: #2E7D32; }
.chat-meta {
  font-size: 10px; font-weight: 500; letter-spacing: .2px;
  color: #B0BEC5; text-transform: none;
}

.chat-text {
  padding: 10px 14px; font-size: 14px; line-height: 1.65;
  word-break: break-word; white-space: pre-wrap;
  border: 1px solid transparent;
}
.chat-msg--op .chat-text {
  background: #F5FAFF; color: #0D47A1;
  border-color: #D6E9FF;
  border-radius: 2px 10px 10px 10px;
}
.chat-msg--partner .chat-text {
  background: #F3FBF4; color: #1B5E20;
  border-color: #DDEFDD;
  border-radius: 10px 2px 10px 10px;
}

/* Raw view */
.raw-transcript {
  white-space: pre-wrap; word-break: break-word;
  font-size: 13.5px; line-height: 1.75; color: #37474F;
  font-family: inherit; margin: 16px 24px 32px;
  padding: 16px 18px;
  max-width: 920px;
  background: #FFFFFF;
  border: 1px solid #ECEFF1;
  border-radius: 8px;
}

.tx-fallback { padding: 16px 24px; }
.tx-fallback-hint {
  display: inline-flex; align-items: center; gap: 6px;
  background: #FFF8E1; color: #EF6C00;
  padding: 6px 10px; border-radius: 6px;
  font-size: 12px;
  margin-bottom: 8px;
}

.tx-empty {
  flex: 1;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px;
  color: #B0BEC5; font-size: 13px;
  padding: 60px 20px;
}

:deep(mark.tx-mark) {
  background: #FFF59D; color: #5D4037;
  padding: 0 2px; border-radius: 3px;
  font-weight: 600;
}

/* Right panel */
.detail-right {
  width: 420px; flex-shrink: 0;
  display: flex; flex-direction: column;
  background: white;
}
.detail-tabs { background: #FAFAFA; }
.detail-right-content { flex: 1; overflow-y: auto; padding: 16px 20px; }

.section-title {
  font-size: 12px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .5px; color: #546E7A;
  margin-bottom: 8px;
  display: flex; align-items: center; gap: 5px;
}

.summary-block {
  font-size: 13px; line-height: 1.7; color: #37474F;
  background: #F9FBE7; border-left: 3px solid #AED581;
  border-radius: 0 8px 8px 0; padding: 12px 16px;
}

.takeaway-block {
  font-size: 13px; line-height: 1.6; color: #5D4037;
  background: #FFF8E1; border-left: 3px solid #FFD54F;
  border-radius: 0 8px 8px 0; padding: 10px 14px;
}

/* Score cards */
.scores-grid { display: flex; flex-direction: column; gap: 10px; }

.score-card-v2 {
  background: #FAFAFA;
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
}
.score-card-label {
  font-size: 12px; font-weight: 700; color: #37474F;
  display: flex; align-items: center; gap: 4px;
}
.score-num { font-size: 22px; font-weight: 800; line-height: 1; }
.score-of { font-size: 12px; font-weight: 500; opacity: 0.5; }
.score-comment { font-size: 12px; line-height: 1.5; color: #78909C; margin-top: 4px; }

/* Markdown blocks */
.detail-md-block {
  font-size: 13px; line-height: 1.6; color: #37474F;
  background: #F5F5F5; border-radius: 8px; padding: 12px 16px;
}
.detail-md-block :deep(h3) { font-size: 14px; margin: 12px 0 6px; color: #263238; }
.detail-md-block :deep(h4) { font-size: 13px; margin: 10px 0 4px; color: #37474F; }
.detail-md-block :deep(blockquote) {
  border-left: 3px solid #90CAF9; margin: 6px 0; padding: 4px 12px;
  background: #E3F2FD; border-radius: 0 6px 6px 0; color: #1565C0; font-style: italic;
}
.detail-md-block :deep(ul) { padding-left: 16px; margin: 4px 0; }
.detail-md-block :deep(li) { margin: 2px 0; }
.detail-md-block :deep(strong) { color: #263238; }
.detail-md-block :deep(p) { margin: 6px 0; }

.reco-block { background: #F3E5F5; border: 1px solid #CE93D8; }
.reco-block :deep(blockquote) {
  border-left-color: #AB47BC; background: #EDE7F6; color: #6A1B9A;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
</style>
