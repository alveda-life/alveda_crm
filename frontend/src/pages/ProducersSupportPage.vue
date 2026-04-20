<template>
  <q-page class="q-pa-md">

    <!-- Header row -->
    <div class="row items-center q-mb-md q-gutter-sm">
      <div style="flex:1;">
        <q-input
          v-model="search"
          outlined dense clearable
          placeholder="Search name, company…"
          style="max-width:280px;"
        >
          <template #prepend><q-icon name="search" color="grey-5" /></template>
        </q-input>
      </div>
      <q-select
        v-model="filterStage"
        :options="stageOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="All Stages"
        style="min-width:160px;"
      />
      <q-select
        v-model="filterOperator"
        :options="operatorOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="All Responsible"
        style="min-width:180px;"
      />
      <q-btn
        :outline="!onlyMine"
        :color="onlyMine ? 'primary' : 'grey-7'"
        :icon="onlyMine ? 'person' : 'person_outline'"
        label="Assigned to Me"
        dense unelevated no-caps
        style="border-radius:8px;font-size:13px;"
        @click="onlyMine = !onlyMine"
      />
      <q-btn
        unelevated color="primary" icon="add" label="Add Producer"
        style="border-radius:8px;"
        @click="showAddDialog = true"
      />
    </div>

    <!-- Table -->
    <q-table
      :rows="filteredRows"
      :columns="columns"
      row-key="id"
      flat bordered
      :loading="loading"
      :rows-per-page-options="[25, 50, 100, 0]"
      rows-per-page-label="Per page"
      style="border-radius:12px; cursor:pointer;"
      @row-click="(_, row) => $router.push(`/producers/${row.id}`)"
    >
      <!-- Name -->
      <template #body-cell-name="props">
        <q-td :props="props">
          <div class="text-weight-semibold" style="color:#212121;">{{ props.row.name }}</div>
          <div v-if="props.row.company" style="font-size:11px;color:#9E9E9E;">{{ props.row.company }}</div>
        </q-td>
      </template>

      <!-- Stage -->
      <template #body-cell-stage="props">
        <q-td :props="props">
          <div :style="`display:inline-flex;align-items:center;gap:5px;padding:2px 8px;border-radius:8px;font-size:11px;font-weight:600;background:${stageStyle(props.row.stage).bg};color:${stageStyle(props.row.stage).color};border:1px solid ${stageStyle(props.row.stage).color}44;`">
            {{ props.row.stage_display }}
          </div>
        </q-td>
      </template>

      <!-- Priority + Coop -->
      <template #body-cell-priority="props">
        <q-td :props="props">
          <div class="row items-center q-gutter-xs">
            <div :style="priorityPill(props.row.priority)"
              style="font-size:10px;font-weight:700;padding:1px 7px;border-radius:8px;">
              {{ props.row.priority_display || props.row.priority }}
            </div>
            <div :style="`width:7px;height:7px;border-radius:50%;background:${coopDot(props.row.cooperation_potential)};`">
              <q-tooltip>{{ props.row.cooperation_potential_display }}</q-tooltip>
            </div>
          </div>
        </q-td>
      </template>

      <!-- Communication Status -->
      <template #body-cell-communication_status="props">
        <q-td :props="props" style="max-width:180px;">
          <div class="row q-gutter-xs flex-wrap">
            <q-chip v-for="tag in splitTags(props.row.communication_status)" :key="tag"
              dense size="xs" style="background:#FFF3E0;color:#E65100;border:1px solid #FFCC80;margin:1px;">
              {{ tag }}
            </q-chip>
            <span v-if="!props.row.communication_status" class="text-grey-4 text-caption">—</span>
          </div>
        </q-td>
      </template>

      <!-- Next Follow-up -->
      <template #body-cell-control_date="props">
        <q-td :props="props">
          <span v-if="props.row.control_date"
            :style="isOverdue(props.row.control_date) ? 'color:#C62828;font-weight:700;font-size:12px;' : 'color:#424242;font-size:12px;'">
            <q-icon v-if="isOverdue(props.row.control_date)" name="warning" size="12px" />
            {{ props.row.control_date }}
          </span>
          <span v-else class="text-grey-4 text-caption">—</span>
        </q-td>
      </template>

      <!-- Last Contact -->
      <template #body-cell-last_contact="props">
        <q-td :props="props">
          <span v-if="props.row.last_contact" class="text-caption" style="color:#424242;">
            {{ props.row.last_contact }}
          </span>
          <span v-else class="text-grey-4 text-caption">—</span>
        </q-td>
      </template>

      <!-- Responsible -->
      <template #body-cell-assigned_to="props">
        <q-td :props="props">
          <div v-if="props.row.assigned_to_detail" class="row items-center q-gutter-xs no-wrap">
            <q-avatar size="22px" color="primary" text-color="white" style="font-size:9px;flex-shrink:0;">
              {{ initials(props.row.assigned_to_detail) }}
            </q-avatar>
            <span style="font-size:12px;">{{ props.row.assigned_to_detail.full_name || props.row.assigned_to_detail.username }}</span>
          </div>
          <span v-else style="font-size:12px;color:#BDBDBD;">—</span>
        </q-td>
      </template>

      <!-- Tasks -->
      <template #body-cell-open_tasks="props">
        <q-td :props="props" class="text-center">
          <div v-if="props.row.open_tasks_count > 0" class="tasks-active">
            <q-icon name="task_alt" size="13px" />
            {{ props.row.open_tasks_count }}
          </div>
          <span v-else style="font-size:12px;color:#BDBDBD;">—</span>
        </q-td>
      </template>

      <template #no-data>
        <div class="full-width column flex-center q-pa-xl text-grey-5">
          <q-icon name="support_agent" size="48px" class="q-mb-sm" />
          <div>No producers in support yet</div>
        </div>
      </template>
    </q-table>

    <AddProducerDialog
      v-model="showAddDialog"
      :users="store.users"
      active-funnel="support"
      @created="onProducerAdded"
    />

  </q-page>
