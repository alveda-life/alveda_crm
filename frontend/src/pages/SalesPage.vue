<template>
  <q-page class="q-pa-md">

    <!-- Toolbar -->
    <div class="row items-center q-mb-md q-gutter-sm">
      <q-icon name="filter_alt" color="deep-purple" size="22px" />
      <div class="text-h6 text-weight-bold">Sales Funnel</div>
      <q-badge color="deep-purple" text-color="white" rounded style="font-size:12px;padding:3px 9px;">
        {{ allPartners.length }}
      </q-badge>
      <q-btn
        :outline="!onlyMine"
        :color="onlyMine ? 'primary' : 'grey-7'"
        :icon="onlyMine ? 'person' : 'person_outline'"
        label="Assigned to Me"
        dense unelevated no-caps
        style="border-radius:8px;font-size:13px;"
        @click="onlyMine = !onlyMine; loadSales()"
      />
      <q-space />
      <q-btn-toggle
        v-model="viewMode"
        toggle-color="primary"
        :options="[
          { value: 'cards', icon: 'view_kanban' },
          { value: 'table', icon: 'table_rows' },
        ]"
        flat dense rounded
        style="border: 1px solid #E0E0E0; border-radius: 8px;"
      />
    </div>

    <div v-if="loading" class="flex flex-center" style="min-height:300px;">
      <q-spinner-dots color="primary" size="48px" />
    </div>

    <div v-else>

      <!-- ══════════ CARD VIEW — funnel ══════════ -->
      <div v-if="viewMode === 'cards'" class="funnel-board">
        <div v-for="stage in funnelStages" :key="stage.key" class="funnel-col">

          <!-- Column header -->
          <div class="q-pa-sm q-mb-sm row items-center justify-between"
            :style="`background:${stage.bgLight}; border-radius:10px; border-left:4px solid ${stage.color};`">
            <div class="row items-center q-gutter-xs">
              <q-icon :name="stage.icon" size="18px" :style="`color:${stage.color}`" />
              <span class="text-subtitle2 text-weight-bold" :style="`color:${stage.color}`">
                {{ stage.label }}
              </span>
            </div>
            <div class="text-white text-weight-bold q-px-sm q-py-xs"
              style="border-radius:12px; font-size:13px;"
              :style="`background:${stage.color};`">
              {{ funnelGroups[stage.key].length }}
            </div>
          </div>

          <div v-if="funnelGroups[stage.key].length === 0"
            class="text-center text-grey-4 text-caption q-py-lg">
            No partners yet
          </div>

          <div v-for="p in funnelGroups[stage.key]" :key="p.id"
            class="q-mb-sm cursor-pointer partner-mini-card"
            @click="$router.push(`/partners/${p.id}`)">

            <!-- Name + contact -->
            <div class="text-weight-bold" style="font-size:14px;color:#212121;">{{ p.name }}</div>
            <div class="text-caption text-grey-6">{{ p.phone || 'No phone' }}</div>
            <div v-if="p.city || p.state" class="text-caption text-grey-5">
              {{ [p.city, p.state].filter(Boolean).join(', ') }}
            </div>

            <!-- Type / category -->
            <div class="row q-gutter-xs q-mt-xs q-mb-xs" style="flex-wrap:wrap;">
              <span :style="`background:${p.type === 'medic' ? '#7B1FA2' : '#546E7A'};color:white;border-radius:4px;padding:2px 7px;font-size:11px;font-weight:600;`">
                {{ p.type_display }}
              </span>
              <span v-if="p.type === 'partner' && p.category"
                style="background:#ECEFF1;color:#455A64;border-radius:4px;padding:2px 7px;font-size:11px;">
                {{ p.category_display }}
              </span>
              <span :style="`background:${statusBg(p.status)};color:white;border-radius:4px;padding:2px 7px;font-size:11px;font-weight:600;`">
                {{ p.status_display || p.status }}
              </span>
            </div>

            <!-- Revenue + orders -->
            <div class="row items-center justify-between"
              style="background:linear-gradient(135deg,#E8F5E9,#F1F8E9);border-radius:8px;padding:6px 10px;margin-bottom:6px;">
              <div>
                <div style="font-size:16px;font-weight:800;color:#2E7D32;line-height:1.1;">₹{{ formatMoney(p.paid_orders_sum) }}</div>
                <div style="font-size:10px;color:#81C784;">Revenue</div>
              </div>
              <div style="text-align:right;">
                <div style="font-size:16px;font-weight:800;color:#1565C0;line-height:1.1;">{{ p.paid_orders_count }}</div>
                <div style="font-size:10px;color:#90CAF9;">Orders</div>
              </div>
            </div>

            <!-- Control date -->
            <div v-if="p.control_date">
              <div v-if="isOverdue(p.control_date)"
                style="background:#FF1744;color:white;border-radius:5px;padding:2px 7px;font-size:11px;font-weight:700;display:inline-flex;align-items:center;gap:3px;">
                <q-icon name="warning" size="11px" /> OVERDUE · {{ formatDate(p.control_date) }}
              </div>
              <div v-else-if="isToday(p.control_date)"
                style="background:#FF6F00;color:white;border-radius:5px;padding:2px 7px;font-size:11px;font-weight:700;display:inline-flex;align-items:center;gap:3px;">
                <q-icon name="today" size="11px" /> TODAY
              </div>
              <div v-else
                style="background:#E3F2FD;color:#0277BD;border-radius:5px;padding:2px 7px;font-size:11px;font-weight:600;display:inline-flex;align-items:center;gap:3px;">
                <q-icon name="event" size="11px" /> {{ formatDate(p.control_date) }}
              </div>
            </div>

          </div>
        </div>
      </div>

      <!-- ══════════ TABLE VIEW ══════════ -->
      <q-card v-else flat bordered style="border-radius:12px;overflow:hidden;">
        <q-table
          :rows="allPartners"
          :columns="tableColumns"
          row-key="id"
          flat
          :rows-per-page-options="[25, 50, 100]"
          @row-click="(e, row) => $router.push(`/partners/${row.id}`)"
          class="sales-table"
        >
          <!-- Name -->
          <template #body-cell-name="props">
            <q-td :props="props">
              <div class="text-weight-medium">{{ props.row.name }}</div>
              <div class="text-caption text-grey-6">{{ props.row.phone }}</div>
              <div v-if="props.row.city || props.row.state" class="text-caption text-grey-5">
                {{ [props.row.city, props.row.state].filter(Boolean).join(', ') }}
              </div>
            </q-td>
          </template>

          <!-- Type / Category -->
          <template #body-cell-type="props">
            <q-td :props="props">
              <q-chip dense size="sm"
                :color="props.row.type === 'medic' ? 'purple' : 'blue-grey'"
                text-color="white" class="q-mr-xs">
                {{ props.row.type_display }}
              </q-chip>
              <q-chip v-if="props.row.type === 'partner' && props.row.category"
                dense size="sm" color="blue-grey-2" text-color="blue-grey-9">
                {{ props.row.category_display }}
              </q-chip>
            </q-td>
          </template>

          <!-- Revenue -->
          <template #body-cell-paid_orders_sum="props">
            <q-td :props="props" class="text-weight-bold text-positive">
              ₹{{ formatMoney(props.row.paid_orders_sum) }}
            </q-td>
          </template>

          <!-- Paid orders -->
          <template #body-cell-paid_orders_count="props">
            <q-td :props="props">
              <q-chip dense :color="paidOrdersColor(props.row.paid_orders_count)"
                text-color="white" style="font-weight:700;">
                {{ props.row.paid_orders_count }}
              </q-chip>
            </q-td>
          </template>

          <!-- Control date -->
          <template #body-cell-control_date="props">
            <q-td :props="props">
              <template v-if="props.row.control_date">
                <div v-if="isOverdue(props.row.control_date)"
                  style="background:#FF1744;color:white;border-radius:6px;padding:3px 8px;font-size:12px;font-weight:700;display:inline-flex;align-items:center;gap:4px;white-space:nowrap;">
                  <q-icon name="warning" size="12px" /> OVERDUE · {{ formatDate(props.row.control_date) }}
                </div>
                <div v-else-if="isToday(props.row.control_date)"
                  style="background:#FF6F00;color:white;border-radius:6px;padding:3px 8px;font-size:12px;font-weight:700;display:inline-flex;align-items:center;gap:4px;white-space:nowrap;">
                  <q-icon name="today" size="12px" /> TODAY
                </div>
                <div v-else
                  style="background:#E3F2FD;color:#0277BD;border-radius:6px;padding:3px 8px;font-size:12px;font-weight:600;display:inline-flex;align-items:center;gap:4px;white-space:nowrap;">
                  <q-icon name="event" size="12px" /> {{ formatDate(props.row.control_date) }}
                </div>
              </template>
              <span v-else class="text-grey-4">—</span>
            </q-td>
          </template>

          <!-- Status -->
          <template #body-cell-status="props">
            <q-td :props="props">
              <q-chip dense size="sm"
                :color="{ new: 'grey-5', in_support: 'blue', closed: 'red' }[props.row.status] || 'grey-5'"
                text-color="white">
                {{ props.row.status_display || props.row.status }}
              </q-chip>
            </q-td>
          </template>

        </q-table>
      </q-card>

    </div>
  </q-page>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from 'src/stores/auth'
