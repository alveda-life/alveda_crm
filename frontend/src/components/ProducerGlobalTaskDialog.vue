<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" persistent>
    <q-card style="min-width:460px;max-width:520px;border-radius:14px;">
      <q-card-section class="row items-center q-pb-none">
        <q-icon name="add_task" color="green-7" size="22px" class="q-mr-sm" />
        <div class="text-h6 text-weight-bold">{{ task ? 'Edit Task' : 'New Producer Task' }}</div>
        <q-space />
        <q-btn flat round icon="close" @click="$emit('update:modelValue', false)" />
      </q-card-section>

      <q-card-section class="q-pt-md">
        <q-form ref="formRef" class="q-gutter-sm">

          <!-- Producer selector (create only) -->
          <div v-if="!task">
            <div class="field-label q-mb-xs">Producer *</div>
            <q-select
              v-model="form.producer"
              :options="producerOptions"
              emit-value map-options use-input input-debounce="0"
              outlined dense clearable
              placeholder="Select producer…"
              :error="!!errors.producer"
              :error-message="errors.producer"
              @filter="filterProducers"
            />
          </div>
          <div v-else class="producer-label">
            <q-icon name="factory" size="14px" color="grey-5" />
            <span>{{ task.producer_name }}</span>
          </div>

          <!-- Title -->
          <div>
            <div class="field-label q-mb-xs">Title *</div>
            <q-input
              v-model="form.title"
              outlined dense
              placeholder="Task title"
              :error="!!errors.title"
              :error-message="errors.title"
              autofocus
            />
          </div>

          <!-- Description -->
          <div>
            <div class="field-label q-mb-xs">Description</div>
            <q-input v-model="form.description" outlined dense type="textarea" rows="2" autogrow placeholder="Optional" />
          </div>

          <div class="row q-gutter-sm">
            <!-- Assign -->
            <div style="flex:1;">
              <div class="field-label q-mb-xs">Assign To</div>
              <q-select
                v-model="form.assigned_to"
                :options="userOptions"
                emit-value map-options
                outlined dense clearable
                placeholder="Unassigned"
              />
            </div>

            <!-- Priority -->
            <div style="min-width:130px;">
              <div class="field-label q-mb-xs">Priority</div>
              <q-select
                v-model="form.priority"
                :options="priorityOptions"
                emit-value map-options
                outlined dense
              />
            </div>
          </div>

          <div class="row q-gutter-sm">
            <!-- Due date -->
            <div style="flex:1;">
              <div class="field-label q-mb-xs">Due Date</div>
              <q-input v-model="form.due_date" outlined dense type="date" clearable />
            </div>

            <!-- Status (edit only) -->
            <div v-if="task" style="flex:1;">
              <div class="field-label q-mb-xs">Status</div>
              <q-select
                v-model="form.status"
                :options="statusOptions"
                emit-value map-options
                outlined dense
              />
            </div>
          </div>

          <!-- Audit trail (edit only) -->
          <div v-if="task" class="audit-block q-mt-sm">
            <div class="audit-row">
              <q-icon name="person_add" size="13px" color="grey-6" />
              <span class="audit-label">Created by</span>
              <span class="audit-value">{{ userName(task.created_by_detail) || '—' }}</span>
              <span class="audit-time">· {{ fmtDatetime(task.created_at) }}</span>
            </div>
            <div v-if="task.completed_at" class="audit-row audit-row--done">
              <q-icon name="check_circle" size="13px" color="green-6" />
              <span class="audit-label">Closed by</span>
              <span class="audit-value">{{ userName(task.completed_by_detail) || '—' }}</span>
              <span class="audit-time">· {{ fmtDatetime(task.completed_at) }}</span>
            </div>
          </div>

        </q-form>
      </q-card-section>

      <q-card-actions align="right" class="q-pa-md q-pt-none">
        <q-btn flat label="Cancel" color="grey-7" @click="$emit('update:modelValue', false)" />
        <q-btn
          unelevated color="green-8" :label="task ? 'Save' : 'Create'"
          style="border-radius:8px;min-width:90px"
          :loading="saving"
          @click="submit"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useProducersStore } from 'src/stores/producers'

const props = defineProps({
  modelValue: Boolean,
  task:       { type: Object, default: null },
  producers:  { type: Array, default: () => [] },
  users:      { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const store   = useProducersStore()
const formRef = ref(null)
const saving  = ref(false)
const errors  = ref({})

const producerFilterText = ref('')
const producerOptions = computed(() => {
  const q = producerFilterText.value.toLowerCase()
  return props.producers
    .filter(p => !q || (p.name + ' ' + (p.company || '')).toLowerCase().includes(q))
    .map(p => ({ label: p.company ? `${p.name} — ${p.company}` : p.name, value: p.id }))
})

function filterProducers(val, update) {
  producerFilterText.value = val
  update()
}

const blank = () => ({
  producer:    null,
  title:       '',
  description: '',
  assigned_to: null,
  priority:    'medium',
  status:      'open',
  due_date:    '',
})

const form = ref(blank())

watch(() => props.modelValue, (open) => {
  if (open) {
    errors.value = {}
    if (props.task) {
      form.value = {
        producer:    props.task.producer,
        title:       props.task.title,
        description: props.task.description,
        assigned_to: props.task.assigned_to,
        priority:    props.task.priority,
        status:      props.task.status,
        due_date:    props.task.due_date || '',
      }
    } else {
      form.value = blank()
    }
  }
})

const userOptions = computed(() =>
  props.users.map(u => ({ label: u.full_name || u.username, value: u.id }))
)

const priorityOptions = [
  { label: 'Low',    value: 'low' },
  { label: 'Medium', value: 'medium' },
  { label: 'High',   value: 'high' },
]
const statusOptions = [
  { label: 'Open',        value: 'open' },
  { label: 'In Progress', value: 'in_progress' },
  { label: 'Done',        value: 'done' },
  { label: 'Cancelled',   value: 'cancelled' },
]

function userName (detail) {
  if (!detail) return ''
  return detail.full_name || detail.username || ''
}
function fmtDatetime (iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('en-US', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

async function submit() {
  errors.value = {}
  if (!props.task && !form.value.producer) {
    errors.value.producer = 'Producer is required'
    return
  }
  if (!form.value.title.trim()) {
    errors.value.title = 'Title is required'
    return
  }
  saving.value = true
  try {
    const payload = {
      title:       form.value.title.trim(),
      description: form.value.description,
      assigned_to: form.value.assigned_to || null,
      priority:    form.value.priority,
      status:      form.value.status,
      due_date:    form.value.due_date || null,
    }
    if (!props.task) payload.producer = form.value.producer

    const saved = props.task
      ? await store.updateProducerTask(props.task.id, payload)
      : await store.createProducerTask(payload)

    await store.refreshOpenTasksCount()
    emit('saved', saved)
    emit('update:modelValue', false)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.field-label { font-size: 12px; font-weight: 600; color: #616161; }
.producer-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #424242; padding: 4px 0;
}

.audit-block {
  background: #FAFAFA;
  border: 1px solid #ECEFF1;
  border-radius: 8px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.audit-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #424242;
  flex-wrap: wrap;
}
.audit-row--done { color: #2E7D32; }
.audit-label { color: #9E9E9E; min-width: 75px; }
.audit-value { font-weight: 600; color: #212121; }
.audit-row--done .audit-value { color: #1B5E20; }
.audit-time { color: #9E9E9E; font-size: 11px; }
</style>
