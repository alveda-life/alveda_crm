<template>
  <q-page class="q-pa-md">
    <!-- Toolbar -->
    <div class="row items-center q-mb-md q-gutter-sm">
      <q-input
        v-model="search"
        outlined
        dense
        placeholder="Search by name, phone, ID..."
        style="min-width: 260px;"
        debounce="400"
        clearable
        @update:model-value="loadPartners"
        @clear="loadPartners"
      >
        <template #prepend><q-icon name="search" /></template>
      </q-input>

      <q-select
        v-model="filters.stage"
        :options="stageOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="All Stages"
        style="min-width: 150px;"
        @update:model-value="loadPartners"
      />
      <q-select
        v-model="filters.status"
        :options="statusOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="All Statuses"
        style="min-width: 140px;"
        @update:model-value="loadPartners"
      />
      <q-select
        v-model="filters.type"
        :options="typeOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="All Types"
        style="min-width: 130px;"
        @update:model-value="loadPartners"
      />
      <q-select
        v-model="filters.category"
        :options="categoryOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="All Categories"
        style="min-width: 160px;"
        @update:model-value="loadPartners"
      />

      <q-input
        :model-value="controlDateLabel"
        outlined dense readonly clearable
        placeholder="Control date"
        style="min-width: 220px;"
        @clear="clearControlDate"
      >
        <template #prepend><q-icon name="event" /></template>
        <q-popup-proxy ref="controlDatePopup" cover transition-show="scale" transition-hide="scale">
          <q-date
            v-model="controlDateRange"
            range
            mask="YYYY-MM-DD"
            today-btn
            @update:model-value="onControlDateChange"
          />
        </q-popup-proxy>
      </q-input>

      <q-btn
        :outline="!onlyMine"
        :color="onlyMine ? 'primary' : 'grey-7'"
        :icon="onlyMine ? 'person' : 'person_outline'"
        label="Assigned to Me"
        dense unelevated no-caps
        style="border-radius:8px;font-size:13px;"
        @click="onlyMine = !onlyMine; loadPartners()"
      />

      <q-space />

      <q-btn v-if="!authStore.isOperator" color="primary" icon="add" label="Add Partner" unelevated
        @click="showAddDialog = true" style="border-radius:8px;" />
    </div>

    <!-- Table -->
    <q-card flat bordered style="border-radius: 12px; overflow: hidden;">
      <q-table
        :rows="partners"
        :columns="columns"
        row-key="id"
        :loading="loading"
        flat
        :rows-per-page-options="[25, 50, 100]"
        v-model:pagination="pagination"
        @request="onRequest"
        binary-state-sort
        @row-click="(evt, row) => openPartner(row.id)"
        class="partners-table"
      >
        <!-- Name column -->
        <template #body-cell-name="props">
          <q-td :props="props">
            <div class="table-name-tag"
              :style="`background:${nameColor(props.row).bg};color:${nameColor(props.row).text}`">
              {{ props.row.name }}
            </div>
            <div class="text-caption text-grey-6">{{ props.row.phone }}</div>
            <div v-if="props.row.city || props.row.state" class="text-caption text-grey-5">
              {{ [props.row.city, props.row.state].filter(Boolean).join(', ') }}
            </div>
          </q-td>
        </template>

        <!-- Type + Category column -->
        <template #body-cell-type="props">
          <q-td :props="props">
            <q-chip dense size="sm" :class="`chip-type-${props.row.type}`" class="q-mr-xs">
              {{ props.row.type_display }}
            </q-chip>
            <q-chip v-if="props.row.category" dense size="sm" :class="`chip-${props.row.category}`">
              {{ props.row.category_display }}
            </q-chip>
          </q-td>
        </template>

        <!-- Stage column -->
        <template #body-cell-stage="props">
          <q-td :props="props">
            <q-chip dense :class="`badge-${props.row.stage}`">
              {{ props.row.stage_display }}
            </q-chip>
          </q-td>
        </template>

        <!-- Status column -->
        <template #body-cell-status="props">
          <q-td :props="props">
            <q-chip dense size="sm"
              :color="{ new: 'grey-5', in_support: 'blue', closed: 'red' }[props.row.status] || 'grey-5'"
              text-color="white">
              {{ props.row.status_display || props.row.status }}
            </q-chip>
          </q-td>
        </template>

        <!-- Control date column -->
        <template #body-cell-control_date="props">
          <q-td :props="props">
            <template v-if="props.row.control_date">
              <div v-if="isOverdue(props.row.control_date)"
                style="background:#FF1744; color:white; border-radius:6px; padding:3px 8px; font-size:12px; font-weight:700; display:inline-flex; align-items:center; gap:4px; white-space:nowrap;">
                <q-icon name="warning" size="13px" /> OVERDUE · {{ formatControlDate(props.row.control_date) }}
              </div>
              <div v-else-if="isToday(props.row.control_date)"
                style="background:#FF6F00; color:white; border-radius:6px; padding:3px 8px; font-size:12px; font-weight:700; display:inline-flex; align-items:center; gap:4px; white-space:nowrap;">
                <q-icon name="today" size="13px" /> TODAY
              </div>
              <div v-else
                style="background:#E3F2FD; color:#0277BD; border-radius:6px; padding:3px 8px; font-size:12px; font-weight:600; display:inline-flex; align-items:center; gap:4px; white-space:nowrap;">
                <q-icon name="event" size="13px" /> {{ formatControlDate(props.row.control_date) }}
              </div>
            </template>
            <span v-else class="text-grey-4 text-caption">—</span>
          </q-td>
        </template>

        <!-- Revenue column -->
        <template #body-cell-paid_orders_sum="props">
          <q-td :props="props" class="text-weight-bold text-positive">
            ₹{{ formatMoney(props.row.paid_orders_sum) }}
          </q-td>
        </template>

        <!-- Assigned column -->
        <template #body-cell-assigned_to="props">
          <q-td :props="props">
            <span v-if="props.row.assigned_to_detail" class="text-caption">{{ props.row.assigned_to_detail.full_name }}</span>
            <span v-else class="text-grey-5 text-caption">Unassigned</span>
          </q-td>
        </template>

        <!-- Contacts column -->
        <template #body-cell-contacts_count="props">
          <q-td :props="props">
            <q-chip dense icon="phone" color="grey-3" text-color="grey-8" size="sm">
              {{ props.row.contacts_count }}
            </q-chip>
          </q-td>
        </template>

        <!-- Actions -->
        <template #body-cell-actions="props">
          <q-td :props="props" @click.stop>
            <q-btn flat round dense icon="open_in_new" size="sm" color="grey-6"
              @click="openPartner(props.row.id)">
              <q-tooltip>Open details</q-tooltip>
            </q-btn>
            <q-btn v-if="authStore.isAdmin" flat round dense icon="delete" size="sm" color="negative"
              @click="confirmDelete(props.row)">
              <q-tooltip>Delete</q-tooltip>
            </q-btn>
          </q-td>
        </template>
      </q-table>
    </q-card>

    <AddPartnerDialog
      v-model="showAddDialog"
      :users="store.users"
      @created="onCreated"
    />
  </q-page>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import { useAuthStore } from 'src/stores/auth'
