<template>
  <q-page class="q-pa-lg operator-activity-page">
    <!-- Header -->
    <div class="row items-center justify-between q-mb-md">
      <div>
        <div class="text-h5 text-weight-bold text-dark">Operator Activity</div>
        <div class="text-caption text-grey-6 q-mt-xs">
          Track when operators work in CRM, see daily timeline and gaps
        </div>
      </div>
      <q-btn flat round icon="refresh" color="grey-6" :loading="anyLoading" @click="reload">
        <q-tooltip>Refresh</q-tooltip>
      </q-btn>
    </div>

    <!-- Tabs -->
    <q-tabs
      v-model="tab"
      dense
      class="q-mb-md"
      active-color="primary"
      indicator-color="primary"
      align="left"
      no-caps
    >
      <q-tab name="day"     icon="today"           label="Day" />
      <q-tab name="week"    icon="calendar_view_week" label="Week" />
      <q-tab name="events"  icon="bubble_chart"    label="Events" />
    </q-tabs>

    <q-tab-panels v-model="tab" animated keep-alive class="bg-transparent">
      <!-- DAY VIEW -->
      <q-tab-panel name="day" class="q-pa-none">
        <div class="row q-col-gutter-md q-mb-md items-end">
          <div class="col-auto">
            <q-input v-model="dayDate" type="date" outlined dense label="Date" style="min-width:160px" />
          </div>
          <div class="col-auto text-caption text-grey-6">
            {{ summaryHeader }}
          </div>
        </div>

        <div v-if="activityStore.loading.summary" class="row justify-center q-py-xl">
          <q-spinner-dots color="primary" size="40px" />
        </div>

        <div v-else-if="!summaryRows.length" class="text-center text-grey-5 q-py-xl">
          <q-icon name="schedule" size="48px" class="q-mb-sm" />
          <div>No operators / no activity recorded for this day</div>
        </div>

        <div v-else class="day-grid">
          <div v-for="op in summaryRows" :key="op.user_id" class="day-row">
            <div class="day-row__head">
              <div class="day-row__name">{{ op.full_name }}</div>
              <div class="day-row__metrics">
                <div class="metric"><strong>{{ formatTime(op.first_event) }}</strong><span>start</span></div>
                <div class="metric"><strong>{{ formatTime(op.last_event) }}</strong><span>end</span></div>
                <div class="metric"><strong>{{ op.active_minutes }}m</strong><span>active</span></div>
                <div class="metric"><strong>{{ op.sessions_count }}</strong><span>sessions</span></div>
                <div class="metric"><strong>{{ op.longest_gap_minutes }}m</strong><span>longest gap</span></div>
                <div class="metric"><strong>{{ op.total_events }}</strong><span>events</span></div>
              </div>
            </div>
            <ActivityTimeline
              :buckets="bucketsFor(op.user_id)"
              :bucket-minutes="bucketsBucketSize(op.user_id) || 5"
              :gap-minutes="summary?.gap_threshold_minutes || 15"
              :first-event="op.first_event"
              :last-event="op.last_event"
            />
          </div>
        </div>
      </q-tab-panel>

      <!-- WEEK VIEW -->
      <q-tab-panel name="week" class="q-pa-none">
        <div class="row q-col-gutter-md q-mb-md items-end">
          <div class="col-auto">
            <q-input v-model="weekFrom" type="date" outlined dense label="From" style="min-width:160px" />
          </div>
          <div class="col-auto">
            <q-input v-model="weekTo" type="date" outlined dense label="To" style="min-width:160px" />
          </div>
          <div class="col-auto">
            <q-select
              v-model="weekUserIds"
              :options="userOptions"
              label="Operators"
              outlined dense
              multiple emit-value map-options use-chips
              option-value="value" option-label="label"
              style="min-width:240px"
            />
          </div>
          <div class="col-auto">
            <q-btn unelevated color="primary" label="Apply" icon="refresh" @click="loadHeatmap" />
          </div>
        </div>

        <div v-if="activityStore.loading.heatmap" class="row justify-center q-py-xl">
          <q-spinner-dots color="primary" size="40px" />
        </div>

        <ActivityHeatmap
          v-else
          :users="heatmap?.users || []"
          :cells="heatmap?.cells || []"
          :bucket-minutes="heatmap?.bucket_minutes || 30"
          :date-from="heatmap?.date_from"
          :date-to="heatmap?.date_to"
          @cell-click="onHeatmapCellClick"
        />
      </q-tab-panel>

      <!-- EVENTS VIEW -->
      <q-tab-panel name="events" class="q-pa-none">
        <div class="row q-col-gutter-md q-mb-md items-end">
          <div class="col-auto">
            <q-select
              v-model="eventsUserId"
              :options="userOptions"
              label="Operator"
              outlined dense
              emit-value map-options
              option-value="value" option-label="label"
              style="min-width:220px"
            />
          </div>
          <div class="col-auto">
            <q-input v-model="eventsDate" type="date" outlined dense label="Date" style="min-width:160px" />
          </div>
          <div class="col-auto">
            <q-select
              v-model="eventsType"
              :options="eventTypeOptions"
              label="Type filter"
              outlined dense clearable
              emit-value map-options
              option-value="value" option-label="label"
              style="min-width:180px"
            />
          </div>
          <div class="col-auto">
            <q-btn unelevated color="primary" label="Load" icon="search" @click="loadEvents" />
          </div>
        </div>

        <div v-if="activityStore.loading.events" class="row justify-center q-py-xl">
          <q-spinner-dots color="primary" size="40px" />
        </div>

        <template v-else>
          <ActivityScatter :events="eventList" />

          <q-table
            v-if="eventList.length"
            class="q-mt-md"
            flat bordered dense
            :rows="eventList"
            :columns="eventColumns"
            row-key="id"
            :pagination="{ rowsPerPage: 25 }"
            no-data-label="No events"
          >
            <template v-slot:body-cell-event_type="props">
              <q-td :props="props">
                <q-badge :color="badgeColor(props.row.event_type)" :label="typeLabel(props.row.event_type)" />
              </q-td>
            </template>
            <template v-slot:body-cell-created_at="props">
              <q-td :props="props">{{ formatDateTime(props.row.created_at) }}</q-td>
            </template>
          </q-table>
        </template>
      </q-tab-panel>
    </q-tab-panels>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useActivityStore } from 'src/stores/activity'
