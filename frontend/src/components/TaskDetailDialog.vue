<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <q-card style="min-width:500px;max-width:580px;border-radius:14px;">

      <!-- Header -->
      <q-card-section class="row items-start q-pb-none">
        <div style="flex:1;min-width:0">
          <div class="row items-center q-gutter-xs q-mb-xs">
            <q-icon :name="priorityIcon(task.priority)" :color="priorityColor(task.priority)" size="16px" />
            <q-chip dense size="sm" :class="`status-chip status-chip--${task.status}`">
              {{ task.status_display }}
            </q-chip>
            <q-chip v-if="task.is_overdue && task.status !== 'done'" dense size="sm" color="negative" text-color="white">
              Overdue
            </q-chip>
          </div>
          <div class="text-h6 text-weight-bold"
            :style="task.status === 'done' ? 'text-decoration:line-through;color:#9E9E9E' : ''">
            {{ task.title }}
          </div>
        </div>
        <q-btn flat round icon="close" @click="$emit('update:modelValue', false)" />
      </q-card-section>

      <!-- Scrollable body -->
      <div class="dialog-body">

        <!-- Description -->
        <div v-if="task.description" class="detail-desc q-mb-md">
          {{ task.description }}
        </div>

        <!-- Meta grid -->
        <div class="meta-grid q-mb-md">
          <div v-if="task.partner_name" class="meta-row">
            <q-icon name="business" color="grey-5" size="15px" />
            <span class="meta-label">Partner</span>
            <router-link
              :to="`/partners/${task.partner}`"
              class="meta-link"
              @click="$emit('update:modelValue', false)"
            >{{ task.partner_name }}</router-link>
          </div>

          <div class="meta-row">
            <q-icon name="person" color="grey-5" size="15px" />
            <span class="meta-label">Assigned to</span>
            <span class="meta-value">
              {{ task.assigned_to_detail
                ? (task.assigned_to_detail.full_name || task.assigned_to_detail.username)
                : '—' }}
            </span>
          </div>

          <div class="meta-row">
            <q-icon name="event" color="grey-5" size="15px" />
            <span class="meta-label">Due date</span>
            <span class="meta-value" :style="dueDateStyle">
              {{ task.due_date ? fmtDate(task.due_date) : '—' }}
            </span>
          </div>

          <div class="meta-row">
            <q-icon name="flag" color="grey-5" size="15px" />
            <span class="meta-label">Priority</span>
            <span class="meta-value">{{ task.priority_display }}</span>
          </div>

          <div class="meta-row">
            <q-icon name="person_add" color="grey-5" size="15px" />
            <span class="meta-label">Created by</span>
            <span class="meta-value">
              {{ task.created_by_detail
                ? (task.created_by_detail.full_name || task.created_by_detail.username)
                : '—' }}
              <span class="meta-time">· {{ fmtDatetime(task.created_at) }}</span>
            </span>
          </div>
        </div>

        <!-- Completion info -->
        <div v-if="task.status === 'done' && task.completed_by_detail" class="completion-block q-mb-md">
          <q-icon name="check_circle" color="green-6" size="18px" />
          <div>
            <div class="completion-title">Marked as Done</div>
            <div class="completion-meta">
              by <strong>{{ task.completed_by_detail.full_name || task.completed_by_detail.username }}</strong>
              <span v-if="task.completed_at"> · {{ fmtDatetime(task.completed_at) }}</span>
            </div>
          </div>
        </div>

        <q-separator class="q-mb-md" />

        <!-- Comments header -->
        <div class="comments-header q-mb-sm">
          <q-icon name="chat_bubble_outline" color="grey-6" size="15px" />
          <span>Comments</span>
          <q-badge v-if="task.comments && task.comments.length" color="grey-4" text-color="grey-8" rounded class="q-ml-xs">
            {{ task.comments.length }}
          </q-badge>
        </div>

        <!-- Existing comments -->
        <div v-if="task.comments && task.comments.length" class="q-gutter-sm q-mb-md">
          <div v-for="c in task.comments" :key="c.id" class="comment-item">
            <div class="comment-avatar">{{ initials(c.author_detail) }}</div>
            <div style="flex:1;min-width:0">
              <div class="comment-meta">
                <span class="comment-author">{{ c.author_detail ? (c.author_detail.full_name || c.author_detail.username) : '?' }}</span>
                <span class="comment-time">{{ fmtDatetime(c.created_at) }}</span>
              </div>
              <div class="comment-text">{{ c.text }}</div>
            </div>
            <q-btn
              v-if="canDeleteComment(c)"
              flat round dense icon="close" size="xs" color="grey-4"
              class="comment-delete"
              @click="removeComment(c.id)"
            />
          </div>
        </div>
        <div v-else class="text-caption text-grey-4 q-mb-md">No comments yet</div>

        <!-- New comment input -->
        <div class="new-comment-row">
          <q-input
            v-model="newComment"
            outlined dense
            placeholder="Write a comment... (Ctrl+Enter to send)"
            type="textarea"
            rows="2"
            autogrow
            style="flex:1"
            @keydown.ctrl.enter="submitComment"
            @keydown.meta.enter="submitComment"
          />
          <q-btn
            unelevated color="primary" icon="send"
            style="border-radius:8px;align-self:flex-end;height:40px"
            :disable="!newComment.trim()"
            :loading="commentSaving"
            @click="submitComment"
          />
        </div>

      </div>

      <q-separator />

      <!-- Actions footer -->
      <q-card-actions class="q-pa-md row q-gutter-sm">
        <q-btn
          v-if="task.status !== 'done'"
          unelevated color="positive" icon="check_circle" label="Mark as Done"
          style="border-radius:8px"
          :loading="saving"
          @click="markDone"
        />
        <q-btn
          v-else
          unelevated color="grey-4" text-color="grey-8" icon="refresh" label="Reopen"
          style="border-radius:8px"
          :loading="saving"
          @click="reopen"
        />
        <q-btn flat color="grey-7" icon="edit" label="Edit" @click="openEdit" />
        <q-space />
        <q-btn flat color="grey-6" label="Close" @click="$emit('update:modelValue', false)" />
      </q-card-actions>

    </q-card>
  </q-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useTasksStore } from 'src/stores/tasks'
