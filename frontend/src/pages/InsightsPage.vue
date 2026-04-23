<template>
  <q-page class="q-pa-md">
    <q-tabs
      v-model="tab"
      dense align="left" inline-label no-caps
      active-color="primary" indicator-color="primary"
      class="q-mb-md"
      :breakpoint="0"
    >
      <q-tab name="per_call" icon="fact_check" label="Per-call insights" />
      <q-tab name="aggregate" icon="insights" label="Aggregate report" />
    </q-tabs>

    <q-tab-panels v-model="tab" animated keep-alive class="bg-transparent">
      <!-- ============== PER-CALL TAB ============== -->
      <q-tab-panel name="per_call" class="q-pa-none">
        <div class="row items-center q-mb-md q-gutter-sm">
          <q-input
            v-model="search"
            outlined dense clearable
            placeholder="Search partner or insight text…"
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
            placeholder="Status"
            style="min-width:140px"
            @update:model-value="load"
          />

          <q-select
            v-model="filterBucket"
            :options="bucketOptions"
            emit-value map-options
            outlined dense clearable
            placeholder="Volume"
            style="min-width:130px"
            @update:model-value="load"
          />

          <q-space />
          <div class="text-caption text-grey-6">{{ total }} insights</div>
        </div>

        <q-card flat bordered style="border-radius:12px;overflow:hidden;">
          <q-table
            :rows="rows"
            :columns="columns"
            row-key="id"
            :loading="loading"
            flat
            :rows-per-page-options="[25, 50, 100]"
            v-model:pagination="pagination"
            @request="onRequest"
            binary-state-sort
            no-data-label="No call insights yet"
            @row-click="openDetail"
          >
            <template #body-cell-call_date="props">
              <q-td :props="props">
                <span class="text-caption text-grey-7">{{ fmtDatetime(props.row.call_date) }}</span>
              </q-td>
            </template>
            <template #body-cell-partner_name="props">
              <q-td :props="props">
                <router-link :to="`/partners/${props.row.partner}`" class="partner-link" @click.stop>
                  {{ props.row.partner_name }}
                </router-link>
              </q-td>
            </template>
            <template #body-cell-status="props">
              <q-td :props="props">
                <q-chip dense size="sm" :color="statusColor(props.row.status)" :text-color="statusText(props.row.status)">
                  <q-spinner-dots v-if="props.row.status === 'processing'" size="10px" class="q-mr-xs" />
                  {{ props.row.status }}
                </q-chip>
              </q-td>
            </template>
            <template #body-cell-density_bucket="props">
              <q-td :props="props">
                <q-badge v-if="props.row.density_bucket" outline :color="bucketColor(props.row.density_bucket)">
                  {{ props.row.density_bucket }}
                </q-badge>
                <span v-else class="text-grey-4">—</span>
              </q-td>
            </template>
            <template #body-cell-insight_count="props">
              <q-td :props="props" class="text-right">{{ props.row.insight_count ?? '—' }}</q-td>
            </template>
            <template #body-cell-preview="props">
              <q-td :props="props">
                <span class="text-caption text-grey-8 ellipsis-2">{{ props.row.preview || '—' }}</span>
              </q-td>
            </template>
          </q-table>
        </q-card>
      </q-tab-panel>

      <!-- ============== AGGREGATE TAB ============== -->
      <q-tab-panel name="aggregate" class="q-pa-none">
        <q-card flat bordered class="q-mb-md" style="border-radius:12px;">
          <q-card-section class="q-pa-md">
            <div class="text-subtitle2 q-mb-sm row items-center">
              <q-icon name="auto_awesome" class="q-mr-xs text-primary" />
              Generate aggregate report
              <q-space />
              <span class="text-caption text-grey-6">
                Clusters all insights in a date range and ranks themes by unique partner count.
              </span>
            </div>
            <div class="row items-end q-gutter-sm">
              <div>
                <div class="text-caption text-grey-7 q-mb-xs">From</div>
                <q-input
                  v-model="agg.from"
                  outlined dense type="date"
                  style="min-width:160px"
                />
              </div>
              <div>
                <div class="text-caption text-grey-7 q-mb-xs">To</div>
                <q-input
                  v-model="agg.to"
                  outlined dense type="date"
                  style="min-width:160px"
                />
              </div>
              <div class="row q-gutter-xs">
                <q-btn dense outline no-caps size="sm" label="Last 7 days" @click="aggPreset(7)" />
                <q-btn dense outline no-caps size="sm" label="30 days"     @click="aggPreset(30)" />
                <q-btn dense outline no-caps size="sm" label="90 days"     @click="aggPreset(90)" />
                <q-btn dense outline no-caps size="sm" label="All time"    @click="aggPreset(3650)" />
              </div>
              <q-space />
              <q-btn
                color="primary" no-caps icon="play_arrow"
                :loading="agg.creating"
                :disable="!agg.from || !agg.to"
                label="Generate report"
                @click="createAggregate"
              />
            </div>
          </q-card-section>
        </q-card>

        <q-card flat bordered style="border-radius:12px;overflow:hidden;">
          <q-table
            :rows="aggRows"
            :columns="aggColumns"
            row-key="id"
            :loading="agg.loading"
            flat
            :rows-per-page-options="[10, 25, 50]"
            v-model:pagination="agg.pagination"
            @request="onAggRequest"
            no-data-label="No aggregate reports yet — generate one above"
            @row-click="openAggDetail"
          >
            <template #body-cell-period="props">
              <q-td :props="props">
                <strong>{{ props.row.date_from }}</strong>
                <span class="text-grey-6"> → </span>
                <strong>{{ props.row.date_to }}</strong>
              </q-td>
            </template>
            <template #body-cell-status="props">
              <q-td :props="props">
                <q-chip dense size="sm" :color="statusColor(props.row.status)" :text-color="statusText(props.row.status)">
                  <q-spinner-dots v-if="props.row.status === 'processing' || props.row.status === 'pending'" size="10px" class="q-mr-xs" />
                  {{ props.row.status }}
                </q-chip>
              </q-td>
            </template>
            <template #body-cell-coverage="props">
              <q-td :props="props">
                <span class="text-caption">
                  {{ props.row.total_calls }} calls · {{ props.row.total_insights }} insights · <b>{{ props.row.unique_partners }} partners</b>
                </span>
              </q-td>
            </template>
            <template #body-cell-summary="props">
              <q-td :props="props">
                <span class="text-caption text-grey-8 ellipsis-2">{{ props.row.summary_text || '—' }}</span>
              </q-td>
            </template>
            <template #body-cell-created_by="props">
              <q-td :props="props">
                <span class="text-caption">
                  {{ props.row.created_by_detail?.full_name || props.row.created_by_detail?.email || '—' }}
                </span>
                <div class="text-caption text-grey-6">{{ fmtDatetime(props.row.created_at) }}</div>
              </q-td>
            </template>
            <template #body-cell-actions="props">
              <q-td :props="props" class="text-right">
                <q-btn
                  v-if="props.row.status === 'done'"
                  dense flat icon="picture_as_pdf" color="deep-purple-7" size="sm"
                  :loading="props.row._pdfLoading"
                  @click.stop="downloadAggregatePdf(props.row)"
                >
                  <q-tooltip>Download PDF</q-tooltip>
                </q-btn>
                <q-btn
                  v-if="props.row.status === 'failed'"
                  dense flat icon="refresh" color="negative" size="sm"
                  @click.stop="retryAggregate(props.row)"
                >
                  <q-tooltip>Retry generation</q-tooltip>
                </q-btn>
                <q-btn dense flat icon="delete" color="grey-7" size="sm"
                  @click.stop="deleteAggregate(props.row)"
                >
                  <q-tooltip>Delete</q-tooltip>
                </q-btn>
              </q-td>
            </template>
          </q-table>
        </q-card>
      </q-tab-panel>
    </q-tab-panels>

    <!-- Per-call insight modal -->
    <q-dialog v-model="detailOpen" maximized transition-show="slide-up" transition-hide="slide-down">
      <q-card v-if="selected" class="insight-detail-card">
        <q-bar class="bg-primary text-white">
          <q-icon name="lightbulb" class="q-mr-sm" />
          <div class="text-weight-bold ellipsis">
            {{ selected.partner_name }} · {{ fmtDatetime(selected.call_date) }}
          </div>
          <q-space />
          <q-btn dense flat round icon="close" v-close-popup />
        </q-bar>
        <q-card-section class="q-pa-md" style="max-height:calc(100vh - 48px); overflow:auto;">
          <div class="row q-gutter-sm q-mb-md items-center">
            <q-btn outline dense no-caps color="primary" icon="person"
                   :to="`/partners/${selected.partner}`" label="Partner page"
                   @click="detailOpen = false" />
            <q-chip dense outline>{{ selected.insight_count }} items · {{ selected.density_bucket || '—' }}</q-chip>
          </div>
          <div class="insight-md" v-html="renderMd(selected.insights_markdown || '')" />
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- Aggregate detail modal -->
    <q-dialog v-model="aggDetailOpen" maximized transition-show="slide-up" transition-hide="slide-down">
      <q-card v-if="aggSelected" class="insight-detail-card">
        <q-bar class="bg-deep-purple-7 text-white">
          <q-icon name="insights" class="q-mr-sm" />
          <div class="text-weight-bold ellipsis">
            Aggregate · {{ aggSelected.date_from }} → {{ aggSelected.date_to }}
          </div>
          <q-space />
          <q-btn
            v-if="aggSelected.status === 'done'"
            dense flat no-caps icon="picture_as_pdf"
            label="Download PDF"
            :loading="aggSelected._pdfLoading"
            @click="downloadAggregatePdf(aggSelected)"
          />
          <q-btn dense flat round icon="close" v-close-popup />
        </q-bar>
        <q-card-section class="q-pa-md" style="max-height:calc(100vh - 48px); overflow:auto;">
          <div class="row q-gutter-sm q-mb-sm">
            <q-chip dense outline icon="event">
              {{ aggSelected.total_calls }} calls
            </q-chip>
            <q-chip dense outline icon="format_list_bulleted">
              {{ aggSelected.total_insights }} raw insights
            </q-chip>
            <q-chip dense color="primary" text-color="white" icon="people">
              {{ aggSelected.unique_partners }} unique partners
            </q-chip>
            <q-chip dense outline :color="statusColor(aggSelected.status)" :text-color="statusText(aggSelected.status)">
              {{ aggSelected.status }}
            </q-chip>
          </div>

          <div v-if="aggSelected.status === 'pending' || aggSelected.status === 'processing'"
               class="q-pa-md text-center">
            <q-spinner-dots color="primary" size="32px" class="q-mr-sm" />
            <div class="text-caption text-grey-7 q-mt-sm">Building aggregate report — refreshing automatically…</div>
          </div>

          <div v-else-if="aggSelected.status === 'failed'" class="q-pa-md">
            <q-banner class="bg-red-1 text-red-9" rounded>
              <template #avatar><q-icon name="error" /></template>
              Generation failed:
              <code style="white-space:pre-wrap;">{{ aggSelected.last_error || 'unknown' }}</code>
              <template #action>
                <q-btn flat color="negative" no-caps label="Retry" @click="retryAggregate(aggSelected, true)" />
              </template>
            </q-banner>
          </div>

          <template v-else>
            <q-card flat bordered class="q-mb-md">
              <q-card-section class="q-py-sm">
                <div class="text-subtitle2 q-mb-xs">Executive summary</div>
                <div style="white-space:pre-wrap;">{{ aggSelected.summary_text || '—' }}</div>
              </q-card-section>
            </q-card>

            <q-card v-if="(aggSelected.clusters_json?.top_priorities || []).length"
                    flat bordered class="q-mb-md">
              <q-card-section class="q-py-sm">
                <div class="text-subtitle2 q-mb-xs">Top priorities</div>
                <ul style="margin:0; padding-left:1.25rem;">
                  <li v-for="(p, i) in aggSelected.clusters_json.top_priorities" :key="i" class="q-mb-xs">
                    {{ p }}
                  </li>
                </ul>
              </q-card-section>
            </q-card>

            <div class="text-subtitle2 q-mb-sm row items-center">
              Themes ranked by unique partners
              <q-space />
              <span class="text-caption text-grey-6">
                {{ (aggSelected.clusters_json?.clusters || []).length }} clusters
              </span>
            </div>

            <div
              v-for="(c, i) in (aggSelected.clusters_json?.clusters || [])"
              :key="i"
              class="cluster-card q-mb-md"
            >
              <div class="row items-center q-mb-xs">
                <div class="text-h6 text-weight-medium">{{ i + 1 }}. {{ c.theme }}</div>
                <q-space />
                <q-chip dense color="primary" text-color="white">
                  {{ c.partner_count }} {{ c.partner_count === 1 ? 'partner' : 'partners' }}
                </q-chip>
                <q-chip dense outline>{{ c.mention_count }} mentions</q-chip>
              </div>
              <div class="text-caption text-grey-7 q-mb-sm">
                {{ formatCategory(c.category) }}
                <template v-if="hasSentiments(c)">
                  · Sentiment —
                  <span v-for="(v, k) in c.sentiment_breakdown" :key="k">
                    <span v-if="v" class="q-ml-xs">
                      <q-badge :color="sentimentColor(k)" outline class="q-mr-xs">{{ k }}: {{ v }}</q-badge>
                    </span>
                  </span>
                </template>
              </div>

              <div class="cluster-bar q-mb-sm">
                <div
                  class="cluster-bar-fill"
                  :style="{ width: barPct(c) + '%', background: barColor(c) }"
                />
              </div>

              <div v-if="c.explanation" style="white-space:pre-wrap;" class="q-mb-sm">
                {{ c.explanation }}
              </div>
              <div v-if="c.recommended_action" class="recommended-box q-mb-sm">
                <strong>Recommended action:</strong> {{ c.recommended_action }}
              </div>

              <div v-if="(c.representative_quotes || []).length">
                <div class="text-caption text-grey-7 q-mb-xs">Representative quotes</div>
                <div
                  v-for="(q, qi) in c.representative_quotes"
                  :key="qi"
                  class="quote-row q-mb-xs"
                >
                  <q-icon name="format_quote" size="14px" class="q-mr-xs text-grey-6" />
                  <span class="text-caption text-grey-9">«{{ q.quote }}»</span>
                  <span v-if="q.partner_id" class="text-caption text-grey-6">
                    —
                    <router-link :to="`/partners/${q.partner_id}`" class="partner-link">
                      {{ q.partner_name || 'Partner' }}
                    </router-link>
                  </span>
                </div>
              </div>
            </div>

            <div v-if="!(aggSelected.clusters_json?.clusters || []).length"
                 class="q-pa-md text-center text-grey-6">
              No clustered themes — period had no material insights.
            </div>
          </template>
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuasar } from 'quasar'
import { api } from 'boot/axios'