import { usePartnersStore } from 'src/stores/partners'

const authStore = useAuthStore()
const store = usePartnersStore()
const loading = ref(true)
const viewMode = ref('cards')
const onlyMine = ref(false)
const allPartners = ref([])

const funnelStages = [
  { key: 's1',  label: '1 Sale',   color: '#43A047', bgLight: '#E8F5E9', icon: 'looks_one' },
  { key: 's3',  label: '3 Sales',  color: '#1976D2', bgLight: '#E3F2FD', icon: 'looks_3'   },
  { key: 's5',  label: '5 Sales',  color: '#7B1FA2', bgLight: '#F3E5F5', icon: 'looks_5'   },
  { key: 's10', label: '10 Sales', color: '#E65100', bgLight: '#FBE9E7', icon: 'star'       },
]

const funnelGroups = computed(() => {
  const g = { s1: [], s3: [], s5: [], s10: [] }
  for (const p of allPartners.value) {
    const n = p.paid_orders_count
    if      (n >= 10) g.s10.push(p)
    else if (n >= 5)  g.s5.push(p)
    else if (n >= 3)  g.s3.push(p)
    else              g.s1.push(p)
  }
  return g
})

const tableColumns = [
  { name: 'name',             label: 'Partner',      field: 'name',             align: 'left',   sortable: true },
  { name: 'type',             label: 'Type',         field: 'type',             align: 'left'                   },
  { name: 'paid_orders_count',label: 'Paid Orders',  field: 'paid_orders_count',align: 'center', sortable: true },
  { name: 'paid_orders_sum',  label: 'Revenue',      field: 'paid_orders_sum',  align: 'right',  sortable: true },
  { name: 'control_date',     label: 'Follow-up',    field: 'control_date',     align: 'left',   sortable: true },
  { name: 'status',           label: 'Status',       field: 'status',           align: 'left',   sortable: true },
]