import { usePartnersStore } from 'src/stores/partners'
import AddPartnerDialog from 'src/components/AddPartnerDialog.vue'
import { nameColor } from 'src/utils/partnerColors'

const $q = useQuasar()
const router = useRouter()
const authStore = useAuthStore()
const store = usePartnersStore()

const partners = ref([])
const loading = ref(false)
const search = ref('')
const showAddDialog = ref(false)
const onlyMine = ref(false)

const filters = reactive({ stage: '', status: '', type: '', category: '' })
const controlDateRange = ref(null)
const controlDatePopup = ref(null)

const controlDateLabel = computed(() => {
  const v = controlDateRange.value
  if (!v) return ''
  if (typeof v === 'string') return v
  return v.from === v.to ? v.from : `${v.from} → ${v.to}`
})

const onControlDateChange = () => {
  loadPartners()
  controlDatePopup.value?.hide()
}

const clearControlDate = () => {
  controlDateRange.value = null
  loadPartners()
}
const pagination = ref({ page: 1, rowsPerPage: 25, rowsNumber: 0, sortBy: 'created_at', descending: true })

const columns = [
  { name: 'name', label: 'Partner', field: 'name', align: 'left', sortable: true },
  { name: 'type', label: 'Type / Category', field: 'type', align: 'left' },
  { name: 'stage', label: 'Stage', field: 'stage', align: 'left', sortable: true },
  { name: 'status', label: 'Status', field: 'status', align: 'left', sortable: true },
  { name: 'control_date', label: 'Control Date', field: 'control_date', align: 'left', sortable: true },
  { name: 'medical_sets_count', label: 'Sets', field: 'medical_sets_count', align: 'center', sortable: true },
  { name: 'paid_orders_count', label: 'Paid Orders', field: 'paid_orders_count', align: 'center', sortable: true },
  { name: 'paid_orders_sum', label: 'Revenue', field: 'paid_orders_sum', align: 'right', sortable: true },
  { name: 'contacts_count', label: 'Calls', field: 'contacts_count', align: 'center' },
  { name: 'assigned_to', label: 'Operator', field: 'assigned_to', align: 'left' },
  { name: 'actions', label: '', field: 'actions', align: 'right' },
]

