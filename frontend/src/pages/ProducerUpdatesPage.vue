<template>
  <q-page class="updates-page">
    <div class="q-px-md q-pt-sm">
      <AiAutoGenBanner v-if="activeTab === 'daily'"  job-id="producer_daily_report" />
      <AiAutoGenBanner v-if="activeTab === 'weekly'" job-id="producer_weekly_report" />
    </div>
    <div class="updates-layout">

      <!-- ── Left sidebar ── -->
      <div class="updates-sidebar">
        <!-- Tabs -->
        <div class="sidebar-tabs">
          <div
            class="sidebar-tab"
            :class="{ 'sidebar-tab--active': activeTab === 'daily' }"
            @click="switchTab('daily')"
          >
            <q-icon name="today" size="16px" />
            <span>Daily</span>
            <q-badge v-if="pendingCount('daily')" color="orange-7" rounded :label="pendingCount('daily')" style="font-size:10px;" />
          </div>
          <div
            class="sidebar-tab"
            :class="{ 'sidebar-tab--active': activeTab === 'weekly' }"
            @click="switchTab('weekly')"
          >
            <q-icon name="date_range" size="16px" />
            <span>Weekly</span>
            <q-badge v-if="pendingCount('weekly')" color="orange-7" rounded :label="pendingCount('weekly')" style="font-size:10px;" />
          </div>
        </div>

        <!-- Generate button (admin) -->
        <div class="sidebar-generate" v-if="authStore.isAdmin">
          <q-btn
            unelevated dense
            :color="activeTab === 'daily' ? 'green-8' : 'blue-8'"
            :icon="generating ? 'hourglass_empty' : 'bolt'"
            :label="generating ? 'Generating…' : `Generate ${activeTab === 'daily' ? 'daily' : 'weekly'}`"
            :loading="generating"
            style="border-radius:8px;width:100%;font-size:12px;"
            @click="generateNow"
          >
            <template #loading><q-spinner-dots size="16px" /></template>
          </q-btn>
        </div>

        <!-- Report list -->
        <div class="report-list">
          <div v-if="!currentReports.length" class="no-reports">
            <q-icon name="description" size="32px" color="grey-3" />
            <div>No reports yet</div>
            <div v-if="authStore.isAdmin" style="font-size:11px;color:#BDBDBD;margin-top:4px;">Click “Generate”</div>
          </div>

          <div
            v-for="r in currentReports"
            :key="r.id"
            class="report-item"
            :class="{ 'report-item--active': activeReport?.id === r.id }"
            @click="selectReport(r)"
          >
            <div class="ri-title-row">
              <q-spinner-dots v-if="isInProgress(r)" color="green-6" size="12px" class="q-mr-xs" />
              <q-icon v-else-if="r.status === 'error'" name="error_outline" color="negative" size="14px" class="q-mr-xs" />
              <q-icon v-else :name="activeTab === 'daily' ? 'today' : 'date_range'" :color="activeTab === 'daily' ? 'green-7' : 'blue-7'" size="14px" class="q-mr-xs" />
              <div class="ri-title">{{ r.title }}</div>
            </div>
            <div class="ri-meta">{{ fmtDatetime(r.created_at) }}</div>
          </div>
        </div>
      </div>

      <!-- ── Right: content ── -->
      <div class="report-content">

        <!-- No report selected -->
        <div v-if="!activeReport" class="empty-state">
          <q-icon :name="activeTab === 'daily' ? 'today' : 'date_range'" size="64px" color="grey-3" />
          <div class="empty-title">{{ activeTab === 'daily' ? 'Daily Updates' : 'Weekly Updates' }}</div>
          <div class="empty-sub">
            {{ activeTab === 'daily'
              ? 'Generated automatically every weekday at 18:00 Riga time'
              : 'Generated automatically every Friday at 14:00 Riga time' }}
          </div>
          <div v-if="authStore.isAdmin" class="empty-sub q-mt-sm">
            Click “Generate” to create a report now
          </div>
        </div>

        <!-- Generating -->
        <div v-else-if="isInProgress(activeReport)" class="generating-state">
          <q-spinner-dots :color="activeTab === 'daily' ? 'green-7' : 'blue-7'" size="48px" />
          <div class="gen-text">Analysing data and building the report…</div>
          <div class="gen-sub">Usually takes 15–30 seconds</div>
        </div>

        <!-- Error -->
        <div v-else-if="activeReport.status === 'error'" class="error-state">
          <q-icon name="error_outline" color="negative" size="48px" />
          <div class="gen-text text-negative">Generation error</div>
          <div class="gen-sub">{{ activeReport.error_message || 'Unknown error' }}</div>
        </div>

        <!-- Done -->
        <div v-else-if="activeReport.status === 'done'" class="report-display">
          <div class="report-toolbar">
            <div class="report-meta">
              <q-icon name="schedule" color="grey-5" size="14px" />
              <span>{{ fmtDatetime(activeReport.created_at) }}</span>
              <q-chip dense size="sm"
                :color="activeTab === 'daily' ? 'green-2' : 'blue-2'"
                :text-color="activeTab === 'daily' ? 'green-9' : 'blue-9'"
                style="font-size:10px;"
              >
                {{ activeTab === 'daily' ? 'Daily' : 'Weekly' }}
              </q-chip>
            </div>
            <div class="row q-gutter-xs">
              <q-btn flat dense icon="download" label=".md" color="grey-7"
                style="border-radius:8px;font-size:12px" @click="downloadReport" />
              <q-btn flat dense icon="content_copy" color="grey-7"
                style="border-radius:8px;font-size:12px" @click="copyReport">
                <q-tooltip>Copy Markdown</q-tooltip>
              </q-btn>
            </div>
          </div>
          <div class="report-body markdown-body" v-html="renderMarkdown(activeReport.content)" />
        </div>

      </div>
    </div>
  </q-page>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useQuasar } from 'quasar'