const todayStr   = () => new Date().toISOString().slice(0, 10)
const isToday    = (d) => d === todayStr()
const isOverdue  = (d) => d && d < todayStr()
const formatDate = (d) => new Date(d + 'T12:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
const formatMoney = (val) => {
  if (!val || Number(val) === 0) return '0'
  const n = Number(val)
  if (n >= 100000) return (n / 100000).toFixed(1) + 'L'
  if (n >= 1000)   return (n / 1000).toFixed(1) + 'k'
  return n.toLocaleString('en-IN')
}
const statusBg = (s) => ({ new: '#9E9E9E', in_support: '#1976D2', closed: '#D32F2F' }[s] || '#9E9E9E')
const paidOrdersColor = (n) => {
  if (n >= 10) return 'deep-orange'
  if (n >= 5)  return 'purple'
  if (n >= 3)  return 'blue'
  return 'green'
}

const loadSales = async () => {
  loading.value = true
  try {
    const params = { min_paid_orders: 1, page_size: 500, ordering: '-paid_orders_count' }
    if (onlyMine.value) params.assigned_to = authStore.user?.id
    const data = await store.fetchPartners(params)
    allPartners.value = data.results || data
  } finally {
    loading.value = false
  }
}

onMounted(loadSales)
</script>

<style scoped>
.funnel-board {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  align-items: start;
}
@media (max-width: 1100px) { .funnel-board { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px)  { .funnel-board { grid-template-columns: 1fr; } }

.partner-mini-card {
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.07);
  padding: 12px;
  transition: transform .15s, box-shadow .15s;
}
.partner-mini-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.11);
}
.sales-table :deep(.q-tr) { cursor: pointer; }
</style>