</template>

<script setup>
import { ref, computed, onMounted, onActivated } from 'vue'
import { useProducersStore } from 'src/stores/producers'
import { useAuthStore } from 'src/stores/auth'
import AddProducerDialog from 'src/components/AddProducerDialog.vue'

const store          = useProducersStore()
const authStore      = useAuthStore()
const loading        = ref(false)
const search         = ref('')
const filterOperator = ref(null)
const filterStage    = ref(null)
const onlyMine       = ref(false)
const showAddDialog  = ref(false)

const stageOptions = [
  { label: 'Agreed',            value: 'agreed' },
  { label: 'Signed',            value: 'signed' },
  { label: 'Products Received', value: 'products_received' },
  { label: 'Ready to Sell',     value: 'ready_to_sell' },
  { label: 'In Store',          value: 'in_store' },
]

const columns = [
  { name: 'name',                 label: 'Name / Company',     field: 'name',                    align: 'left',   sortable: true },
  { name: 'stage',                label: 'Stage',              field: 'stage',                   align: 'left',   sortable: true },
  { name: 'priority',             label: 'Priority / Coop',    field: 'priority',                align: 'left',   sortable: true },
  { name: 'communication_status', label: 'Comm. Status',       field: 'communication_status',    align: 'left' },
  { name: 'control_date',         label: 'Next Follow-up',     field: 'control_date',            align: 'left',   sortable: true },
  { name: 'last_contact',         label: 'Last Contact',       field: 'last_contact',            align: 'left',   sortable: true },
  { name: 'assigned_to',          label: 'Responsible',        field: r => r.assigned_to_detail?.full_name || '', align: 'left', sortable: true },
  { name: 'open_tasks',           label: 'Tasks',              field: 'open_tasks_count',        align: 'center', sortable: true },
]

const supportProducers = computed(() =>
  store.producers.filter(p => p.funnel === 'support')
)

const operatorOptions = computed(() => {
  const seen = new Set()
  const opts = []
  for (const p of supportProducers.value) {
    if (p.assigned_to && !seen.has(p.assigned_to)) {
      seen.add(p.assigned_to)
      const d = p.assigned_to_detail
      opts.push({ label: d?.full_name || d?.username || `User ${p.assigned_to}`, value: p.assigned_to })
    }
  }
  return opts
})

const filteredRows = computed(() => {
  let rows = supportProducers.value
  if (filterStage.value)    rows = rows.filter(p => p.stage === filterStage.value)
  if (filterOperator.value) rows = rows.filter(p => p.assigned_to === filterOperator.value)
  else if (onlyMine.value)  rows = rows.filter(p => p.assigned_to === authStore.user?.id)
  if (search.value.trim()) {
    const q = search.value.trim().toLowerCase()
    rows = rows.filter(p =>
      (p.name || '').toLowerCase().includes(q) ||
      (p.company || '').toLowerCase().includes(q)
    )
  }
  return rows
})

const stageStyle = (s) => ({
  agreed:           { bg: '#E3F2FD', color: '#1565C0' },
  signed:           { bg: '#F3E5F5', color: '#6A1B9A' },
  products_received:{ bg: '#E0F7FA', color: '#00838F' },
  ready_to_sell:    { bg: '#FBE9E7', color: '#E65100' },
  in_store:         { bg: '#E8F5E9', color: '#2E7D32' },
}[s] || { bg: '#F5F5F5', color: '#757575' })

const priorityPill = (p) => ({
  high:   'background:#FFEBEE;color:#C62828;border:1px solid #FFCDD2;',
  medium: 'background:#FFF3E0;color:#E65100;border:1px solid #FFCC80;',
  low:    'background:#F5F5F5;color:#757575;border:1px solid #E0E0E0;',
}[p] || 'background:#F5F5F5;color:#757575;')

const coopDot = (p) => ({
  strong:      '#43A047',
  medium:      '#1E88E5',
  weak:        '#FF7043',
  no_response: '#9E9E9E',
}[p] || '#9E9E9E')

const splitTags = (str) => (str || '').split(',').map(s => s.trim()).filter(Boolean)
const isOverdue = (d) => d && new Date(d) < new Date(new Date().toDateString())
const initials  = (u) => ((u?.full_name || u?.username || '?').split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2))

const onProducerAdded = () => { showAddDialog.value = false; load() }

const load = async () => {
  loading.value = true
  try { await store.fetchProducers({ funnel: 'support' }) }
  finally { loading.value = false }
}

onMounted(async () => { await Promise.all([load(), store.fetchUsers()]) })
onActivated(load)
</script>

<style scoped>
.tasks-active {
  display: inline-flex; align-items: center; gap: 4px;
  background: #FFF3E0; color: #E65100;
  font-size: 12px; font-weight: 700;
  padding: 2px 8px; border-radius: 8px;
}
</style>
