<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md q-gutter-sm">
      <div>
        <div class="text-h6 q-mb-xs row items-center">
          <q-icon name="insights" class="q-mr-sm text-deep-purple-7" />
          General Insights
        </div>
        <div class="text-caption text-grey-7">
          Top 15 cross-call themes ranked by how many unique partners voiced them.
          Same idea phrased differently is merged into one theme.
        </div>
      </div>
      <q-space />

      <q-btn-toggle
        v-model="period"
        no-caps unelevated dense rounded
        color="grey-3" toggle-color="deep-purple-7"
        text-color="grey-9" toggle-text-color="white"
        :options="periodOptions"
        @update:model-value="loadGeneral(false)"
      />

      <q-btn
        outline dense no-caps color="deep-purple-7"
        icon="refresh" label="Refresh"
        :loading="refreshing"
        @click="loadGeneral(true)"
      >
        <q-tooltip>Force a fresh rebuild now</q-tooltip>
      </q-btn>
    </div>

    <q-card flat bordered class="q-mb-md" style="border-radius:12px;">
      <q-card-section class="q-py-sm row items-center q-gutter-sm">
        <q-chip dense outline icon="event">
          {{ data?.date_from || '—' }} → {{ data?.date_to || '—' }}
        </q-chip>
        <q-chip dense outline icon="phone_in_talk">
          {{ data?.total_calls ?? 0 }} calls
        </q-chip>
        <q-chip dense outline icon="format_list_bulleted">
          {{ data?.total_insights ?? 0 }} raw insights
        </q-chip>
        <q-chip dense color="deep-purple-7" text-color="white" icon="people">
          {{ data?.unique_partners ?? 0 }} unique partners
        </q-chip>
        <q-chip dense outline :color="statusColor(data?.status)" :text-color="statusText(data?.status)">
          <q-spinner-dots
            v-if="data?.status === 'pending' || data?.status === 'processing'"
            size="10px" class="q-mr-xs"
          />
          {{ data?.status || '—' }}
        </q-chip>
        <q-space />
        <span class="text-caption text-grey-6">
          Last refreshed {{ fmtRelative(data?.completed_at) }}
        </span>
      </q-card-section>
    </q-card>

    <div v-if="loading && !data" class="q-pa-xl text-center">
      <q-spinner-dots color="deep-purple-7" size="40px" />
      <div class="text-caption text-grey-7 q-mt-sm">Loading General Insights…</div>
    </div>

    <div v-else-if="data?.status === 'pending' || data?.status === 'processing'" class="q-pa-xl text-center">
      <q-spinner-dots color="deep-purple-7" size="40px" />
      <div class="text-caption text-grey-7 q-mt-sm">
        Building report — usually completes in &lt;1 min. Auto-refreshing…
      </div>
    </div>

    <div v-else-if="data?.status === 'failed'">
      <q-banner class="bg-red-1 text-red-9" rounded>
        <template #avatar><q-icon name="error" /></template>
        Generation failed: <code>{{ data?.last_error || 'unknown' }}</code>
        <template #action>
          <q-btn flat color="negative" no-caps label="Retry" @click="loadGeneral(true)" />
        </template>
      </q-banner>
    </div>

    <div v-else-if="!clusters.length" class="q-pa-xl text-center text-grey-6">
      No clustered themes — period had no material insights.
    </div>

    <template v-else>
      <q-card v-if="executiveSummary" flat bordered class="q-mb-md">
        <q-card-section class="q-py-sm">
          <div class="text-subtitle2 q-mb-xs">Executive summary</div>
          <div style="white-space:pre-wrap;">{{ executiveSummary }}</div>
        </q-card-section>
      </q-card>

      <q-card v-if="topPriorities.length" flat bordered class="q-mb-md">
        <q-card-section class="q-py-sm">
          <div class="text-subtitle2 q-mb-xs">Top priorities</div>
          <ul style="margin:0; padding-left:1.25rem;">
            <li v-for="(p, i) in topPriorities" :key="i" class="q-mb-xs">{{ p }}</li>
          </ul>
        </q-card-section>
      </q-card>

      <div class="text-subtitle2 q-mb-sm">
        Top {{ clusters.length }} themes
        <span class="text-caption text-grey-6 q-ml-xs">
          ranked by unique partners (% of {{ data.unique_partners }} partners spoken to in this window)
        </span>
      </div>

      <div
        v-for="(c, i) in clusters"
        :key="i"
        class="cluster-card q-mb-md"
        :style="{ borderLeftColor: barColor(c.category) }"
      >
        <div class="row items-start no-wrap q-mb-xs">
          <div class="rank-badge q-mr-md" :style="{ background: barColor(c.category) }">
            {{ i + 1 }}
          </div>
          <div class="col">
            <div class="text-h6 text-weight-medium" style="line-height:1.3;">{{ c.theme }}</div>
            <div class="text-caption text-grey-7 q-mt-xs">
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
          </div>
          <div class="text-right q-ml-md">
            <div class="text-h5 text-weight-bold" :style="{ color: barColor(c.category) }">
              {{ c.partner_count }}
            </div>
            <div class="text-caption text-grey-7" style="margin-top:-2px;">
              partner{{ c.partner_count === 1 ? '' : 's' }}
            </div>
            <div class="text-caption text-grey-9 q-mt-xs">
              <b>{{ percentOfPartners(c) }}%</b> of {{ data.unique_partners }}
            </div>
            <div class="text-caption text-grey-6">{{ c.mention_count }} mention{{ c.mention_count === 1 ? '' : 's' }}</div>
          </div>
        </div>

        <div class="cluster-bar q-mb-sm q-mt-xs">
          <div class="cluster-bar-fill" :style="{ width: percentOfPartners(c) + '%', background: barColor(c.category) }" />
        </div>

        <div v-if="c.explanation" style="white-space:pre-wrap;" class="q-mb-sm text-body2">
          {{ c.explanation }}
        </div>

        <div v-if="c.recommended_action" class="recommended-box q-mb-sm">
          <strong>Recommended action:</strong> {{ c.recommended_action }}
        </div>

        <div v-if="(c.representative_quotes || []).length">
          <div class="text-caption text-grey-7 q-mb-xs">Representative quotes</div>
          <div
            v-for="(q, qi) in (c.representative_quotes || []).slice(0, 3)"
            :key="qi"
            class="quote-row"
          >
            <q-icon name="format_quote" size="14px" class="q-mr-xs text-grey-6" />
            <span class="text-caption text-grey-9">«{{ q.quote }}»</span>
            <span v-if="q.partner_id" class="text-caption text-grey-6 q-ml-xs">
              —
              <router-link :to="`/partners/${q.partner_id}`" class="partner-link">
                {{ q.partner_name || 'Partner' }}
              </router-link>
            </span>
          </div>
        </div>
      </div>
    </template>
  </q-page>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useQuasar } from 'quasar'
