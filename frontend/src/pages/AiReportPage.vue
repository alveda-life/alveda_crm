<template>
  <q-page class="ai-report-page">
    <div class="ai-report-layout">

      <!-- ── Left sidebar: report history ── -->
      <div class="report-sidebar">
        <div class="sidebar-header">
          <q-icon name="auto_awesome" color="deep-purple-5" size="18px" />
          <span>Report History</span>
          <q-badge v-if="reports.length" color="grey-4" text-color="grey-8" rounded>
            {{ reports.length }}
          </q-badge>
        </div>

        <div v-if="!reports.length" class="no-reports">
          <q-icon name="description" size="32px" color="grey-3" />
          <div>No reports yet</div>
        </div>

        <div v-else class="report-list">
          <div
            v-for="r in reports"
            :key="r.id"
            class="report-item"
            :class="{ 'report-item--active': activeReport?.id === r.id }"
            @click="selectReport(r)"
          >
            <div class="ri-title-row">
              <q-spinner-dots v-if="r.status === 'pending' || r.status === 'generating'" color="deep-purple-4" size="12px" class="q-mr-xs" />
              <q-icon v-else-if="r.status === 'error'" name="error_outline" color="negative" size="14px" class="q-mr-xs" />
              <div class="ri-title">{{ r.title }}</div>
            </div>
            <div class="ri-meta">{{ fmtDate(r.created_at) }}</div>
            <q-btn v-if="authStore.isAdmin"
              flat round dense icon="delete" size="xs" color="grey-4"
              class="ri-delete"
              @click.stop="confirmDelete(r)"
            />
          </div>
        </div>
      </div>

      <!-- ── Right: content area ── -->
      <div class="report-content">

        <!-- Input area always visible at top -->
        <div class="prompt-area">
          <div class="prompt-area-header">
            <q-icon name="auto_awesome" color="deep-purple-5" size="20px" />
            <span class="prompt-title">AI Report Generator</span>
            <span class="prompt-hint">Powered by Claude</span>
          </div>

          <div class="prompt-input-row">
            <q-input
              v-model="promptText"
              outlined
              type="textarea"
              autogrow
              rows="2"
              placeholder="Describe the report you need… e.g. “Operator activity report for the last 30 days” or “Weekly summary of partner funnel health”"
              class="prompt-input"
              :disable="submitting"
              @keydown.ctrl.enter="generate"
              @keydown.meta.enter="generate"
            />
            <q-btn
              unelevated color="deep-purple-6" icon="send" label="Generate"
              style="border-radius:10px;min-width:120px;align-self:flex-end;height:44px"
              :loading="submitting"
              :disable="!promptText.trim()"
              @click="generate"
            >
              <template #loading>
                <q-spinner-dots size="20px" />
              </template>
            </q-btn>
          </div>
          <div class="prompt-tips">
            <span>Ctrl+Enter to send</span>
            <span>·</span>
            <span>Reports are saved automatically</span>
          </div>
        </div>

        <!-- No report selected -->
        <div v-if="!activeReport" class="empty-state">
          <q-icon name="analytics" size="64px" color="grey-3" />
          <div class="empty-title">Generate your first report</div>
          <div class="empty-sub">AI will analyze CRM data and create a detailed Markdown report</div>
          <div class="example-prompts">
            <div class="ep-label">Examples:</div>
            <div
              v-for="ex in examplePrompts"
              :key="ex"
              class="ep-chip"
              @click="promptText = ex"
            >{{ ex }}</div>
          </div>
        </div>

        <!-- Active report: pending/generating -->
        <div v-if="activeReport && isInProgress(activeReport)" class="generating-state">
          <q-spinner-dots color="deep-purple-5" size="48px" />
          <div class="gen-text">Analyzing CRM data and generating report…</div>
          <div class="gen-sub">This may take 10–30 seconds. You can close this tab — the report will be saved.</div>
        </div>

        <!-- Active report: error -->
        <div v-if="activeReport && activeReport.status === 'error'" class="error-state">
          <q-icon name="error_outline" color="negative" size="48px" />
          <div class="gen-text text-negative">Generation failed</div>
          <div class="gen-sub">{{ activeReport.error_message || 'Unknown error' }}</div>
        </div>

        <!-- Active report display -->
        <div v-if="activeReport && activeReport.status === 'done'" class="report-display">
          <div class="report-toolbar">
            <div class="report-meta">
              <q-icon name="schedule" color="grey-5" size="14px" />
              <span>{{ fmtDatetime(activeReport.created_at) }}</span>
              <span class="q-mx-xs text-grey-4">·</span>
              <span>Prompt: <em>{{ activeReport.prompt }}</em></span>
            </div>
            <div class="row q-gutter-xs">
              <q-btn flat dense icon="picture_as_pdf" label="PDF" color="grey-7"
                style="border-radius:8px;font-size:12px"
                @click="downloadPdf(activeReport)" />
              <q-btn flat dense icon="download" label=".md" color="grey-7"
                style="border-radius:8px;font-size:12px"
                @click="downloadReport(activeReport)" />
              <q-btn flat dense icon="content_copy" color="grey-7"
                style="border-radius:8px;font-size:12px"
                @click="copyReport(activeReport)">
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
import { useReportsStore } from 'src/stores/reports'
import { marked } from 'marked'

