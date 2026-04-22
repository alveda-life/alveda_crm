<template>
  <q-page class="q-pa-md">

    <!-- Toolbar -->
    <div class="row items-center q-mb-md q-gutter-sm">
      <!-- Search -->
      <q-input
        v-model="store.filters.search"
        outlined dense
        :placeholder="`Search ${funnelLabel}...`"
        style="min-width:220px;"
        debounce="400"
        @update:model-value="store.fetchKanban()"
        clearable
        @clear="store.fetchKanban()"
      >
        <template #prepend><q-icon name="search" /></template>
      </q-input>

      <!-- Operator filter (admins only) -->
      <q-select
        v-if="authStore.isAdmin"
        v-model="store.filters.assigned_to"
        :options="operatorOptions"
        emit-value map-options
        outlined dense clearable
        placeholder="All Operators"
        style="min-width:160px;"
        @update:model-value="store.fetchKanban()"
      />

      <q-btn
        :outline="!onlyMine"
        :color="onlyMine ? 'primary' : 'grey-7'"
        :icon="onlyMine ? 'person' : 'person_outline'"
        label="Assigned to Me"
        dense unelevated no-caps
        style="border-radius:8px;font-size:13px;"
        @click="toggleMine"
      />

      <q-space />

      <q-btn
        v-if="canCreate"
        color="primary"
        icon="add"
        label="Add Producer"
        unelevated
        style="border-radius:8px;"
        @click="showAddDialog = true"
      />
    </div>

    <!-- Stage stats chips -->
    <div class="row q-gutter-xs q-mb-md" v-if="store.stats">
      <q-chip
        v-for="(cfg, key) in activeStageConfig"
        :key="key"
        dense
        :style="`background:${cfg.bgLight};color:${cfg.color};border:1px solid ${cfg.color}33;`"
        class="text-weight-medium"
      >
        <q-avatar :color="cfg.colorName" text-color="white" size="18px" style="font-size:10px;">
          {{ store.stats.by_stage?.[key] ?? 0 }}
        </q-avatar>
        {{ cfg.label }}
      </q-chip>
    </div>

    <!-- Kanban board -->
    <div class="kanban-container" v-if="!store.loading">
      <div
        v-for="(cfg, key) in activeStageConfig"
        :key="key"
        class="kanban-column"
      >
        <!-- Column header -->
        <div
          class="q-pa-sm q-mb-sm row items-center justify-between"
          :style="`background:${cfg.bgLight};border-radius:10px;border-left:4px solid ${cfg.color};`"
        >
          <div class="row items-center q-gutter-xs">
            <q-icon :name="cfg.icon" :color="cfg.colorName" size="18px" />
            <span class="text-subtitle2 text-weight-bold" :style="`color:${cfg.color}`">
              {{ cfg.label }}
            </span>
          </div>
          <q-badge :style="`background:${cfg.color};color:white;`" rounded>
            {{ (store.kanbanData[key] || []).length }}
          </q-badge>
        </div>

        <!-- Draggable cards -->
        <draggable
          v-model="store.kanbanData[key]"
          group="producers"
          item-key="id"
          :animation="150"
          ghost-class="drag-ghost"
          chosen-class="drag-chosen"
          :disabled="!canEdit"
          @add="(evt) => onDragEnd(evt, key)"
          class="kanban-cards"
          :class="{ 'drag-over': dragOver === key }"
          @dragover="dragOver = key"
          @dragleave="dragOver = null"
        >
          <template #item="{ element }">
            <ProducerCard
              :producer="element"
              :stage-color="cfg.color"
              :users="store.users"
              :active-funnel="props.funnel"
              class="q-mb-sm"
              @click="openProducer(element.id)"
              @assign="handleAssign"
              @move-funnel="handleMoveFunnel"
            />
          </template>
        </draggable>
      </div>
    </div>

    <div v-else class="row justify-center q-mt-xl">
      <q-spinner-dots color="primary" size="48px" />
    </div>

    <!-- Add Producer Dialog -->
    <AddProducerDialog
      v-model="showAddDialog"
      :users="store.users"
      :active-funnel="funnel"
      @created="onProducerCreated"
    />

  </q-page>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import draggable from 'vuedraggable'
import { useProducersStore } from 'src/stores/producers'
import { useAuthStore }     from 'src/stores/auth'
import ProducerCard from 'src/components/ProducerCard.vue'
import AddProducerDialog from 'src/components/AddProducerDialog.vue'

const props = defineProps({
  funnel: { type: String, default: 'onboarding' },
})

const $q        = useQuasar()
const router    = useRouter()
const store     = useProducersStore()
const authStore = useAuthStore()

const showAddDialog = ref(false)
const dragOver      = ref(null)
const onlyMine      = ref(false)

function toggleMine() {
  onlyMine.value = !onlyMine.value
  store.filters.assigned_to = onlyMine.value ? authStore.user?.id : null
  store.fetchKanban()
}

