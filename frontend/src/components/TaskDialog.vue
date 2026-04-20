<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" persistent>
    <q-card style="min-width:440px;border-radius:14px;">
      <q-card-section class="row items-center q-pb-none">
        <div class="text-h6 text-weight-bold">{{ task ? 'Edit Task' : 'New Task' }}</div>
        <q-space />
        <q-btn flat round icon="close" @click="$emit('update:modelValue', false)" />
      </q-card-section>

      <q-card-section class="q-pt-md q-gutter-sm">
        <!-- Title -->
        <q-input
          v-model="form.title"
          outlined dense
          label="Title *"
          :error="!!errors.title"
          :error-message="errors.title"
          autofocus
        />

        <!-- Description -->
        <q-input
          v-model="form.description"
          outlined dense
          type="textarea"
          label="Description / What to do"
          rows="3"
          autogrow
        />

        <div class="row q-gutter-sm">
          <!-- Assigned to -->
          <q-select
            v-model="form.assigned_to"
            :options="userOptions"
            emit-value map-options
            outlined dense clearable
            label="Assign to"
            style="flex:1"
          />

          <!-- Priority -->
          <q-select
            v-model="form.priority"
            :options="priorityOptions"
            emit-value map-options
            outlined dense
            label="Priority"
            style="min-width:130px"
          >
            <template #selected-item="scope">
              <div class="row items-center q-gutter-xs">
                <q-icon :name="priorityIcon(scope.opt.value)" :color="priorityColor(scope.opt.value)" size="14px" />
                <span>{{ scope.opt.label }}</span>
              </div>
            </template>
          </q-select>
        </div>

        <div class="row q-gutter-sm">
          <!-- Due date -->
          <q-input
            v-model="form.due_date"
            outlined dense
            type="date"
            label="Due date"
            style="flex:1"
            clearable
          />

          <!-- Status (edit only) -->
          <q-select
            v-if="task"
            v-model="form.status"
            :options="statusOptions"
            emit-value map-options
            outlined dense
            label="Status"
            style="flex:1"
          />
        </div>
      </q-card-section>

      <q-card-actions align="right" class="q-pa-md q-pt-none">
        <q-btn flat label="Cancel" color="grey-7" @click="$emit('update:modelValue', false)" />
        <q-btn
          unelevated color="primary" :label="task ? 'Save' : 'Create'"
          style="border-radius:8px;min-width:90px"
          :loading="saving"
          @click="submit"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useTasksStore } from 'src/stores/tasks'
import { usePartnersStore } from 'src/stores/partners'

const props = defineProps({
  modelValue: Boolean,
  task:       { type: Object, default: null },
  partnerId:  { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const tasksStore  = useTasksStore()
const partnersStore = usePartnersStore()

const saving = ref(false)
const errors = ref({})

const blank = () => ({
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
  (partnersStore.users || []).map(u => ({
    label: `${u.first_name} ${u.last_name}`.trim() || u.username,
    value: u.id,
  }))
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

function priorityIcon(p)  { return { low: 'arrow_downward', medium: 'remove', high: 'arrow_upward' }[p] || 'remove' }
function priorityColor(p) { return { low: 'grey-5', medium: 'orange', high: 'red' }[p] || 'grey' }

async function submit() {
  errors.value = {}
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
    if (!props.task && props.partnerId) {
      payload.partner = props.partnerId
    }
    const saved = props.task
      ? await tasksStore.updateTask(props.task.id, payload)
      : await tasksStore.createTask(payload)

    await tasksStore.refreshOpenCount()
    emit('saved', saved)
    emit('update:modelValue', false)
  } finally {
    saving.value = false
  }
}
</script>