const $q = useQuasar()
const authStore = useAuthStore()
const store = useReportsStore()

const promptText   = ref('')
const submitting   = ref(false)
const activeReport = ref(null)

const reports = computed(() => store.partnerReports)

// Keep activeReport in sync with store (polling updates store entries in-place)
watch(
  reports,
  (list) => {
    if (activeReport.value) {
      const fresh = list.find(r => r.id === activeReport.value.id)
      if (fresh) activeReport.value = fresh
    }
  },
  { deep: true }
)

function isInProgress(r) {
  return r.status === 'pending' || r.status === 'generating'
}

function selectReport(r) {
  activeReport.value = r
}

const examplePrompts = [
  'Operator report for the last 30 days — calls, conversions, activity',
  'Partner funnel analysis — where we lose them, who is stuck',
  'Weekly performance summary for all operators',
  'Financial report — revenue, unpaid orders, top partners',
  'Which partners are in Dead stages and why — analysis',
  'Task completion report — who delivers and who does not',
]

async function generate() {
  if (!promptText.value.trim() || submitting.value) return
  submitting.value = true
  try {
    const report = await store.generateReport(promptText.value.trim(), 'partners')
    activeReport.value = report
    promptText.value   = ''
  } catch (e) {
    $q.notify({ type: 'negative', message: e?.response?.data?.error || 'Generation failed' })
  } finally {
    submitting.value = false
  }
}

function renderMarkdown(md) {
  if (!md) return ''
  return marked.parse(md)
}

function downloadPdf(r) {
  const html = renderMarkdown(r.content)
  const win = window.open('', '_blank')
  win.document.write(`<!DOCTYPE html><html><head>
    <meta charset="utf-8">
    <title>${r.title}</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
             max-width: 800px; margin: 40px auto; padding: 0 20px; color: #222; line-height: 1.6; }
      h1 { font-size: 22px; border-bottom: 2px solid #7c4dff; padding-bottom: 8px; }
      h2 { font-size: 18px; margin-top: 24px; color: #333; }
      h3 { font-size: 15px; color: #555; }
      table { border-collapse: collapse; width: 100%; margin: 12px 0; }
      th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 13px; }
      th { background: #f5f5f5; }
      blockquote { border-left: 3px solid #7c4dff; margin: 8px 0; padding: 4px 12px; color: #555; }
      code { background: #f5f5f5; padding: 2px 4px; border-radius: 3px; font-size: 13px; }
      ul, ol { padding-left: 20px; }
      @media print { body { margin: 20px; } }
    </style>
  </head><body>${html}</body></html>`)
  win.document.close()
  setTimeout(() => win.print(), 400)
}

