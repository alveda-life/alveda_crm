<template>
  <q-page class="q-pa-md">
    <!-- Toolbar -->
    <div class="row items-center q-mb-md q-gutter-sm">
      <!-- Search -->
      <q-input
        v-model="store.filters.search"
        outlined
        dense
        placeholder="Search partners..."
        style="min-width: 220px;"
        debounce="400"
        @update:model-value="store.fetchKanban()"
        clearable
        @clear="store.fetchKanban()"
      >
        <template #prepend><q-icon name="search" /></template>
      </q-input>

      <!-- Type filter -->
      <q-select
        v-model="store.filters.type"
        :options="typeOptions"
        emit-value
        map-options
        outlined
        dense
        clearable
        placeholder="All Types"
        style="min-width: 130px;"
        @update:model-value="store.fetchKanban()"
      />

      <!-- Category filter -->
      <q-select
        v-model="store.filters.category"
        :options="categoryOptions"
        emit-value
        map-options
        outlined
        dense
        clearable
        placeholder="All Categories"
        style="min-width: 160px;"
        @update:model-value="store.fetchKanban()"
      />

      <!-- Operator filter -->
      <q-select
        v-model="store.filters.assigned_to"
        :options="operatorOptions"
        emit-value
        map-options
        outlined
        dense
        clearable
        placeholder="All Operators"
        style="min-width: 160px;"
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

      <!-- Add partner button -->
      <q-btn
        color="primary"
        icon="add"
        label="Add Partner"
        unelevated
        @click="showAddDialog = true"
        style="border-radius: 8px;"
      />
    </div>

    <!-- Stats row -->
    <div class="row q-gutter-sm q-mb-md" v-if="store.stats">
      <q-chip
        v-for="(stage, key) in stageConfig"
        :key="key"
        :style="`background: ${stage.bgLight}; color: ${stage.color}; border: 1px solid ${stage.color}33;`"
        class="text-weight-medium"
      >
        <q-avatar :color="stage.color" text-color="white" size="20px">
          {{ store.stats.by_stage?.[key] || 0 }}
        </q-avatar>
        {{ stage.label }}
      </q-chip>
      <q-chip icon="currency_rupee" color="positive" text-color="white" class="text-weight-medium">
        {{ formatMoney(store.stats.total_revenue) }} revenue
      </q-chip>
    </div>

    <!-- Kanban board -->
    <div class="kanban-container" v-if="!store.loading">
      <div
        v-for="(stage, key) in stageConfig"
        :key="key"
        class="kanban-column"
      >
        <!-- Column header -->
        <div
          class="q-pa-sm q-mb-sm row items-center justify-between"
          :style="`background: ${stage.bgLight}; border-radius: 10px; border-left: 4px solid ${stage.color};`"
        >
          <div class="row items-center q-gutter-sm">
            <q-icon :name="stage.icon" :color="stage.colorName" size="18px" />
            <span class="text-subtitle2 text-weight-bold" :style="`color: ${stage.color}`">
              {{ stage.label }}
            </span>
          </div>
          <q-badge
            :style="`background: ${stage.color}; color: white;`"
            rounded
          >
            {{ store.kanbanTotals[key] ?? (store.kanbanData[key] || []).length }}
          </q-badge>
        </div>

        <!-- Draggable cards -->
        <draggable
          v-model="store.kanbanData[key]"
          group="partners"
          item-key="id"
          :animation="150"
          ghost-class="drag-ghost"
          chosen-class="drag-chosen"
          @add="(evt) => onDragEnd(evt, key)"
          class="kanban-cards"
          :class="{ 'drag-over': dragOver === key }"
          @dragover="dragOver = key"
          @dragleave="dragOver = null"
        >
          <template #item="{ element }">
            <PartnerCard
              :partner="element"
              :stage-color="stage.color"
              :users="store.users"
              class="q-mb-sm"
              @click="openPartner(element.id)"
              @stage-change="handleStageChange"
              @assign="handleAssign"
            />
          </template>
        </draggable>

        <!-- Show more button -->
        <q-btn
          v-if="store.kanbanHasMore[key]"
          flat dense no-caps
          color="grey-7"
          class="full-width q-mt-xs"
          style="border-radius:8px; font-size:12px;"
          :loading="loadingMore[key]"
          @click="loadMore(key)"
        >
          <q-icon name="expand_more" size="16px" class="q-mr-xs" />
          Show more ({{ (store.kanbanData[key] || []).length }} of {{ store.kanbanTotals[key] || 0 }})
        </q-btn>
      </div>
    </div>

    <!-- Loading state -->
    <div v-else class="row justify-center q-mt-xl">
      <q-spinner-dots color="primary" size="48px" />
    </div>

    <!-- Add Partner Dialog -->
    <AddPartnerDialog
      v-model="showAddDialog"
      :users="store.users"
      @created="onPartnerCreated"
    />
  </q-page>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import draggable from 'vuedraggable'