const activeSection = computed(() =>
  props.funnel === 'onboarding' ? 'producers_onboarding' : 'producers_support'
)
const canCreate = computed(() => authStore.can(activeSection.value, 'create'))
const canEdit   = computed(() => authStore.can(activeSection.value, 'edit'))

const funnelLabel = computed(() =>
  props.funnel === 'onboarding' ? 'onboarding producers' : 'support producers'
)

const onboardingStages = {
  interest:        { label: 'Interest',          color: '#F44336', colorName: 'red',           bgLight: '#FFEBEE', icon: 'star_outline' },
  in_communication: { label: 'In Communication', color: '#FF9800', colorName: 'orange',         bgLight: '#FFF3E0', icon: 'forum' },
  terms_negotiation:{ label: 'Negotiation',       color: '#EF6C00', colorName: 'deep-orange-9',  bgLight: '#FBE9E7', icon: 'sync_alt' },
  negotiation:      { label: 'Signing Contract',  color: '#9C27B0', colorName: 'purple',         bgLight: '#F3E5F5', icon: 'gavel' },
  contract_signed: { label: 'Contract Signed',   color: '#1565C0', colorName: 'blue-9',         bgLight: '#E3F2FD', icon: 'draw' },
  on_platform:     { label: 'On the Platform',   color: '#2E7D32', colorName: 'green-9',        bgLight: '#E8F5E9', icon: 'rocket_launch' },
  stopped:         { label: 'Stopped',           color: '#757575', colorName: 'grey-7',         bgLight: '#F5F5F5', icon: 'block' },
}

const supportStages = {
  agreed:           { label: 'Agreed',           color: '#1565C0', colorName: 'blue-9',        bgLight: '#E3F2FD', icon: 'handshake' },
  signed:           { label: 'Signed',           color: '#6A1B9A', colorName: 'purple-9',      bgLight: '#F3E5F5', icon: 'draw' },
  products_received:{ label: 'Products Received',color: '#00838F', colorName: 'cyan-8',        bgLight: '#E0F7FA', icon: 'inventory_2' },
  ready_to_sell:    { label: 'Ready to Sell',    color: '#E65100', colorName: 'deep-orange-9', bgLight: '#FBE9E7', icon: 'storefront' },
  in_store:         { label: 'In Store',         color: '#2E7D32', colorName: 'green-9',       bgLight: '#E8F5E9', icon: 'check_circle' },
}

const activeStageConfig = computed(() =>
  props.funnel === 'onboarding' ? onboardingStages : supportStages
)

const operatorOptions = computed(() =>
  store.users.map(u => ({ label: u.full_name || u.username, value: u.id }))
)

// Re-fetch when funnel prop changes (switching between sidebar items)
watch(() => props.funnel, () => {
  store.fetchKanban(props.funnel)
})

const openProducer = (id) => router.push(`/producers/${id}`)

const handleAssign = async ({ producerId, userId }) => {
  try {
    await store.updateProducer(producerId, { assigned_to: userId })
    $q.notify({ type: 'positive', message: 'Operator assigned', timeout: 1500 })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to assign' })
  }
}

const handleMoveFunnel = async ({ producerId, targetFunnel, targetStage }) => {
  try {
    await store.updateStage(producerId, targetStage, targetFunnel)
    const label = targetFunnel === 'support' ? 'Support' : 'Onboarding'
    $q.notify({ type: 'positive', message: `Moved to ${label} funnel`, timeout: 2000 })
    store.fetchStats()
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to move producer' })
  }
}

const onDragEnd = async (evt, toStage) => {
  dragOver.value = null
  const moved = store.kanbanData[toStage]?.[evt.newIndex]
  if (!moved) return
  try {
    await store.updateStage(moved.id, toStage, props.funnel)
    $q.notify({ type: 'positive', message: `Moved to "${activeStageConfig.value[toStage]?.label}"`, timeout: 1500 })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to move card' })
    store.fetchKanban(props.funnel)
  }
}

const onProducerCreated = () => {
  showAddDialog.value = false
  store.fetchKanban(props.funnel)
  store.fetchStats()
  $q.notify({ type: 'positive', message: 'Producer added' })
}

onMounted(async () => {
  // Reset stale per-operator filter that might have leaked in from another page
  store.filters.assigned_to = ''
  store.filters.search      = ''
  await Promise.all([
    store.fetchKanban(props.funnel),
    store.fetchStats(),
    store.fetchUsers(),
  ])
})
</script>

<style scoped>
.kanban-container {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 16px;
  min-height: calc(100vh - 200px);
}
.kanban-column {
  min-width: 240px;
  max-width: 280px;
  flex: 1;
  display: flex;
  flex-direction: column;
}
.kanban-cards {
  flex: 1;
  min-height: 80px;
  padding: 4px;
  border-radius: 8px;
  transition: background 0.2s;
}
.kanban-cards.drag-over { background: rgba(0,0,0,0.04); }
.drag-ghost  { opacity: 0.4; }
.drag-chosen { box-shadow: 0 8px 24px rgba(0,0,0,0.2) !important; }
</style>