const $q = useQuasar()
const route = useRoute()

const tab = ref('per_call')

// ====== Per-call (existing) ======
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const pagination = ref({
  sortBy: 'call_date',
  descending: true,
  page: 1,
  rowsPerPage: 25,
  rowsNumber: 0,
})
const search = ref('')
const filterStatus = ref(null)
const filterBucket = ref(null)
const statusOptions = [
  { label: 'Done', value: 'done' },
  { label: 'Pending', value: 'pending' },
  { label: 'Processing', value: 'processing' },
  { label: 'Failed', value: 'failed' },
]
const bucketOptions = [
  { label: 'Low (1–3)', value: 'low' },
  { label: 'Medium (4–7)', value: 'medium' },
  { label: 'High (8+)', value: 'high' },
]
const columns = [
  { name: 'call_date', label: 'Call', field: 'call_date', align: 'left', sortable: true },
  { name: 'partner_name', label: 'Partner', field: 'partner_name', align: 'left' },
  { name: 'status', label: 'Status', field: 'status', align: 'left' },
  { name: 'density_bucket', label: 'Volume', field: 'density_bucket', align: 'center' },
  { name: 'insight_count', label: '#', field: 'insight_count', align: 'right' },
  { name: 'preview', label: 'Preview', field: 'preview', align: 'left' },
]
const detailOpen = ref(false)
const selected = ref(null)