import { useAuthStore } from 'src/stores/auth'

const props = defineProps({
  modelValue: Boolean,
  task:       { type: Object, required: true },
})
const emit = defineEmits(['update:modelValue', 'edit', 'updated'])

const tasksStore = useTasksStore()
const authStore  = useAuthStore()
const saving        = ref(false)
const commentSaving = ref(false)
const newComment    = ref('')

const dueDateStyle = computed(() => {
  if (!props.task.due_date) return ''
  if (props.task.is_overdue && props.task.status !== 'done') return 'color:#C62828;font-weight:700'
  if (props.task.due_date === new Date().toISOString().slice(0, 10)) return 'color:#E65100;font-weight:700'
  return ''
})

async function markDone() {
  saving.value = true
  try {
    const updated = await tasksStore.updateTask(props.task.id, { status: 'done' })
    await tasksStore.refreshOpenCount()
    emit('updated', updated)
  } finally {
    saving.value = false
  }
}

async function reopen() {
  saving.value = true
  try {
    const updated = await tasksStore.updateTask(props.task.id, { status: 'open' })
    await tasksStore.refreshOpenCount()
    emit('updated', updated)
  } finally {
    saving.value = false
  }
}

function openEdit() {
  emit('update:modelValue', false)
  emit('edit', props.task)
}

async function submitComment() {
  const text = newComment.value.trim()
  if (!text) return
  commentSaving.value = true
  try {
    const updated = await tasksStore.addComment(props.task.id, text)
    newComment.value = ''
    emit('updated', updated)
  } finally {
    commentSaving.value = false
  }
}

async function removeComment(commentId) {
  const updated = await tasksStore.deleteComment(props.task.id, commentId)
  emit('updated', updated)
}

function canDeleteComment(comment) {
  if (authStore.isAdmin) return true
  return comment.author === authStore.user?.id
}

function initials(userDetail) {
  if (!userDetail) return '?'
  const name = userDetail.full_name || userDetail.username || ''
  return name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()
}

function priorityIcon(p)  { return { low: 'arrow_downward', medium: 'remove', high: 'arrow_upward' }[p] || 'remove' }
function priorityColor(p) { return { low: 'grey-5', medium: 'orange', high: 'red-6' }[p] || 'grey' }

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })
}

function fmtDatetime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('en-US', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>

<style scoped>
.dialog-body {
  padding: 12px 16px 16px;
  overflow-y: auto;
  max-height: calc(80vh - 140px);
}

.detail-desc {
  font-size: 13px;
  color: #424242;
  background: #F9F9F9;
  border-radius: 8px;
  padding: 10px 12px;
  white-space: pre-wrap;
  line-height: 1.55;
}

.meta-grid { display: flex; flex-direction: column; gap: 8px; }
.meta-row  { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.meta-label { color: #9E9E9E; min-width: 90px; font-size: 12px; }
.meta-value { color: #212121; }
.meta-time  { color: #9E9E9E; font-size: 11px; }
.meta-link  { color: #1565C0; text-decoration: none; font-weight: 500; }
.meta-link:hover { text-decoration: underline; }

.completion-block {
  display: flex; align-items: flex-start; gap: 10px;
  background: #F1F8E9; border-radius: 10px; padding: 10px 14px;
}
.completion-title { font-size: 12px; font-weight: 700; color: #2E7D32; }
.completion-meta  { font-size: 12px; color: #4CAF50; }

.comments-header {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 700; color: #616161;
}

.comment-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 8px 10px;
  background: #FAFAFA;
  border-radius: 10px;
  border: 1px solid #F0F0F0;
}
.comment-item:hover .comment-delete { opacity: 1; }

.comment-avatar {
  width: 30px; height: 30px; border-radius: 50%;
  background: #E3F2FD; color: #1565C0;
  font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.comment-meta   { display: flex; align-items: baseline; gap: 8px; margin-bottom: 3px; }
.comment-author { font-size: 12px; font-weight: 700; color: #212121; }
.comment-time   { font-size: 11px; color: #9E9E9E; }
.comment-text   { font-size: 13px; color: #424242; white-space: pre-wrap; line-height: 1.5; }
.comment-delete { opacity: 0; transition: opacity 0.15s; flex-shrink: 0; }

.new-comment-row { display: flex; gap: 8px; align-items: flex-start; }

.status-chip { font-size: 11px; font-weight: 600; }
.status-chip--open        { background: #E3F2FD !important; color: #1565C0 !important; }
.status-chip--in_progress { background: #FFF3E0 !important; color: #E65100 !important; }
.status-chip--done        { background: #E8F5E9 !important; color: #2E7D32 !important; }
.status-chip--cancelled   { background: #F5F5F5 !important; color: #9E9E9E !important; }
</style>