import { api } from 'boot/axios'

const $q = useQuasar()

const period = ref('30d')
const periodOptions = [
  { label: '30 days', value: '30d' },
  { label: '60 days', value: '60d' },
  { label: '180 days', value: '180d' },
  { label: 'All time', value: 'all' },
]

const loading = ref(false)
const refreshing = ref(false)
const data = ref(null)
let pollTimer = null

const clusters = computed(() => data.value?.clusters_json?.clusters || [])
const executiveSummary = computed(() =>
  (data.value?.summary_text || data.value?.clusters_json?.executive_summary || '').trim(),
)
const topPriorities = computed(() => data.value?.clusters_json?.top_priorities || [])

function statusColor(st) {
  return { done: 'green-2', processing: 'blue-2', pending: 'grey-3', failed: 'red-2' }[st] || 'grey-2'
}
function statusText(st) {
  return { done: 'green-9', processing: 'blue-9', pending: 'grey-8', failed: 'red-9' }[st] || 'grey-8'
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
function barColor(category) {
  const cat = String(category || '').toLowerCase()
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
function percentOfPartners(c) {
  const total = data.value?.unique_partners || 0
  if (!total) return 0
  return Math.round(((c.partner_count || 0) / total) * 100)
}

async function loadGeneral(force) {
  if (force) refreshing.value = true
  else if (!data.value) loading.value = true
  try {
    const url = `/insight-aggregates/general/?period=${period.value}`
    const res = force ? await api.post(url) : await api.get(url)
    data.value = res.data
    schedulePolling()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Failed to load General Insights' })
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function schedulePolling() {
  clearTimeout(pollTimer)
  if (!data.value) return
  if (data.value.status === 'pending' || data.value.status === 'processing') {
    pollTimer = setTimeout(async () => {
      try {
        const res = await api.get(`/insight-aggregates/general/?period=${period.value}`)
        data.value = res.data
        schedulePolling()
      } catch { /* ignore */ }
    }, 4000)
  }
}

watch(period, () => {
  data.value = null
  loadGeneral(false)
})

onMounted(() => loadGeneral(false))
onUnmounted(() => clearTimeout(pollTimer))
</script>

<style scoped>
.cluster-card {
  background: #FFF;
  border: 1px solid #E0E0E0;
  border-left-width: 4px;
  border-radius: 10px;
  padding: 14px 18px;
  transition: box-shadow 150ms ease;
}
.cluster-card:hover { box-shadow: 0 1px 6px rgba(94, 53, 177, 0.12); }
.rank-badge {
  width: 36px; height: 36px;
  border-radius: 50%;
  color: white;
  font-weight: 700; font-size: 16px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
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
  transition: width 220ms ease;
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
  margin-bottom: 4px;
}
.partner-link { color: #2E7D32; text-decoration: none; font-weight: 500; }
.partner-link:hover { text-decoration: underline; }
</style>