function fmtDatetime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-US', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}
function statusColor(st) {
  return { done: 'green-2', processing: 'blue-2', pending: 'grey-3', failed: 'red-2' }[st] || 'grey-2'
}
function statusText(st) {
  return { done: 'green-9', processing: 'blue-9', pending: 'grey-8', failed: 'red-9' }[st] || 'grey-8'
}
function bucketColor(b) {
  return { low: 'grey-7', medium: 'orange', high: 'deep-orange' }[b] || 'grey'
}

function renderMd(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
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
      if (/^<(h[3-4]|ul)/.test(b)) return b
      return `<p>${b.replace(/\n/g, '<br>')}</p>`
    })
    .join('\n')
}

async function load() {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.rowsPerPage,
    }
    if (search.value) params.search = search.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterBucket.value) params.density_bucket = filterBucket.value
    if (pagination.value.sortBy) {
      params.ordering = (pagination.value.descending ? '-' : '') + pagination.value.sortBy
    }
    const contactId = route.query.contact
    if (contactId) params.contact = contactId
    const res = await api.get('/call-insights/', { params })
    rows.value = res.data.results || res.data
    total.value = res.data.count ?? rows.value.length
    pagination.value.rowsNumber = total.value
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Failed to load insights' })
  } finally {
    loading.value = false
  }
}

