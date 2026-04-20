<template>
  <q-page class="q-pa-md">

    <!-- Toolbar -->
    <div class="row items-center q-mb-md q-gutter-sm">

      <q-select
        v-model="filterStage"
        :options="stageOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="All Stages"
        style="min-width:150px"
        @update:model-value="load"
      />

      <q-select
        v-if="authStore.isAdmin"
        v-model="filterOperator"
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

      <!-- Summary chips -->
      <template v-if="rows.length">
        <q-chip dense icon="person_off" color="deep-orange-1" text-color="deep-orange-8" style="font-weight:700">
          {{ rows.length }} abandoned
        </q-chip>
        <q-chip v-if="neverContactedCount > 0" dense icon="voice_over_off" color="red-1" text-color="red-8" style="font-weight:700">
          {{ neverContactedCount }} never called
        </q-chip>
        <q-chip v-if="criticalCount > 0" dense icon="warning" color="orange-1" text-color="orange-9" style="font-weight:700">
          {{ criticalCount }} critical (&gt;30d)
        </q-chip>
      </template>

      <q-btn flat round icon="refresh" color="grey-6" :loading="loading" @click="load" />
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
        binary-state-sort
        @row-click="(evt, row) => openPartner(row.id)"
        class="abandoned-table"
        no-data-label="No abandoned partners — all partners are being contacted regularly"
      >
        <!-- Partner name -->
        <template #body-cell-name="props">
          <q-td :props="props">
            <div class="text-weight-medium">{{ props.row.name }}</div>
            <div v-if="props.row.phone" class="text-caption text-grey-6">{{ props.row.phone }}</div>
          </q-td>
        </template>

        <!-- Stage -->
        <template #body-cell-stage="props">
          <q-td :props="props">
            <q-chip dense :class="`badge-${props.row.stage}`">{{ props.row.stage_display }}</q-chip>
          </q-td>
        </template>

        <!-- Operator -->
        <template #body-cell-assigned_to="props">
          <q-td :props="props">
            <span v-if="props.row.assigned_to" class="text-caption">
              {{ props.row.assigned_to.name || props.row.assigned_to.username }}
            </span>
            <span v-else class="text-caption text-red-4">Unassigned</span>
          </q-td>
        </template>

        <!-- Days silent — key column -->
        <template #body-cell-days_silent="props">
          <q-td :props="props">
            <div
              class="silence-badge"
              :class="silenceClass(props.row)"
            >
              <q-icon :name="props.row.days_silent === null ? 'voice_over_off' : 'schedule'" size="13px" />
              {{ props.row.days_silent === null ? 'Never called' : `${props.row.days_silent}d` }}
            </div>
          </q-td>
        </template>

        <!-- Last contact -->
        <template #body-cell-last_contact="props">
          <q-td :props="props">
            <span v-if="props.row.last_contact" class="text-caption text-grey-7">
              {{ fmtDate(props.row.last_contact) }}
            </span>
            <span v-else class="text-caption text-red-4">—</span>
          </q-td>
        </template>

        <!-- Added -->
        <template #body-cell-created_at="props">
          <q-td :props="props">
            <span class="text-caption text-grey-5">{{ fmtDate(props.row.created_at) }}</span>
          </q-td>
        </template>

        <!-- Actions -->
        <template #body-cell-actions="props">
          <q-td :props="props" @click.stop>
            <q-btn flat round dense icon="open_in_new" size="sm" color="grey-6"
              @click="openPartner(props.row.id)">
              <q-tooltip>Open partner</q-tooltip>
            </q-btn>
          </q-td>
        </template>

      </q-table>
    </q-card>

  </q-page>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePartnersStore } from 'src/stores/partners'
import { useAuthStore } from 'src/stores/auth'

const router = useRouter()
const store = usePartnersStore()
const authStore = useAuthStore()

const loading = ref(false)
const rows = ref([])
const filterStage = ref(null)
const filterOperator = ref(null)
const onlyMine = ref(false)

const pagination = ref({
  sortBy: 'days_silent',
  descending: true,
  rowsPerPage: 25,
})

const columns = [
  { name: 'name',         label: 'Partner',       field: 'name',         align: 'left',   sortable: true },
  { name: 'stage',        label: 'Stage',          field: 'stage',        align: 'left',   sortable: true },
  { name: 'assigned_to',  label: 'Operator',       field: r => r.assigned_to?.name || '', align: 'left', sortable: true },
  { name: 'days_silent',  label: 'Silent',         field: r => r.days_silent ?? -1,       align: 'left',   sortable: true },
  { name: 'last_contact', label: 'Last Contact',   field: 'last_contact', align: 'left',   sortable: true },
  { name: 'created_at',   label: 'Added',          field: 'created_at',   align: 'left',   sortable: true },
  { name: 'actions',      label: '',               field: 'actions',      align: 'right' },
]

const stageOptions = [
  { label: 'New',              value: 'new' },
  { label: 'Agreed to Create First Set', value: 'trained' },
  { label: 'Set Created',      value: 'set_created' },
  { label: 'Has Sale',         value: 'has_sale' },
  { label: '— Dead: No Answer', value: 'no_answer' },
  { label: '— Dead: Declined', value: 'declined' },
  { label: '— Dead: No Sales', value: 'no_sales' },
]

const operatorOptions = computed(() =>
  (store.users || []).map(u => ({
    label: `${u.first_name} ${u.last_name}`.trim() || u.username,
    value: u.id,
  }))
)

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filterStage.value)    params.stage       = filterStage.value
    if (filterOperator.value) params.assigned_to = filterOperator.value
    else if (onlyMine.value)  params.assigned_to = authStore.user?.id
    const data = await store.fetchAbandoned(params)
    // days_silent null (never called) → sort as very large number
    rows.value = (data.results || []).map(r => ({
      ...r,
      _sort_days: r.days_silent === null ? 99999 : r.days_silent,
    }))
  } finally {
    loading.value = false
  }
}

const neverContactedCount = computed(() => rows.value.filter(r => r.days_silent === null).length)
const criticalCount        = computed(() => rows.value.filter(r => r.days_silent !== null && r.days_silent > 30).length)

function silenceClass(row) {
  if (row.days_silent === null)  return 'silence--never'
  if (row.days_silent > 60)      return 'silence--critical'
  if (row.days_silent > 30)      return 'silence--bad'
  return 'silence--warn'
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })
}

const openPartner = (id) => router.push(`/partners/${id}`)

onMounted(() => {
  if (!store.users.length) store.fetchUsers()
  load()
})
</script>

<style scoped>
.abandoned-table :deep(.q-tr) { cursor: pointer; }

.silence-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 10px;
  white-space: nowrap;
}
.silence--warn     { background: #FFF3E0; color: #E65100; }
.silence--bad      { background: #FBE9E7; color: #BF360C; }
.silence--critical { background: #FFEBEE; color: #B71C1C; }
.silence--never    { background: #B71C1C; color: #fff; }
</style>