import { useAuthStore } from 'src/stores/auth'
import { api } from 'boot/axios'
import { marked } from 'marked'
import AiAutoGenBanner from 'components/AiAutoGenBanner.vue'

const $q        = useQuasar()
const authStore = useAuthStore()

const activeTab    = ref('daily')
const dailyReports  = ref([])
const weeklyReports = ref([])
const activeReport  = ref(null)
const generating    = ref(false)
let pollTimer       = null

const currentReports = computed(() =>
  activeTab.value === 'daily' ? dailyReports.value : weeklyReports.value
)

function pendingCount(type) {
  const list = type === 'daily' ? dailyReports.value : weeklyReports.value
  return list.filter(r => isInProgress(r)).length || 0
}

function isInProgress(r) {
  return r.status === 'pending' || r.status === 'generating'
}

function selectReport(r) {
  activeReport.value = r
}

async function fetchReports(type) {
  const res = await api.get('/producer-updates/', { params: { type } })
  const list = res.data.results ?? res.data
  if (type === 'daily')  dailyReports.value  = list
  else                   weeklyReports.value = list

  // Update activeReport if it's in this list
  if (activeReport.value && activeReport.value.report_type === type) {
    const fresh = list.find(r => r.id === activeReport.value.id)
    if (fresh) activeReport.value = fresh
  }
}

function switchTab(tab) {
  activeTab.value   = tab
  activeReport.value = null
}