function onRequest(props) {
  pagination.value = props.pagination
  load()
}

async function openDetail(_, row) {
  try {
    const res = await api.get(`/call-insights/${row.id}/`)
    selected.value = res.data
    detailOpen.value = true
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to load insight detail' })
  }
}

watch(
  () => route.query.contact,
  () => {
    pagination.value.page = 1
    load()
  },
)

// ====== Aggregate ======
function todayIso() {
  return new Date().toISOString().slice(0, 10)
}
function isoDaysAgo(days) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

const agg = ref({
  from: isoDaysAgo(30),
  to: todayIso(),
  loading: false,
  creating: false,
  pagination: { page: 1, rowsPerPage: 10, rowsNumber: 0, sortBy: 'created_at', descending: true },
})
const aggRows = ref([])
const aggColumns = [
  { name: 'period',     label: 'Period',   field: 'date_from', align: 'left' },
  { name: 'status',     label: 'Status',   field: 'status',    align: 'left' },
  { name: 'coverage',   label: 'Coverage', field: 'total_insights', align: 'left' },
  { name: 'summary',    label: 'Summary',  field: 'summary_text', align: 'left' },
  { name: 'created_by', label: 'Created',  field: 'created_at', align: 'left' },
  { name: 'actions',    label: '',         field: 'actions',    align: 'right' },
]
const aggDetailOpen = ref(false)
const aggSelected = ref(null)
let aggPollTimer = null