const stageOptions = [
  { label: 'New', value: 'new' },
  { label: 'Agreed to Create First Set', value: 'trained' },
  { label: 'Set Created', value: 'set_created' },
  { label: 'Has Sale', value: 'has_sale' },
  { label: 'Dead (No Answer)', value: 'no_answer' },
  { label: 'Dead (Declined)', value: 'declined' },
  { label: 'Dead (No Sales)', value: 'no_sales' },
]
const statusOptions = [
  { label: 'New', value: 'new' },
  { label: 'In Support', value: 'in_support' },
  { label: 'Closed', value: 'closed' },
]
const typeOptions = [
  { label: 'Partner', value: 'partner' },
  { label: 'Medic', value: 'medic' },
]
const categoryOptions = [
  { label: 'Doctor', value: 'doctor' },
  { label: 'Fitness Trainer', value: 'fitness_trainer' },
  { label: 'Blogger', value: 'blogger' },
  { label: 'Other', value: 'other' },
]

const todayStr = () => new Date().toISOString().slice(0, 10)
const isToday = (dateStr) => dateStr === todayStr()
const isOverdue = (dateStr) => dateStr && dateStr < todayStr()
const formatControlDate = (dateStr) => new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', { day: 'numeric', month: 'short' })


const formatMoney = (val) => {
  if (!val) return '0'
  return Number(val).toLocaleString('en-US', { minimumFractionDigits: 0 })
}

const loadPartners = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.rowsPerPage,
    }
    if (search.value) params.search = search.value
    if (filters.stage) params.stage = filters.stage
    if (filters.status) params.status = filters.status
    if (filters.type) params.type = filters.type
    if (filters.category) params.category = filters.category
    const cd = controlDateRange.value
    if (cd) {
      if (typeof cd === 'string') {
        params.control_date_from = cd
        params.control_date_to = cd
      } else {
        if (cd.from) params.control_date_from = cd.from
        if (cd.to)   params.control_date_to   = cd.to
      }
    }
    if (onlyMine.value) params.assigned_to = authStore.user?.id
    if (pagination.value.sortBy) {
      params.ordering = (pagination.value.descending ? '-' : '') + pagination.value.sortBy
    }
    const data = await store.fetchPartners(params)
    partners.value = data.results || data
    pagination.value.rowsNumber = data.count || partners.value.length
  } finally {
    loading.value = false
  }
}

const onRequest = (props) => {
  pagination.value = props.pagination
  loadPartners()
}

const openPartner = (id) => router.push(`/partners/${id}`)

const confirmDelete = (row) => {
  $q.dialog({
    title: 'Delete Partner',
    message: `Delete "${row.name}"? This cannot be undone.`,
    cancel: true,
    persistent: true,
    ok: { label: 'Delete', color: 'negative', flat: false },
  }).onOk(async () => {
    await store.deletePartner(row.id)
    loadPartners()
    store.fetchStats()
    $q.notify({ type: 'positive', message: 'Partner deleted' })
  })
}

const onCreated = () => {
  showAddDialog.value = false
  loadPartners()
  store.fetchStats()
  $q.notify({ type: 'positive', message: 'Partner added successfully' })
}

onMounted(() => loadPartners())
</script>

<style scoped>
.partners-table :deep(.q-tr) { cursor: pointer; }
.table-name-tag {
  display: inline-block;
  font-size: 13px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
  margin-bottom: 2px;
}
</style>
