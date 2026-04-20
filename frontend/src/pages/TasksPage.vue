<template>
  <q-page class="q-pa-md">

    <!-- Toolbar -->
    <div class="row items-center q-mb-md q-gutter-sm">

      <q-input
        v-model="search"
        outlined dense clearable
        placeholder="Search tasks..."
        style="min-width:220px"
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
        placeholder="All Statuses"
        style="min-width:150px"
        @update:model-value="load"
      />

      <q-select
        v-model="filterPriority"
        :options="priorityOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="All Priorities"
        style="min-width:145px"
        @update:model-value="load"
      />

      <q-select
        v-if="authStore.isAdmin"
        v-model="filterAssignee"
        :options="operatorOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="All Operators"
        style="min-width:170px"
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

      <q-btn unelevated color="primary" icon="add" label="New Task"
        style="border-radius:8px"
        @click="openCreate" />
    </div>

    <!-- Table -->
    <q-card flat bordered style="border-radius:12px;overflow:hidden">
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
        class="tasks-table"
        no-data-label="No tasks found"
        @row-click="openDetail"
      >
        <!-- Title -->
        <template #body-cell-title="props">
          <q-td :props="props">
            <div class="row items-start q-gutter-xs">
              <q-icon :name="priorityIcon(props.row.priority)"
                :color="priorityColor(props.row.priority)" size="15px" class="q-mt-xs" />
              <div>
                <div class="text-weight-medium"
                  :style="props.row.status === 'done' ? 'text-decoration:line-through;color:#9E9E9E' : ''">
                  {{ props.row.title }}
                </div>
                <div v-if="props.row.description" class="text-caption text-grey-5 ellipsis" style="max-width:300px">
                  {{ props.row.description }}
                </div>
              </div>
            </div>
          </q-td>
        </template>

        <!-- Partner -->
        <template #body-cell-partner="props">
          <q-td :props="props">
            <router-link
              v-if="props.row.partner"
              :to="`/partners/${props.row.partner}`"
              class="partner-link"
              @click.stop
            >
              {{ props.row.partner_name }}
            </router-link>
            <span v-else class="text-grey-4">—</span>
          </q-td>
        </template>

        <!-- Status -->
        <template #body-cell-status="props">
          <q-td :props="props" @click.stop>
            <q-select
              :model-value="props.row.status"
              :options="statusOptions"
              emit-value map-options
              dense borderless
              style="min-width:120px"
              @update:model-value="val => quickStatus(props.row, val)"
            >
              <template #selected>
                <div class="row items-center q-gutter-xs">
                  <div class="status-dot" :class="`status-dot--${props.row.status}`" />
                  <span :class="`status-lbl--${props.row.status}`">{{ props.row.status_display }}</span>
                </div>
              </template>
            </q-select>
          </q-td>
        </template>

        <!-- Due date -->
        <template #body-cell-due_date="props">
          <q-td :props="props">
            <template v-if="props.row.due_date">
              <div v-if="props.row.is_overdue && props.row.status !== 'done'"
                class="due-overdue">
                <q-icon name="warning" size="12px" /> {{ fmtDate(props.row.due_date) }}
              </div>
              <div v-else-if="isToday(props.row.due_date)"
                class="due-today">
                <q-icon name="today" size="12px" /> Today
              </div>
              <span v-else class="text-caption text-grey-7">{{ fmtDate(props.row.due_date) }}</span>
            </template>
            <span v-else class="text-grey-4">—</span>
          </q-td>
        </template>

        <!-- Assigned to -->
        <template #body-cell-assigned_to="props">
          <q-td :props="props">
            <span v-if="props.row.assigned_to_detail" class="text-caption">
              {{ props.row.assigned_to_detail.full_name || props.row.assigned_to_detail.username }}
            </span>
            <span v-else class="text-grey-4 text-caption">Unassigned</span>
          </q-td>
        </template>

        <!-- Created (author + datetime) -->
        <template #body-cell-created="props">
          <q-td :props="props">
            <div class="who-name">{{ userName(props.row.created_by_detail) || '—' }}</div>
            <div class="who-date">{{ fmtDatetime(props.row.created_at) }}</div>
          </q-td>
        </template>

        <!-- Closed (completer + datetime) -->
        <template #body-cell-closed="props">
          <q-td :props="props">
            <template v-if="props.row.completed_at">
              <div class="who-name who-name--done">
                <q-icon name="check_circle" color="green-6" size="12px" />
                {{ userName(props.row.completed_by_detail) || '—' }}
              </div>
              <div class="who-date">{{ fmtDatetime(props.row.completed_at) }}</div>
            </template>
            <span v-else class="text-grey-4 text-caption">—</span>
          </q-td>
        </template>

        <!-- Actions -->
        <template #body-cell-actions="props">
          <q-td :props="props" @click.stop>
            <q-btn flat round dense icon="edit" size="sm" color="grey-6" @click="openEdit(props.row)">
              <q-tooltip>Edit</q-tooltip>
            </q-btn>
            <q-btn flat round dense icon="check_circle" size="sm"
              :color="props.row.status === 'done' ? 'green-6' : 'grey-4'"
              @click="toggleDone(props.row)">
              <q-tooltip>{{ props.row.status === 'done' ? 'Reopen' : 'Mark done' }}</q-tooltip>
            </q-btn>
            <q-btn v-if="authStore.isAdmin" flat round dense icon="delete" size="sm" color="grey-4" @click="confirmDelete(props.row)">
              <q-tooltip>Delete</q-tooltip>
            </q-btn>
          </q-td>
        </template>

      </q-table>
    </q-card>

    <TaskDialog
      v-model="dialogOpen"
      :task="editingTask"
      @saved="onSaved"
    />

    <TaskDetailDialog
      v-if="detailTask"
      v-model="detailOpen"
      :task="detailTask"
      @updated="onDetailUpdated"
      @edit="openEdit"
    />
  </q-page>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { useTasksStore } from 'src/stores/tasks'
