<template>
  <div class="tx-chat">

    <!-- Optional toolbar (search + stats + view toggle) -->
    <div v-if="!compact" class="tx-chat-toolbar">
      <q-btn-toggle
        v-model="view"
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
        v-model="search"
        outlined dense clearable
        placeholder="Search transcript…"
        class="tx-chat-search"
        debounce="200"
      >
        <template #prepend><q-icon name="search" size="16px" /></template>
      </q-input>

      <q-space />

      <div class="tx-chat-stats">
        <span class="tx-chat-stat">
          <q-icon name="text_fields" size="13px" />
          {{ activeText.length.toLocaleString() }} ch · {{ wordCount(activeText).toLocaleString() }} words
        </span>
      </div>

      <q-btn flat dense round icon="content_copy" size="sm"
             @click="copyTranscript"
             :title="`Copy ${view === 'raw' ? 'raw' : 'diarized'} transcript`" />
    </div>

    <!-- Chat view -->
    <template v-if="view === 'chat'">
      <div v-if="parsedTurns.length" class="chat-wrap" :class="{ 'chat-wrap--compact': compact }">
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
        <div v-if="!filteredTurns.length" class="tx-chat-empty">
          <q-icon name="search_off" size="22px" />
          <div>No turns match "{{ search }}"</div>
        </div>
      </div>
      <div v-else-if="raw" class="tx-chat-fallback">
        <div class="tx-chat-fallback-hint">
          <q-icon name="info" size="14px" />
          No diarized version yet — showing raw transcript below.
        </div>
        <pre class="raw-transcript" v-html="highlight(raw)" />
      </div>
      <div v-else class="tx-chat-empty">
        <q-icon name="hearing_disabled" size="32px" />
        <div>No transcript available</div>
      </div>
    </template>

    <!-- Raw view -->
    <template v-else>
      <pre v-if="raw" class="raw-transcript" v-html="highlight(raw)" />
      <div v-else class="tx-chat-empty">
        <q-icon name="hearing_disabled" size="32px" />
        <div>No raw transcript available</div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useQuasar } from 'quasar'

const props = defineProps({
  diarized: { type: String, default: '' },
  raw:      { type: String, default: '' },
  compact:  { type: Boolean, default: false }, // smaller padding for inline embedding
  initialView: { type: String, default: 'chat' },
})

const $q     = useQuasar()
const view   = ref(props.initialView)
const search = ref('')

const parsedTurns = computed(() => {
  if (!props.diarized) return []
  return props.diarized
    .split(/\n\n+/)
    .map(l => l.trim())
    .filter(Boolean)
    .map((line, idx) => {
      let m = line.match(/^\*\*\s*(Operator|Partner|Unknown|Speaker\s*\d*)\s*:?\s*\*\*\s*:?\s*([\s\S]*)$/i)
      if (!m) m = line.match(/^\*\*\s*(Operator|Partner|Unknown|Speaker\s*\d*)\s*\*\*\s*:?\s*([\s\S]*)$/i)
      if (!m) m = line.match(/^(Operator|Partner|Unknown|Speaker\s*\d*)\s*:\s*([\s\S]*)$/i)
      if (m) {
        const rawLabel = m[1].trim()
        const isOp = /^operator$/i.test(rawLabel)
        const isPt = /^partner$/i.test(rawLabel)
        const speaker = isOp ? 'Operator' : isPt ? 'Partner' : 'Speaker'
        const text = m[2].replace(/\*\*/g, '').trim()
        return { speaker, text, isOperator: isOp, idx }
      }
      return { speaker: 'Speaker', text: line.replace(/\*\*/g, '').trim(), isOperator: idx % 2 === 0, idx }
    })
})

const filteredTurns = computed(() => {
  const q = search.value?.trim().toLowerCase()
  if (!q) return parsedTurns.value
  return parsedTurns.value.filter(t =>
    t.text.toLowerCase().includes(q) || t.speaker.toLowerCase().includes(q)
  )
})

