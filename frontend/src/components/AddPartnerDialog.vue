<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" persistent>
    <q-card style="min-width: 520px; max-width: 600px; border-radius: 16px;">
      <q-card-section class="row items-center q-pb-none">
        <q-icon name="person_add" color="primary" size="24px" class="q-mr-sm" />
        <div class="text-h6 text-weight-bold">{{ isEdit ? 'Edit Partner' : 'Add New Partner' }}</div>
        <q-space />
        <q-btn icon="close" flat round dense @click="$emit('update:modelValue', false)" />
      </q-card-section>

      <q-card-section>
        <q-form @submit.prevent="save" ref="formRef">
          <div class="row q-gutter-md">

            <!-- Name -->
            <div class="col-12">
              <div class="field-label q-mb-xs">Full Name *</div>
              <q-input
                v-model="form.name"
                outlined dense
                placeholder="e.g. Dr. Priya Sharma"
                :rules="[v => !!v || 'Name is required']"
              />
            </div>

            <!-- Phone -->
            <div class="col">
              <div class="field-label q-mb-xs">Phone</div>
              <q-input v-model="form.phone" outlined dense placeholder="+7 999 000-00-00" />
            </div>

            <!-- Platform User ID -->
            <div class="col">
              <div class="field-label q-mb-xs">Platform User ID</div>
              <q-input v-model="form.user_id" outlined dense placeholder="USR1234" />
            </div>

            <!-- Type -->
            <div class="col-12">
              <div class="row q-gutter-md">
                <div class="col">
                  <div class="field-label q-mb-xs">Type *</div>
                  <q-select
                    v-model="form.type"
                    :options="typeOptions"
                    emit-value map-options
                    outlined dense
                    :rules="[v => !!v || 'Required']"
                  />
                </div>
                <div v-if="form.type === 'partner'" class="col">
                  <div class="field-label q-mb-xs">Category *</div>
                  <q-select
                    v-model="form.category"
                    :options="categoryOptions"
                    emit-value map-options
                    outlined dense
                    :rules="[v => !!v || 'Required']"
                  />
                </div>
              </div>
            </div>

            <!-- Stage + Status -->
            <div class="col-12">
              <div class="row q-gutter-md">
                <div class="col">
                  <div class="field-label q-mb-xs">Funnel Stage</div>
                  <q-select
                    v-model="form.stage"
                    :options="stageOptions"
                    emit-value map-options
                    outlined dense
                  />
                </div>
                <div class="col">
                  <div class="field-label q-mb-xs">Status</div>
                  <q-select
                    v-model="form.status"
                    :options="statusOptions"
                    emit-value map-options
                    outlined dense
                  />
                </div>
              </div>
            </div>

            <!-- Control date + Operator -->
            <div class="col-12">
              <div class="row q-gutter-md">
                <div class="col">
                  <div class="field-label q-mb-xs">Follow-up Date *</div>
                  <q-input
                    v-model="form.control_date"
                    outlined dense type="date"
                    :max="maxControlDate"
                    :rules="[
                      v => !!v || 'Date is required',
                      v => v <= maxControlDate || 'Max 14 days ahead'
                    ]"
                  />
                </div>
                <div class="col">
                  <div class="field-label q-mb-xs">Operator</div>
                  <q-select
                    v-model="form.assigned_to"
                    :options="userOptions"
                    emit-value map-options
                    outlined dense clearable
                    placeholder="Unassigned"
                  />
                </div>
              </div>
            </div>

            <!-- Gender + Experience -->
            <div class="col-12">
              <div class="row q-gutter-md">
                <div class="col">
                  <div class="field-label q-mb-xs">Gender</div>
                  <q-select
                    v-model="form.gender"
                    :options="genderOptions"
                    emit-value map-options
                    outlined dense clearable
                    placeholder="Not specified"
                  />
                </div>
                <div class="col">
                  <div class="field-label q-mb-xs">Experience (years)</div>
                  <q-input v-model.number="form.experience_years" outlined dense type="number" min="0" max="60" placeholder="e.g. 5" />
                </div>
              </div>
            </div>

            <!-- State + City -->
            <div class="col-12">
              <div class="row q-gutter-md">
                <div class="col">
                  <div class="field-label q-mb-xs">State</div>
                  <q-select
                    v-model="form.state"
                    :options="stateOptions"
                    use-input input-debounce="0"
                    @filter="filterStates"
                    outlined dense clearable
                    placeholder="Search state..."
                    @update:model-value="form.city = ''"
                  />
                </div>
                <div class="col">
                  <div class="field-label q-mb-xs">City</div>
                  <q-select
                    v-model="form.city"
                    :options="cityOptions"
                    use-input input-debounce="0"
                    @filter="filterCities"
                    outlined dense clearable
                    placeholder="Search city..."
                  />
                </div>
              </div>
            </div>

            <!-- Referred by -->
            <div class="col-12">
              <div class="field-label q-mb-xs">Referred By</div>
              <q-input v-model="form.referred_by" outlined dense placeholder="Username or ID" />
            </div>

            <!-- Notes -->
            <div class="col-12">
              <div class="field-label q-mb-xs">Notes</div>
              <q-input
                v-model="form.notes"
                type="textarea"
                outlined dense
                rows="2"
                placeholder="Internal notes..."
                autogrow
              />
            </div>
          </div>
        </q-form>
      </q-card-section>

      <q-card-actions align="right" class="q-pa-md q-pt-none">
        <q-btn flat label="Cancel" color="grey-7" @click="$emit('update:modelValue', false)" />
        <q-btn
          unelevated color="primary"
          :label="isEdit ? 'Save Changes' : 'Add Partner'"
          :loading="saving"
          @click="save"
          style="border-radius: 8px; min-width: 140px;"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { usePartnersStore } from 'src/stores/partners'