import { usePartnersStore } from 'src/stores/partners'
import { useAuthStore } from 'src/stores/auth'
import TaskDialog from 'src/components/TaskDialog.vue'
import TaskDetailDialog from 'src/components/TaskDetailDialog.vue'

const $q            = useQuasar()
const tasksStore    = useTasksStore()
const partnersStore = usePartnersStore()
const authStore     = useAuthStore()

const rows    = ref([])
const loading = ref(false)
const search  = ref('')
const filterStatus   = ref(null)
const filterPriority = ref(null)
const filterAssignee = ref(null)
const onlyMine = ref(false)
const dialogOpen  = ref(false)
const editingTask = ref(null)
const detailOpen  = ref(false)
const detailTask  = ref(null)

const pagination = ref({
  page: 1, rowsPerPage: 25, rowsNumber: 0,
  sortBy: 'due_date', descending: false,
})

const columns = [
  { name: 'title',       label: 'Task',       field: 'title',    align: 'left',   sortable: true },
  { name: 'partner',     label: 'Partner',    field: 'partner',  align: 'left',   sortable: false },
  { name: 'status',      label: 'Status',     field: 'status',   align: 'left',   sortable: true },
  { name: 'due_date',    label: 'Due Date',   field: 'due_date', align: 'left',   sortable: true },
  { name: 'assigned_to', label: 'Assignee',   field: r => r.assigned_to_detail?.full_name || '', align: 'left', sortable: true },
  { name: 'created',     label: 'Created',    field: 'created_at', align: 'left', sortable: true },
  { name: 'closed',      label: 'Closed',     field: 'completed_at', align: 'left', sortable: true },
  { name: 'actions',     label: '',           field: 'actions',  align: 'right' },
]

const statusOptions = [
  { label: 'Open',        value: 'open' },
  { label: 'In Progress', value: 'in_progress' },
  { label: 'Done',        value: 'done' },
  { label: 'Cancelled',   value: 'cancelled' },
]
const priorityOptions = [
  { label: 'Low',    value: 'low' },
  { label: 'Medium', value: 'medium' },
  { label: 'High',   value: 'high' },
]

const operatorOptions = computed(() =>
  (partnersStore.users || []).map(u => ({
    label: `${u.first_name} ${u.last_name}`.trim() || u.username,
    value: u.id,
  }))
)