function downloadReport(r) {
  const blob = new Blob([r.content], { type: 'text/markdown;charset=utf-8' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = slugify(r.title) + '.md'
  a.click()
  URL.revokeObjectURL(url)
}

function copyReport(r) {
  navigator.clipboard.writeText(r.content)
  $q.notify({ type: 'positive', message: 'Copied to clipboard', timeout: 1500 })
}

function slugify(s) {
  return s.toLowerCase().replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').slice(0, 60) || 'report'
}

function confirmDelete(r) {
  $q.dialog({
    title: 'Delete Report',
    message: `Delete "${r.title}"?`,
    cancel: true,
    ok: { label: 'Delete', color: 'negative' },
  }).onOk(async () => {
    if (activeReport.value?.id === r.id) activeReport.value = null
    await store.deleteReport(r.id, 'partners')
  })
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })
}
function fmtDatetime(iso) {
  return new Date(iso).toLocaleString('en-US', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => store.fetchReports('partners'))
onUnmounted(() => store._stopPolling())
</script>

<style scoped>
.ai-report-page { padding: 0; height: calc(100vh - 50px); }

.ai-report-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* ── Left sidebar ── */
.report-sidebar {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid #F0F0F0;
  background: #FAFAFA;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  font-size: 13px;
  font-weight: 700;
  color: #424242;
  border-bottom: 1px solid #F0F0F0;
  flex-shrink: 0;
}

.no-reports {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 16px;
  color: #BDBDBD;
  font-size: 12px;
  text-align: center;
}

.report-list {
  overflow-y: auto;
  flex: 1;
  padding: 8px;
}

.report-item {
  position: relative;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.12s;
  margin-bottom: 4px;
}
.report-item:hover { background: #F0F0F0; }
.report-item--active { background: #EDE7F6; }
.report-item:hover .ri-delete { opacity: 1; }

.ri-title-row {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  margin-bottom: 3px;
}
.ri-title {
  font-size: 12px;
  font-weight: 600;
  color: #212121;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}
.ri-meta { font-size: 10px; color: #9E9E9E; }
.ri-delete {
  position: absolute;
  top: 6px; right: 6px;
  opacity: 0;
  transition: opacity 0.12s;
}

/* ── Right content ── */
.report-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Prompt area */
.prompt-area {
  flex-shrink: 0;
  padding: 16px 24px 12px;
  border-bottom: 1px solid #F0F0F0;
  background: #fff;
}

.prompt-area-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.prompt-title { font-size: 15px; font-weight: 700; color: #212121; }
.prompt-hint  { font-size: 11px; color: #9E9E9E; }

.prompt-input-row { display: flex; gap: 10px; align-items: flex-start; }
.prompt-input { flex: 1; }

.prompt-tips {
  display: flex;
  gap: 8px;
  font-size: 10px;
  color: #BDBDBD;
  margin-top: 6px;
}

/* Empty state */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px;
  text-align: center;
}
.empty-title { font-size: 18px; font-weight: 700; color: #424242; }
.empty-sub   { font-size: 13px; color: #9E9E9E; }

.example-prompts {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
}
.ep-label { font-size: 11px; color: #BDBDBD; text-transform: uppercase; letter-spacing: 0.5px; }
.ep-chip {
  background: #F3E5F5;
  color: #6A1B9A;
  border-radius: 20px;
  padding: 5px 14px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.12s;
  max-width: 480px;
  text-align: center;
}
.ep-chip:hover { background: #E1BEE7; }

/* Generating / Error */
.generating-state, .error-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  padding: 48px;
}
.gen-text { font-size: 15px; font-weight: 600; color: #424242; }
.gen-sub  { font-size: 12px; color: #9E9E9E; max-width: 400px; }

/* Report display */
.report-display {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.report-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 24px;
  border-bottom: 1px solid #F0F0F0;
  flex-shrink: 0;
}
.report-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #9E9E9E;
  min-width: 0;
  overflow: hidden;
}
.report-meta em {
  font-style: normal;
  color: #616161;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 300px;
  display: inline-block;
}

.report-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

/* ── Markdown styling ── */
.markdown-body :deep(h1) { font-size: 22px; font-weight: 800; color: #212121; margin: 0 0 16px; padding-bottom: 8px; border-bottom: 2px solid #EDE7F6; }
.markdown-body :deep(h2) { font-size: 18px; font-weight: 700; color: #311B92; margin: 24px 0 12px; }
.markdown-body :deep(h3) { font-size: 15px; font-weight: 700; color: #4527A0; margin: 18px 0 8px; }
.markdown-body :deep(p)  { font-size: 13px; line-height: 1.7; color: #424242; margin: 0 0 10px; }
.markdown-body :deep(strong) { color: #212121; }
.markdown-body :deep(em)     { color: #7B1FA2; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { font-size: 13px; color: #424242; line-height: 1.8; padding-left: 20px; margin: 0 0 10px; }
.markdown-body :deep(li)     { margin-bottom: 4px; }
.markdown-body :deep(blockquote) {
  border-left: 4px solid #CE93D8;
  padding: 8px 16px;
  margin: 12px 0;
  background: #F3E5F5;
  border-radius: 0 8px 8px 0;
  font-size: 13px;
  color: #6A1B9A;
}
.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin: 12px 0 16px;
}
.markdown-body :deep(th) {
  background: #EDE7F6;
  color: #4527A0;
  font-weight: 700;
  padding: 8px 12px;
  text-align: left;
  border: 1px solid #D1C4E9;
}
.markdown-body :deep(td) {
  padding: 7px 12px;
  border: 1px solid #E8E8E8;
  color: #424242;
}
.markdown-body :deep(tr:nth-child(even) td) { background: #FAFAFA; }
.markdown-body :deep(code) {
  background: #F3E5F5;
  color: #6A1B9A;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
}
.markdown-body :deep(pre) {
  background: #1A1A2E;
  color: #E0E0E0;
  padding: 14px 16px;
  border-radius: 10px;
  overflow-x: auto;
  font-size: 12px;
  margin: 12px 0;
}
.markdown-body :deep(pre code) { background: none; color: inherit; padding: 0; }
.markdown-body :deep(hr) { border: none; border-top: 1px solid #EDE7F6; margin: 20px 0; }
</style>