function aggPreset(days) {
  agg.value.to = todayIso()
  agg.value.from = isoDaysAgo(days)
}

async function loadAggregates() {
  agg.value.loading = true
  try {
    const params = {
      page: agg.value.pagination.page,
      page_size: agg.value.pagination.rowsPerPage,
    }
    const res = await api.get('/insight-aggregates/', { params })
    aggRows.value = res.data.results || res.data
    agg.value.pagination.rowsNumber = res.data.count ?? aggRows.value.length
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Failed to load aggregates' })
  } finally {
    agg.value.loading = false
  }
  schedulePolling()
}

function onAggRequest(props) {
  agg.value.pagination = props.pagination
  loadAggregates()
}

const hasUnfinished = computed(() =>
  aggRows.value.some(r => r.status === 'pending' || r.status === 'processing'),
)

function schedulePolling() {
  clearTimeout(aggPollTimer)
  if (!hasUnfinished.value && !(aggSelected.value &&
      ['pending', 'processing'].includes(aggSelected.value.status))) {
    return
  }
  aggPollTimer = setTimeout(async () => {
    await loadAggregates()
    if (aggSelected.value && ['pending', 'processing', 'failed'].includes(aggSelected.value.status)) {
      try {
        const res = await api.get(`/insight-aggregates/${aggSelected.value.id}/`)
        aggSelected.value = res.data
      } catch { /* ignore */ }
    }
  }, 3000)
}

async function createAggregate() {
  if (!agg.value.from || !agg.value.to) return
  if (agg.value.from > agg.value.to) {
    $q.notify({ type: 'negative', message: '“From” must be on or before “To”' })
    return
  }
  agg.value.creating = true
  try {
    const res = await api.post('/insight-aggregates/', {
      date_from: agg.value.from,
      date_to: agg.value.to,
    })
    $q.notify({ type: 'positive', message: 'Aggregation started — usually completes in <1 min' })
    aggSelected.value = res.data
    aggDetailOpen.value = true
    await loadAggregates()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Failed to start aggregation' })
  } finally {
    agg.value.creating = false
  }
}