async function load() {
  loading.value = true
  try {
    const params = {
      page:      pagination.value.page,
      page_size: pagination.value.rowsPerPage,
    }
    if (search.value)        params.search      = search.value
    if (filterStatus.value)  params.status      = filterStatus.value
    if (filterPriority.value) params.priority   = filterPriority.value
    if (filterAssignee.value) params.assigned_to = filterAssignee.value
    else if (onlyMine.value)  params.assigned_to = authStore.user?.id
    if (pagination.value.sortBy) {
      params.ordering = (pagination.value.descending ? '-' : '') + pagination.value.sortBy
    }
    const data = await tasksStore.fetchTasks(params)
    rows.value = data.results || data
    pagination.value.rowsNumber = data.count || rows.value.length
  } finally {
    loading.value = false
  }
}

function onRequest(props) {
  pagination.value = props.pagination
  load()
}

function openCreate() {
  editingTask.value = null
  dialogOpen.value  = true
}
function openEdit(task) {
  editingTask.value = task
  dialogOpen.value  = true
}
function openDetail(evt, row) {
  detailTask.value = row
  detailOpen.value = true
}
function onDetailUpdated(updated) {
  const idx = rows.value.findIndex(r => r.id === updated.id)
  if (idx !== -1) rows.value[idx] = updated
  detailTask.value = updated
}

async function quickStatus(task, newStatus) {
  await tasksStore.updateTask(task.id, { status: newStatus })
  await tasksStore.refreshOpenCount()
  load()
}

async function toggleDone(task) {
  const newStatus = task.status === 'done' ? 'open' : 'done'
  await tasksStore.updateTask(task.id, { status: newStatus })
  await tasksStore.refreshOpenCount()
  load()
}

function confirmDelete(task) {
  $q.dialog({
    title: 'Delete Task',
    message: `Delete "${task.title}"?`,
    cancel: true,
    ok: { label: 'Delete', color: 'negative' },
  }).onOk(async () => {
    await tasksStore.deleteTask(task.id)
    await tasksStore.refreshOpenCount()
    load()
    $q.notify({ type: 'positive', message: 'Task deleted' })
  })
}

async function onSaved() {
  load()
  $q.notify({ type: 'positive', message: editingTask.value ? 'Task updated' : 'Task created' })
}

function priorityIcon(p)  { return { low: 'arrow_downward', medium: 'remove', high: 'arrow_upward' }[p] || 'remove' }
function priorityColor(p) { return { low: 'grey-5', medium: 'orange', high: 'red-6' }[p] || 'grey' }

const todayStr = new Date().toISOString().slice(0, 10)
const isToday  = (d) => d === todayStr
function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })
}

function fmtDatetime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('en-US', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

function userName(detail) {
  if (!detail) return ''
  return detail.full_name || detail.username || ''
}

onMounted(() => {
  if (!partnersStore.users.length) partnersStore.fetchUsers()
  load()
})
</script>

<style scoped>
.tasks-table :deep(.q-tr.q-tr--no-hover) { cursor: default; }
.tasks-table :deep(tbody .q-tr) { cursor: pointer; }
.tasks-table :deep(tbody .q-tr:hover) { background: rgba(46, 125, 50, 0.04); }

.partner-link {
  color: #1565C0;
  text-decoration: none;
  font-size: 12px;
  font-weight: 500;
}
.partner-link:hover { text-decoration: underline; }

.status-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot--open        { background: #42A5F5; }
.status-dot--in_progress { background: #FFA726; }
.status-dot--done        { background: #66BB6A; }
.status-dot--cancelled   { background: #BDBDBD; }

.status-lbl--open        { color: #1565C0; font-size: 12px; font-weight: 600; }
.status-lbl--in_progress { color: #E65100; font-size: 12px; font-weight: 600; }
.status-lbl--done        { color: #2E7D32; font-size: 12px; }
.status-lbl--cancelled   { color: #9E9E9E; font-size: 12px; }

.due-overdue {
  display: inline-flex; align-items: center; gap: 3px;
  background: #FFEBEE; color: #C62828;
  font-size: 11px; font-weight: 700;
  padding: 2px 7px; border-radius: 8px;
}
.due-today {
  display: inline-flex; align-items: center; gap: 3px;
  background: #FFF3E0; color: #E65100;
  font-size: 11px; font-weight: 700;
  padding: 2px 7px; border-radius: 8px;
}

.who-name {
  font-size: 12px;
  font-weight: 500;
  color: #212121;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  white-space: nowrap;
}
.who-name--done { color: #2E7D32; font-weight: 600; }
.who-date {
  font-size: 10.5px;
  color: #9E9E9E;
  white-space: nowrap;
}
</style>