import ActivityTimeline from 'src/components/ActivityTimeline.vue'
import ActivityHeatmap  from 'src/components/ActivityHeatmap.vue'
import ActivityScatter  from 'src/components/ActivityScatter.vue'
import { formatServerTime, formatServerDateTime, getServerDate } from 'src/utils/serverTime'

const activityStore = useActivityStore()
const route = useRoute()
const router = useRouter()

const tab = ref('day')

// ---------- DAY ----------
const today = getServerDate()
const dayDate = ref(today)
const summary = computed(() => activityStore.summary)
const summaryRows = computed(() => summary.value?.operators || [])

// per-user timeline cache (loaded lazily after summary arrives)
const timelinesByUser = ref({})

const summaryHeader = computed(() => {
  if (!summary.value) return ''
  const n = summaryRows.value.length
  const active = summaryRows.value.filter(r => r.active_minutes > 0).length
  return `${active} of ${n} operators active on ${summary.value.date}`
})

function bucketsFor (userId) {
  return timelinesByUser.value[userId]?.buckets || []
}
function bucketsBucketSize (userId) {
  return timelinesByUser.value[userId]?.bucket_minutes
}

async function loadDay () {
  await activityStore.fetchSummary({ date: dayDate.value })
  if (summary.value?.operators?.length) {
    syncUserOptions(summary.value.operators.map(o => ({ user_id: o.user_id, full_name: o.full_name })))
  }
  // Fetch a 5-min timeline for every operator that had at least one event.
  const tasks = (summary.value?.operators || [])
    .filter(op => op.total_events > 0)
    .map(async op => {
      const data = await activityStore.fetchTimeline({ userId: op.user_id, date: dayDate.value, bucket: 5 })
      timelinesByUser.value = { ...timelinesByUser.value, [op.user_id]: data }
    })
  await Promise.all(tasks)
}