async function openAggDetail(_, row) {
  try {
    const res = await api.get(`/insight-aggregates/${row.id}/`)
    aggSelected.value = res.data
    aggDetailOpen.value = true
    schedulePolling()
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to load aggregate' })
  }
}

async function retryAggregate(row, alreadyOpen = false) {
  try {
    const res = await api.post(`/insight-aggregates/${row.id}/retry/`)
    if (alreadyOpen) aggSelected.value = res.data
    $q.notify({ type: 'positive', message: 'Retry queued' })
    loadAggregates()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Retry failed' })
  }
}

async function downloadAggregatePdf(row) {
  if (!row || row.status !== 'done') return
  row._pdfLoading = true
  try {
    const res = await api.get(`/insight-aggregates/${row.id}/pdf/`, { responseType: 'blob' })
    const blob = new Blob([res.data], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `aggregate-insights-${row.date_from}-to-${row.date_to}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'PDF download failed' })
  } finally {
    row._pdfLoading = false
  }
}

async function deleteAggregate(row) {
  $q.dialog({
    title: 'Delete aggregate?',
    message: `Delete the aggregate for ${row.date_from} → ${row.date_to}?`,
    cancel: true, persistent: true,
    ok: { color: 'negative', label: 'Delete' },
  }).onOk(async () => {
    try {
      await api.delete(`/insight-aggregates/${row.id}/`)
      $q.notify({ type: 'positive', message: 'Deleted' })
      loadAggregates()
    } catch (e) {
      $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Delete failed' })
    }
  })
}

function formatCategory(cat) {
  const map = {
    product: 'Product / Offer',
    market_ayurveda: 'Ayurveda Market',
    competitors: 'Competitors / Alternatives',
    manufacturers: 'Manufacturers / Brands',
    platform_ask_ayurveda: 'Ask Ayurveda Platform',
    prescribing_procurement: 'Prescribing / Procurement',
    earning_money: 'Earnings / Margins',
    other: 'Other',
  }
  return map[String(cat || '').toLowerCase()] || 'Other'
}

function hasSentiments(c) {
  const sb = c.sentiment_breakdown || {}
  return Object.values(sb).some(v => Number(v) > 0)
}

function sentimentColor(k) {
  return { positive: 'green', negative: 'red', neutral: 'grey-7', mixed: 'amber-8' }[k] || 'grey'
}

function maxPartnerCount() {
  const list = aggSelected.value?.clusters_json?.clusters || []
  return Math.max(1, ...list.map(c => c.partner_count || 0))
}

function barPct(c) {
  return Math.round(((c.partner_count || 0) / maxPartnerCount()) * 100)
}

function barColor(c) {
  const cat = String(c.category || '').toLowerCase()
  return {
    platform_ask_ayurveda: '#7E57C2',
    earning_money: '#EF6C00',
    prescribing_procurement: '#2E7D32',
    competitors: '#C62828',
    manufacturers: '#AD1457',
    product: '#1565C0',
    market_ayurveda: '#00838F',
  }[cat] || '#546E7A'
}

watch(tab, (val) => {
  if (val === 'aggregate' && !aggRows.value.length) loadAggregates()
})

onMounted(() => {
  if (route.query.contact) search.value = ''
  load()
})

onUnmounted(() => {
  clearTimeout(aggPollTimer)
})
</script>

<style scoped>
.partner-link { color: #2E7D32; text-decoration: none; font-weight: 500; font-size: 13px; }
.partner-link:hover { text-decoration: underline; }
.ellipsis-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.insight-detail-card { max-width: 1080px; margin: 0 auto; }
.insight-md { font-size: 14px; line-height: 1.65; color: #212121; }
.insight-md :deep(ul) { margin: 8px 0; padding-left: 1.25rem; }

.cluster-card {
  background: #FFF;
  border: 1px solid #E0E0E0;
  border-radius: 10px;
  padding: 14px 16px;
}
.cluster-bar {
  width: 100%;
  height: 6px;
  background: #ECEFF1;
  border-radius: 3px;
  overflow: hidden;
}
.cluster-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 200ms ease;
}
.recommended-box {
  background: #FFF8E1;
  border-left: 3px solid #FFB300;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  color: #4E342E;
}
.quote-row {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  flex-wrap: wrap;
}
</style>
