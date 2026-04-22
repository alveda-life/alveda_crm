<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" persistent>
    <q-card style="min-width:480px;max-width:580px;border-radius:16px;max-height:92vh;display:flex;flex-direction:column;">
      <q-card-section class="row items-center q-pb-none flex-shrink-0">
        <q-icon name="factory" color="primary" size="24px" class="q-mr-sm" />
        <div class="text-h6 text-weight-bold">{{ isEdit ? 'Edit Producer' : 'Add Producer' }}</div>
        <q-space />
        <q-btn icon="close" flat round dense @click="$emit('update:modelValue', false)" />
      </q-card-section>

      <q-card-section style="flex:1 1 auto;min-height:0;overflow-y:auto;">
        <q-form @submit.prevent="save" ref="formRef">
            <div class="row q-col-gutter-md">

              <!-- Name -->
              <div class="col-12">
                <div class="field-label q-mb-xs">Contact Name *</div>
                <q-input v-model="form.name" outlined dense placeholder="e.g. Rajiv Mehta"
                  :rules="[v => !!v || 'Name is required']" />
              </div>

              <!-- Company -->
              <div class="col-12">
                <div class="field-label q-mb-xs">Company / Brand</div>
                <q-input v-model="form.company" outlined dense placeholder="e.g. Himalaya Herbs Pvt Ltd" />
              </div>

              <!-- Phone + Email -->
              <div class="col-6">
                <div class="field-label q-mb-xs">Phone</div>
                <q-input v-model="form.phone" outlined dense placeholder="+91 98765 43210" />
              </div>
              <div class="col-6">
                <div class="field-label q-mb-xs">Email</div>
                <q-input v-model="form.email" outlined dense type="email" placeholder="info@example.com" />
              </div>

              <!-- Website -->
              <div class="col-12">
                <div class="field-label q-mb-xs">Website</div>
                <q-input v-model="form.website" outlined dense placeholder="https://example.com" />
              </div>

              <!-- City + Country -->
              <div class="col-6">
                <div class="field-label q-mb-xs">City</div>
                <q-input v-model="form.city" outlined dense placeholder="Mumbai" />
              </div>
              <div class="col-6">
                <div class="field-label q-mb-xs">Country</div>
                <q-input v-model="form.country" outlined dense placeholder="India" />
              </div>

              <!-- Product Categories (multi-select) -->
              <div class="col-12">
                <div class="field-label q-mb-xs">Product Categories</div>
                <q-select
                  v-model="form.product_type_arr"
                  :options="productTypeOptions"
                  outlined dense multiple
                  use-chips use-input input-debounce="0"
                  new-value-mode="add-unique"
                  placeholder="Select or type categories…"
                />
              </div>

              <!-- Funnel + Stage -->
              <div class="col-6">
                <div class="field-label q-mb-xs">Funnel</div>
                <q-select
                  v-model="form.funnel"
                  :options="funnelOptions" emit-value map-options
                  outlined dense
                  @update:model-value="form.stage = defaultStage(form.funnel)"
                />
              </div>
              <div class="col-6">
                <div class="field-label q-mb-xs">Stage</div>
                <q-select
                  v-model="form.stage"
                  :options="stageOptions" emit-value map-options
                  outlined dense
                />
              </div>

              <!-- Operator -->
              <div class="col-12">
                <div class="field-label q-mb-xs">Assign To</div>
                <q-select
                  v-model="form.assigned_to"
                  :options="userOptions" emit-value map-options
                  outlined dense clearable
                  placeholder="Unassigned"
                />
              </div>

              <!-- Notes -->
              <div class="col-12">
                <div class="field-label q-mb-xs">Notes</div>
                <q-input v-model="form.notes" outlined dense type="textarea" rows="2" placeholder="Optional notes" />
              </div>

              <!-- Pharma Details divider -->
              <div class="col-12">
                <q-separator class="q-mt-xs q-mb-sm" />
                <div style="font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#9E9E9E;">
                  Pharma Details
                </div>
              </div>

              <!-- Priority + Cooperation Potential -->
              <div class="col-6">
                <div class="field-label q-mb-xs">Priority</div>
                <q-select v-model="form.priority" :options="priorityOptions" emit-value map-options outlined dense />
              </div>
              <div class="col-6">
                <div class="field-label q-mb-xs">Coop. Potential</div>
                <q-select v-model="form.cooperation_potential" :options="coopOptions" emit-value map-options outlined dense />
              </div>

              <!-- Product Count + Control Date -->
              <div class="col-6">
                <div class="field-label q-mb-xs">Product Count (SKUs)</div>
                <q-input v-model.number="form.product_count" outlined dense type="number" min="0" placeholder="0" />
              </div>
              <div class="col-6">
                <div class="field-label q-mb-xs">Next Follow-up Date</div>
                <q-input v-model="form.control_date" outlined dense type="date" />
              </div>

              <!-- Next Step (single select + allow new) -->
              <div class="col-12">
                <div class="field-label q-mb-xs">Next Step</div>
                <q-select
                  v-model="form.next_step"
                  :options="nextStepOptions"
                  outlined dense
                  use-input input-debounce="0"
                  new-value-mode="add"
                  clearable
                  placeholder="Select or type…"
                />
              </div>

              <!-- Certifications (multi-select with chips) -->
              <div class="col-12">
                <div class="field-label q-mb-xs">Certifications</div>
                <q-select
                  v-model="form.certifications_arr"
                  :options="certOptions"
                  outlined dense multiple
                  use-chips use-input input-debounce="0"
                  new-value-mode="add-unique"
                  placeholder="GMP, ISO, FSSAI…"
                />
              </div>

              <!-- Communication Status (multi-select with chips) -->
              <div class="col-12">
                <div class="field-label q-mb-xs">Communication Status</div>
                <q-select
                  v-model="form.communication_status_arr"
                  :options="commStatusOptions"
                  outlined dense multiple
                  use-chips use-input input-debounce="0"
                  new-value-mode="add-unique"
                  placeholder="Not Contacted, Email Sent…"
                />
              </div>

              <!-- Contact Info -->
              <div class="col-12">
                <div class="field-label q-mb-xs">Key Contacts</div>
                <q-input v-model="form.contact_info" outlined dense type="textarea" rows="2"
                  placeholder="Names, emails, phones of key contacts" />
              </div>
            </div>

            <div class="row q-gutter-sm q-mt-md">
              <q-btn unelevated color="primary" type="submit" :loading="saving"
                :label="isEdit ? 'Save Changes' : 'Add Producer'"
                style="border-radius:8px;" />
              <q-btn flat color="grey-7" label="Cancel" @click="$emit('update:modelValue', false)" />
            </div>
        </q-form>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useProducersStore } from 'src/stores/producers'