import { useAuthStore } from 'src/stores/auth'
import { usePartnersStore } from 'src/stores/partners'
import PartnerCard from 'src/components/PartnerCard.vue'
import AddPartnerDialog from 'src/components/AddPartnerDialog.vue'

const $q = useQuasar()
const router = useRouter()
const authStore = useAuthStore()
const store = usePartnersStore()

const onlyMine = ref(false)
function toggleMine() {
  onlyMine.value = !onlyMine.value
  store.filters.assigned_to = onlyMine.value ? authStore.user?.id : null
  store.fetchKanban()
}

const showAddDialog = ref(false)
const dragOver = ref(null)
const loadingMore = ref({})

const loadMore = async (stageKey) => {
  loadingMore.value[stageKey] = true
  try {
    await store.fetchKanbanMore(stageKey)
  } finally {
    loadingMore.value[stageKey] = false
  }
}

const stageConfig = {
  new: {
    label: 'New',
    color: '#F44336',
    colorName: 'red',
    bgLight: '#FFEBEE',
    icon: 'fiber_new',
  },
  trained: {
    label: 'Agreed to Create First Set',
    color: '#FFB300',
    colorName: 'amber',
    bgLight: '#FFF8E1',
    icon: 'school',
  },
  set_created: {
    label: 'Set Created',
    color: '#0277BD',
    colorName: 'light-blue',
    bgLight: '#E1F5FE',
    icon: 'medical_services',
  },
  has_sale: {
    label: 'Has Sale',
    color: '#2E7D32',
    colorName: 'green',
    bgLight: '#E8F5E9',
    icon: 'paid',
  },
  no_answer: {
    label: 'Dead (No Answer)',
    color: '#546E7A',
    colorName: 'blue-grey',
    bgLight: '#ECEFF1',
    icon: 'phone_missed',
  },
  declined: {
    label: 'Dead (Declined)',
    color: '#B71C1C',
    colorName: 'red-10',
    bgLight: '#FFEBEE',
    icon: 'cancel',
  },
  no_sales: {
    label: 'Dead (No Sales)',
    color: '#E65100',
    colorName: 'deep-orange',
    bgLight: '#FBE9E7',
    icon: 'trending_down',
  },
}

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

const operatorOptions = computed(() =>
  store.users.map(u => ({ label: u.full_name || u.username, value: u.id }))
)

const formatMoney = (val) => {
  if (!val) return '0'
  return Number(val).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

const openPartner = (id) => {
  router.push(`/partners/${id}`)
}

const handleAssign = async ({ partnerId, userId, userDetail }) => {
  try {
    await store.updatePartner(partnerId, { assigned_to: userId })
    // Update locally so card refreshes without full reload
    for (const stageKey of Object.keys(store.kanbanData)) {
      const idx = store.kanbanData[stageKey].findIndex(p => p.id === partnerId)
      if (idx !== -1) {
        store.kanbanData[stageKey][idx] = {
          ...store.kanbanData[stageKey][idx],
          assigned_to: userId,
          assigned_to_detail: userDetail,
        }
        break
      }
    }
    $q.notify({ type: 'positive', message: `Assigned to ${userDetail.full_name || userDetail.username}`, timeout: 1500 })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to assign operator' })
  }
}

const handleStageChange = async ({ partnerId, newStage }) => {
  try {
    await store.updateStage(partnerId, newStage)
    $q.notify({ type: 'positive', message: 'Stage updated' })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to update stage' })
    store.fetchKanban()
  }
}

const onDragEnd = async (evt, toStage) => {
  dragOver.value = null

  const movedElement = store.kanbanData[toStage][evt.newIndex]
  if (!movedElement) return

  try {
    await store.updateStage(movedElement.id, toStage)
    $q.notify({ type: 'positive', message: `Moved to "${stageConfig[toStage].label}"`, timeout: 1500 })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to update stage' })
    store.fetchKanban()
  }
}

const onPartnerCreated = () => {
  showAddDialog.value = false
  store.fetchKanban()
  store.fetchStats()
  $q.notify({ type: 'positive', message: 'Partner added successfully' })
}

onMounted(() => {
  store.fetchKanban()
})
</script>

<style scoped>
.drag-ghost {
  opacity: 0.4;
}
.drag-chosen {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2) !important;
}
</style>