import { INDIA_STATES, INDIA_CITIES_WITH_OTHER, ALL_INDIA_CITIES } from 'src/data/india-locations'

const props = defineProps({
  modelValue: Boolean,
  partner: { type: Object, default: null },
  users: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'created'])

const store = usePartnersStore()
const formRef = ref(null)
const saving = ref(false)

const isEdit = computed(() => !!props.partner)

const todayIso = () => new Date().toISOString().slice(0, 10)
const maxControlDate = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() + 14)
  return d.toISOString().slice(0, 10)
})

const defaultForm = () => ({
  name: '',
  phone: '',
  user_id: '',
  type: 'partner',
  category: 'other',
  gender: '',
  experience_years: null,
  state: '',
  city: '',
  stage: 'new',
  status: 'new',
  control_date: todayIso(),
  referred_by: '',
  assigned_to: null,
  notes: '',
})

const form = ref(defaultForm())

watch(() => props.partner, (p) => {
  if (p) {
    form.value = {
      name: p.name,
      phone: p.phone,
      user_id: p.user_id,
      type: p.type,
      category: p.category,
      gender: p.gender || '',
      experience_years: p.experience_years ?? null,
      state: p.state || '',
      city: p.city || '',
      stage: p.stage,
      status: p.status || 'new',
      control_date: p.control_date || todayIso(),
      referred_by: p.referred_by,
      assigned_to: p.assigned_to,
      notes: p.notes,
    }
  } else {
    form.value = defaultForm()
  }
}, { immediate: true })

watch(() => props.modelValue, (val) => {
  if (!val && !props.partner) form.value = defaultForm()
})

watch(() => form.value.type, (newType) => {
  if (newType === 'medic') form.value.category = ''
})

const genderOptions = [
  { label: 'Male', value: 'male' },
  { label: 'Female', value: 'female' },
]

const stateOptions = ref(INDIA_STATES)
const cityOptions = ref(ALL_INDIA_CITIES)

const filterStates = (val, update) => {
  update(() => {
    const q = val.toLowerCase()
    stateOptions.value = q ? INDIA_STATES.filter(s => s.toLowerCase().includes(q)) : INDIA_STATES
  })
}

const filterCities = (val, update) => {
  update(() => {
    const base = form.value.state && INDIA_CITIES_WITH_OTHER[form.value.state]
      ? INDIA_CITIES_WITH_OTHER[form.value.state]
      : ALL_INDIA_CITIES
    const q = val.toLowerCase()
    cityOptions.value = q ? base.filter(c => c.toLowerCase().includes(q)) : base
  })
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

const statusOptions = [
  { label: 'New', value: 'new' },
  { label: 'In Support', value: 'in_support' },
  { label: 'Closed', value: 'closed' },
]

const stageOptions = [
  { label: 'New', value: 'new' },
  { label: 'Agreed to Create First Set', value: 'trained' },
  { label: 'Medical Set Created', value: 'set_created' },
  { label: 'Has Sale', value: 'has_sale' },
]

const userOptions = computed(() =>
  props.users.map(u => ({ label: u.full_name || u.username, value: u.id }))
)

const save = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return

  saving.value = true
  try {
    if (isEdit.value) {
      await store.updatePartner(props.partner.id, form.value)
    } else {
      await store.createPartner(form.value)
    }
    emit('created')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.field-label {
  font-size: 12px;
  font-weight: 600;
  color: #757575;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>
