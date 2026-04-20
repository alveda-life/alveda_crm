<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <q-card style="min-width:400px;border-radius:14px;">
      <q-card-section class="row items-center q-pb-none">
        <q-icon name="add_task" color="primary" size="24px" class="q-mr-sm" />
        <div class="text-h6 text-weight-bold">New Task</div>
        <q-space />
        <q-btn icon="close" flat round dense @click="$emit('update:modelValue', false)" />
      </q-card-section>

      <q-card-section>
        <q-form @submit.prevent="submit" ref="formRef">
          <div class="row q-col-gutter-sm">
            <div class="col-12">
              <div class="field-label q-mb-xs">Title *</div>
              <q-input v-model="form.title" outlined dense placeholder="Task title"
                :rules="[v => !!v || 'Required']" />
            </div>
            <div class="col-12">
              <div class="field-label q-mb-xs">Description</div>
              <q-input v-model="form.description" outlined dense type="textarea" rows="2" placeholder="Optional" />
            </div>
            <div class="col-6">
              <div class="field-label q-mb-xs">Priority</div>
              <q-select v-model="form.priority" :options="priorityOptions" emit-value map-options
                outlined dense />
            </div>
            <div class="col-6">
              <div class="field-label q-mb-xs">Due Date</div>
              <q-input v-model="form.due_date" outlined dense type="date" />
            </div>
            <div class="col-12">
              <div class="field-label q-mb-xs">Assign To</div>
              <q-select v-model="form.assigned_to" :options="userOptions" emit-value map-options
                outlined dense clearable placeholder="Unassigned" />
            </div>
          </div>

          <div class="row q-gutter-sm q-mt-md">
            <q-btn unelevated color="primary" type="submit" label="Add Task" style="border-radius:8px;" />
            <q-btn flat color="grey-7" label="Cancel" @click="$emit('update:modelValue', false)" />
          </div>
        </q-form>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  users:      { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'save'])

const formRef = ref(null)
const emptyForm = () => ({ title: '', description: '', priority: 'medium', due_date: '', assigned_to: null })
const form = ref(emptyForm())

watch(() => props.modelValue, (v) => { if (v) form.value = emptyForm() })

const priorityOptions = [
  { label: 'Low',    value: 'low' },
  { label: 'Medium', value: 'medium' },
  { label: 'High',   value: 'high' },
]

const userOptions = computed(() =>
  props.users.map(u => ({ label: u.full_name || u.username, value: u.id }))
)

const submit = async () => {
  const ok = await formRef.value?.validate()
  if (!ok) return
  const data = { ...form.value }
  if (!data.due_date) delete data.due_date
  if (!data.assigned_to) delete data.assigned_to
  emit('save', data)
}
</script>

<style scoped>
.field-label { font-size: 12px; font-weight: 600; color: #616161; }
</style>