const activeText = computed(() => view.value === 'raw' ? (props.raw || '') : (props.diarized || props.raw || ''))

function wordCount(s) {
  if (!s) return 0
  return s.trim().split(/\s+/).filter(Boolean).length
}
function escapeHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
function highlight(text) {
  const safe = escapeHtml(text)
  const q = search.value?.trim()
  if (!q) return safe
  const re = new RegExp(escapeRegExp(escapeHtml(q)), 'gi')
  return safe.replace(re, m => `<mark class="tx-mark">${m}</mark>`)
}

async function copyTranscript() {
  const text = view.value === 'raw' ? (props.raw || '') : (props.diarized || props.raw || '')
  try {
    await navigator.clipboard.writeText(text)
    $q.notify({ type: 'positive', message: 'Transcript copied', timeout: 1200 })
  } catch {
    $q.notify({ type: 'negative', message: 'Copy failed' })
  }
}
</script>

<style scoped>
.tx-chat { display: flex; flex-direction: column; }

.tx-chat-toolbar {
  position: sticky; top: 0; z-index: 5;
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px;
  background: #FFFFFFEE;
  backdrop-filter: blur(8px);
  border-bottom: 1px solid #ECEFF1;
  flex-wrap: wrap;
}
.tx-chat-search { min-width: 200px; max-width: 280px; }
.tx-chat-search :deep(.q-field__control) { height: 30px; min-height: 30px; font-size: 12px; }
.tx-chat-search :deep(.q-field__marginal) { height: 30px; }

.tx-chat-stats { display: flex; align-items: center; gap: 10px; font-size: 11.5px; color: #607D8B; white-space: nowrap; }
.tx-chat-stat  { display: inline-flex; align-items: center; gap: 4px; }

.chat-wrap {
  display: flex; flex-direction: column; gap: 12px;
  padding: 16px 24px 20px;
  max-width: 920px; width: 100%; margin: 0 auto;
}
.chat-wrap--compact {
  padding: 8px 4px;
  max-width: 100%;
  gap: 8px;
}

.chat-msg { display: flex; gap: 12px; animation: fadeIn 0.15s ease; }
.chat-wrap--compact .chat-msg { gap: 8px; }

.chat-avatar {
  width: 30px; height: 30px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; margin-top: 4px;
  border: 1px solid transparent;
}
.chat-msg--op      .chat-avatar { background: #E3F2FD; color: #1565C0; border-color: #BBDEFB; }
.chat-msg--partner .chat-avatar { background: #E8F5E9; color: #2E7D32; border-color: #C8E6C9; }

.chat-content { flex: 1; min-width: 0; }

.chat-speaker {
  display: flex; align-items: baseline; gap: 8px;
  font-size: 10.5px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .6px; margin-bottom: 3px;
}
.chat-msg--op      .chat-speaker { color: #1565C0; }
.chat-msg--partner .chat-speaker { color: #2E7D32; }
.chat-meta { font-size: 10px; font-weight: 500; letter-spacing: .2px; color: #B0BEC5; text-transform: none; }

.chat-text {
  padding: 9px 13px; font-size: 13.5px; line-height: 1.6;
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

.raw-transcript {
  white-space: pre-wrap; word-break: break-word;
  font-size: 13px; line-height: 1.7; color: #37474F;
  font-family: inherit; margin: 12px 4px;
  padding: 14px 16px;
  background: #FFFFFF;
  border: 1px solid #ECEFF1;
  border-radius: 8px;
}

.tx-chat-fallback { padding: 12px 4px; }
.tx-chat-fallback-hint {
  display: inline-flex; align-items: center; gap: 6px;
  background: #FFF8E1; color: #EF6C00;
  padding: 6px 10px; border-radius: 6px;
  font-size: 12px;
  margin-bottom: 8px;
}

.tx-chat-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px; color: #B0BEC5; font-size: 13px;
  padding: 32px 12px;
}

:deep(mark.tx-mark) {
  background: #FFF59D; color: #5D4037;
  padding: 0 2px; border-radius: 3px;
  font-weight: 600;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(2px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