async function generateNow() {
  generating.value = true
  try {
    const res = await api.post('/producer-updates/generate/', { type: activeTab.value })
    const report = res.data
    if (activeTab.value === 'daily')  dailyReports.value  = [report, ...dailyReports.value]
    else                               weeklyReports.value = [report, ...weeklyReports.value]
    activeReport.value = report
    startPolling()
  } catch (e) {
    $q.notify({ type: 'negative', message: e?.response?.data?.error || 'Generation error' })
  } finally {
    generating.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    const hasInProgress =
      dailyReports.value.some(isInProgress) ||
      weeklyReports.value.some(isInProgress)
    if (!hasInProgress) { stopPolling(); return }
    await Promise.all([fetchReports('daily'), fetchReports('weekly')])
  }, 3000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

function renderMarkdown(md) { return md ? marked.parse(md) : '' }

function downloadReport() {
  if (!activeReport.value) return
  const blob = new Blob([activeReport.value.content], { type: 'text/markdown;charset=utf-8' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href = url
  a.download = `producer-${activeTab.value}-${new Date().toISOString().slice(0,10)}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function copyReport() {
  if (!activeReport.value) return
  navigator.clipboard.writeText(activeReport.value.content)
  $q.notify({ type: 'positive', message: 'Copied', timeout: 1500 })
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
}
function fmtDatetime(iso) {
  return new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

watch(currentReports, (list) => {
  const hasInProgress = list.some(isInProgress)
  if (hasInProgress) startPolling()
}, { deep: true })

onMounted(async () => {
  await Promise.all([fetchReports('daily'), fetchReports('weekly')])
  const hasInProgress =
    dailyReports.value.some(isInProgress) ||
    weeklyReports.value.some(isInProgress)
  if (hasInProgress) startPolling()
  // Auto-select latest report
  if (currentReports.value.length) activeReport.value = currentReports.value[0]
})

onUnmounted(stopPolling)
</script>

<style scoped>
.updates-page   { padding: 0; height: calc(100vh - 50px); }
.updates-layout { display: flex; height: 100%; overflow: hidden; }

/* Sidebar */
.updates-sidebar {
  width: 260px; flex-shrink: 0;
  border-right: 1px solid #F0F0F0;
  background: #FAFAFA;
  display: flex; flex-direction: column; overflow: hidden;
}
.sidebar-tabs {
  display: flex; border-bottom: 1px solid #F0F0F0; flex-shrink: 0;
}
.sidebar-tab {
  flex: 1; display: flex; align-items: center; justify-content: center;
  gap: 5px; padding: 12px 8px; font-size: 12px; font-weight: 600;
  color: #9E9E9E; cursor: pointer; border-bottom: 2px solid transparent;
  transition: all 0.15s;
}
.sidebar-tab:hover { background: #F5F5F5; color: #424242; }
.sidebar-tab--active { color: #2E7D32; border-bottom-color: #2E7D32; background: #fff; }

.sidebar-generate { padding: 10px; flex-shrink: 0; border-bottom: 1px solid #F0F0F0; }

.report-list { flex: 1; overflow-y: auto; padding: 8px; }
.no-reports {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 40px 16px; color: #BDBDBD; font-size: 12px; text-align: center;
}
.report-item {
  position: relative; padding: 10px 12px; border-radius: 10px;
  cursor: pointer; margin-bottom: 4px; transition: background 0.12s;
}
.report-item:hover { background: #F0F0F0; }
.report-item--active { background: #E8F5E9; }
.ri-title-row { display: flex; align-items: flex-start; gap: 4px; margin-bottom: 3px; }
.ri-title {
  font-size: 12px; font-weight: 600; color: #212121; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; flex: 1; min-width: 0;
}
.ri-meta { font-size: 10px; color: #9E9E9E; }

/* Content area */
.report-content { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }

.empty-state, .generating-state, .error-state {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 10px; text-align: center; padding: 48px;
}
.empty-title { font-size: 18px; font-weight: 700; color: #424242; }
.empty-sub   { font-size: 13px; color: #9E9E9E; max-width: 380px; }
.gen-text    { font-size: 15px; font-weight: 600; color: #424242; }
.gen-sub     { font-size: 12px; color: #9E9E9E; }

.report-display { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.report-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 24px; border-bottom: 1px solid #F0F0F0; flex-shrink: 0;
}
.report-meta {
  display: flex; align-items: center; gap: 8px;
  font-size: 11px; color: #9E9E9E;
}
.report-body { flex: 1; overflow-y: auto; padding: 24px 32px; }

/* Markdown styles */
.markdown-body :deep(h1) { font-size: 22px; font-weight: 800; color: #212121; margin: 0 0 16px; padding-bottom: 8px; border-bottom: 2px solid #E8F5E9; }
.markdown-body :deep(h2) { font-size: 17px; font-weight: 700; color: #1B5E20; margin: 24px 0 10px; }
.markdown-body :deep(h3) { font-size: 14px; font-weight: 700; color: #2E7D32; margin: 16px 0 6px; }
.markdown-body :deep(p)  { font-size: 13px; line-height: 1.75; color: #424242; margin: 0 0 10px; }
.markdown-body :deep(strong) { color: #212121; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { font-size: 13px; color: #424242; line-height: 1.85; padding-left: 20px; margin: 0 0 10px; }
.markdown-body :deep(li) { margin-bottom: 4px; }
.markdown-body :deep(blockquote) {
  border-left: 4px solid #A5D6A7; padding: 8px 16px; margin: 12px 0;
  background: #F1F8E9; border-radius: 0 8px 8px 0; font-size: 13px; color: #33691E;
}
.markdown-body :deep(table) { width: 100%; border-collapse: collapse; font-size: 12px; margin: 12px 0 16px; }
.markdown-body :deep(th) { background: #E8F5E9; color: #1B5E20; font-weight: 700; padding: 8px 12px; text-align: left; border: 1px solid #C8E6C9; }
.markdown-body :deep(td) { padding: 7px 12px; border: 1px solid #E8E8E8; color: #424242; }
.markdown-body :deep(tr:nth-child(even) td) { background: #FAFAFA; }
.markdown-body :deep(code) { background: #E8F5E9; color: #2E7D32; padding: 1px 5px; border-radius: 4px; font-size: 12px; }
.markdown-body :deep(hr) { border: none; border-top: 1px solid #E8F5E9; margin: 20px 0; }
</style>