const props = defineProps({
  modelValue:  { type: Boolean, default: false },
  users:       { type: Array, default: () => [] },
  activeFunnel:{ type: String, default: 'onboarding' },
  producer:    { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'created', 'updated'])

const store   = useProducersStore()
const formRef = ref(null)
const saving  = ref(false)
const isEdit  = computed(() => !!props.producer)

const defaultStage = (funnel) => funnel === 'onboarding' ? 'interest' : 'agreed'

// ── Option lists ──────────────────────────────────────────────────────────────
const productTypeOptions = [
  'Ayurvedic', 'Ayurvedic Classics', 'Baby Care', 'Beauty & Personal Care',
  'Contract Manufacturing', 'Dental Care', 'Digestive', 'Hair Care',
  'Herbal', 'Herbal Pharmaceuticals', 'Herbal Pain Patches',
  'OTC Remedies', 'Other', 'Pharmaceutical', 'Skin Care',
  'Supplements', 'Unani', 'Wellness', "Women's Health",
]

const certOptions = ['GMP', 'ISO', 'FSSAI', 'AYUSH License', 'FDA']

const commStatusOptions = [
  'Not Contacted', 'Email Sent', 'WhatsApp Message Sent',
  'LinkedIn Request Sent', 'LinkedIn Message Sent',
  'Call Scheduled', 'Waiting for Reply',
  'Follow-Up Needed', 'Negotiation status',
]

const nextStepOptions = [
  'Agreement draft', 'Completed', 'Follow-up required',
  'Internal review', 'Negotiation stage', 'On hold',
  'Preparing for meeting', 'Waiting for call time',
  'Waiting for documents', 'Waiting for their reply',
]

const priorityOptions = [
  { label: 'High',   value: 'high' },
  { label: 'Medium', value: 'medium' },
  { label: 'Low',    value: 'low' },
]
const coopOptions = [
  { label: 'Strong',          value: 'strong' },
  { label: 'Medium',          value: 'medium' },
  { label: 'Weak',            value: 'weak' },
  { label: 'No Response Yet', value: 'no_response' },
]

// ── Helpers: string ↔ array ───────────────────────────────────────────────────
const toArr = (str) => (str || '').split(',').map(s => s.trim()).filter(Boolean)

const emptyForm = () => ({
  name:                       '',
  company:                    '',
  phone:                      '',
  email:                      '',
  website:                    '',
  city:                       '',
  country:                    '',
  product_type_arr:           [],
  notes:                      '',
  funnel:                     props.activeFunnel,
  stage:                      defaultStage(props.activeFunnel),
  assigned_to:                null,
  priority:                   'medium',
  product_count:              null,
  cooperation_potential:      'medium',
  certifications_arr:         [],
  communication_status_arr:   [],
  next_step:                  '',
  contact_info:               '',
  control_date:               null,
})

const form = ref(emptyForm())

watch(() => props.modelValue, (v) => {
  if (v) {
    if (props.producer) {
      const p = props.producer
      form.value = {
        ...emptyForm(),
        ...p,
        product_type_arr:         toArr(p.product_type),
        certifications_arr:       toArr(p.certifications),
        communication_status_arr: toArr(p.communication_status),
        next_step:                p.next_step || '',
      }
    } else {
      form.value = emptyForm()
    }
  }
})

// ── Funnel / Stage options ────────────────────────────────────────────────────
const funnelOptions = [
  { label: 'Onboarding', value: 'onboarding' },
  { label: 'Support',    value: 'support' },
]
const onboardingStageOptions = [
  { label: 'Interest',         value: 'interest' },
  { label: 'In Communication', value: 'in_communication' },
  { label: 'Negotiation',      value: 'terms_negotiation' },
  { label: 'Signing Contract', value: 'negotiation' },
  { label: 'Contract Signed',  value: 'contract_signed' },
  { label: 'On the Platform',  value: 'on_platform' },
  { label: 'Stopped',          value: 'stopped' },
]
const supportStageOptions = [
  { label: 'Agreed',            value: 'agreed' },
  { label: 'Signed',            value: 'signed' },
  { label: 'Products Received', value: 'products_received' },
  { label: 'Ready to Sell',     value: 'ready_to_sell' },
  { label: 'In Store',          value: 'in_store' },
]
const stageOptions = computed(() =>
  form.value.funnel === 'onboarding' ? onboardingStageOptions : supportStageOptions
)
const userOptions = computed(() =>
  props.users.map(u => ({ label: u.full_name || u.username, value: u.id }))
)

// ── Save ──────────────────────────────────────────────────────────────────────
const save = async () => {
  const ok = await formRef.value?.validate()
  if (!ok) return
  saving.value = true
  try {
    // Convert arrays back to comma-separated strings
    const payload = {
      ...form.value,
      product_type:         form.value.product_type_arr.join(', '),
      certifications:       form.value.certifications_arr.join(', '),
      communication_status: form.value.communication_status_arr.join(', '),
    }
    delete payload.product_type_arr
    delete payload.certifications_arr
    delete payload.communication_status_arr

    if (isEdit.value) {
      await store.updateProducer(props.producer.id, payload)
      emit('updated')
    } else {
      await store.createProducer(payload)
      emit('created')
    }
    emit('update:modelValue', false)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.field-label { font-size: 12px; font-weight: 600; color: #616161; }
</style>