// ---------- WEEK ----------
const weekTo = ref(today)
const weekFrom = ref((() => {
  // 6 days back, anchored at noon UTC for DST safety.
  const d = new Date(`${today}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() - 6)
  return d.toISOString().slice(0, 10)
})())
const weekUserIds = ref([])
const heatmap = computed(() => activityStore.heatmap)

async function loadHeatmap () {
  await activityStore.fetchHeatmap({
    dateFrom: weekFrom.value,
    dateTo:   weekTo.value,
    userIds:  weekUserIds.value,
  })
  // Sync user options for the events tab (so we can pick from the same list).
  if (heatmap.value?.users?.length) {
    syncUserOptions(heatmap.value.users)
  }
}

function onHeatmapCellClick (cell) {
  dayDate.value = cell.date
  tab.value = 'day'
  if (cell.user_id) eventsUserId.value = cell.user_id
}

// ---------- EVENTS ----------
const eventsUserId = ref(null)
const eventsDate   = ref(today)
const eventsType   = ref(null)

const eventList = computed(() => activityStore.events?.results || [])

const userOptions = ref([])
function syncUserOptions (users) {
  // Merge so we never lose entries that came from a different endpoint.
  const map = new Map(userOptions.value.map(o => [o.value, o]))
  for (const u of users) {
    map.set(u.user_id, { value: u.user_id, label: u.full_name })
  }
  userOptions.value = Array.from(map.values())
  if (!eventsUserId.value && userOptions.value.length) {
    eventsUserId.value = userOptions.value[0].value
  }
}

async function loadEvents () {
  if (!eventsUserId.value) return
  await activityStore.fetchEvents({
    userId:    eventsUserId.value,
    date:      eventsDate.value,
    eventType: eventsType.value,
    pageSize:  500,
  })
}

const eventTypeOptions = [
  { value: 'page_view',      label: 'Page view' },
  { value: 'partner_open',   label: 'Partner open' },
  { value: 'partner_close',  label: 'Partner close' },
  { value: 'contact_create', label: 'Contact added' },
  { value: 'task_create',    label: 'Task created' },
  { value: 'task_complete',  label: 'Task done' },
  { value: 'note_create',    label: 'Note' },
  { value: 'status_change',  label: 'Status change' },
  { value: 'call_log',       label: 'Call' },
  { value: 'heartbeat',      label: 'Heartbeat' },
  { value: 'login',          label: 'Login' },
  { value: 'logout',         label: 'Logout' },
  { value: 'other',          label: 'Other' },
]

function typeLabel (t) {
  return eventTypeOptions.find(o => o.value === t)?.label || t
}

const TYPE_BADGE_COLORS = {
  partner_open: 'green-7', partner_close: 'green-3',
  contact_create: 'blue-7', task_create: 'purple-7', task_complete: 'deep-purple-7',
  note_create: 'orange-7', status_change: 'cyan-7', call_log: 'red-7',
  page_view: 'grey-6', heartbeat: 'grey-4',
  login: 'green-6', logout: 'red-6', other: 'grey-7',
}
function badgeColor (t) { return TYPE_BADGE_COLORS[t] || 'grey-6' }

const eventColumns = [
  { name: 'created_at',  label: 'Time',     field: 'created_at',  align: 'left', sortable: true },
  { name: 'event_type',  label: 'Type',     field: 'event_type',  align: 'left', sortable: true },
  { name: 'object_type', label: 'Object',   field: row => row.object_id ? `${row.object_type}#${row.object_id}` : (row.object_type || ''), align: 'left' },
  { name: 'path',        label: 'Path',     field: 'path',        align: 'left' },
]

function formatTime (iso) {
  return formatServerTime(iso)
}
function formatDateTime (iso) {
  return formatServerDateTime(iso)
}

const anyLoading = computed(() =>
  Object.values(activityStore.loading).some(Boolean)
)

async function reload () {
  if (tab.value === 'day') await loadDay()
  else if (tab.value === 'week') await loadHeatmap()
  else await loadEvents()
}

watch(dayDate, loadDay)
watch(tab, async (newTab) => {
  if (newTab === 'week' && !heatmap.value) await loadHeatmap()
  else if (newTab === 'events' && !activityStore.events && eventsUserId.value) {
    await loadEvents()
  }
})

onMounted(async () => {
  // Bootstrap the user list from the heatmap call so other tabs have it.
  await Promise.all([loadDay(), loadHeatmap()])
  if (route.query.user_id && route.query.date) {
    tab.value = 'events'
    eventsUserId.value = Number(route.query.user_id)
    eventsDate.value = String(route.query.date)
    await loadEvents()
  }
})

// Update URL when tab/date changes — makes sharing links easy.
watch([tab, dayDate], () => {
  router.replace({ query: { ...route.query, tab: tab.value, date: dayDate.value } })
})
</script>

<style scoped>
.operator-activity-page { max-width: 1400px; margin: 0 auto; }

.day-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.day-row {
  background: #FAFAFA;
  border: 1px solid #EEEEEE;
  border-radius: 8px;
  padding: 12px 14px;
}
.day-row__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.day-row__name {
  font-weight: 700;
  color: #212121;
  font-size: 14px;
}
.day-row__metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: flex-end;
}
.day-row__metrics .metric {
  display: flex;
  flex-direction: column;
  font-size: 11px;
  color: #9E9E9E;
  line-height: 1.1;
}
.day-row__metrics .metric strong {
  font-size: 14px;
  color: #212121;
}
</style>
