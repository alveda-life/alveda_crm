<template>
  <q-page class="q-pa-md" style="max-width:820px;">

    <div class="text-h6 text-weight-bold q-mb-lg">AI Evaluation Settings</div>

    <q-card flat bordered style="border-radius:12px;" class="q-mb-md">
      <q-card-section>
        <div class="section-title q-mb-xs">
          <q-icon name="info" color="blue-7" size="18px" />
          Product Information
        </div>
        <div class="text-caption text-grey-6 q-mb-sm">
          Describe the product in detail — goals, benefits, target audience, pricing, sets, etc.
          Claude uses this when scoring how well the operator explained it.
        </div>
        <q-input
          v-model="form.product_info"
          type="textarea"
          outlined
          :rows="8"
          autogrow
          placeholder="Enter full product description here…"
        />
      </q-card-section>
    </q-card>

    <q-card flat bordered style="border-radius:12px;" class="q-mb-md">
      <q-card-section>
        <div class="section-title q-mb-xs">
          <q-icon name="record_voice_over" color="orange-7" size="18px" />
          Evaluation Prompt
          <q-chip dense size="sm" color="grey-2" text-color="grey-7" class="q-ml-sm" style="font-size:10px;">
            Leave blank to use default
          </q-chip>
        </div>
        <div class="text-caption text-grey-6 q-mb-sm">
          A single set of instructions the AI uses to score every call. The AI will produce
          three numeric scores from these criteria — survey/discovery, product explanation
          and overall — but you describe what matters in <b>one</b> place.
        </div>
        <div class="text-caption text-grey-6 q-mb-md">
          Tip: list what a good call looks like, what mistakes lose points, and any
          must-ask questions or facts. Use the language you want the AI to think in
          (English works best).
        </div>

        <q-input
          v-model="form.evaluation_prompt"
          type="textarea"
          outlined
          :rows="12"
          autogrow
          placeholder="e.g. A good call: operator greets the partner by name, asks when they last created a Medical Set, explains the 30% commission as something the partner EARNS (never PAYS)…"
        />
      </q-card-section>
    </q-card>

    <div class="row items-center q-gutter-sm">
      <q-btn
        unelevated color="green-8" icon="save" label="Save Settings"
        style="border-radius:8px;"
        :loading="saving"
        @click="save"
      />
      <div v-if="savedAt" class="text-caption text-grey-5">
        <q-icon name="check_circle" color="green-5" size="14px" />
        Saved {{ savedAt }}
      </div>
    </div>

  </q-page>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { api } from 'boot/axios'

const $q    = useQuasar()
const saving = ref(false)
const savedAt = ref('')

const form = ref({
  product_info:      '',
  evaluation_prompt: '',
})

async function load() {
  try {
    const res = await api.get('/crm-settings/')
    Object.assign(form.value, res.data)
  } catch {}
}

async function save() {
  saving.value = true
  try {
    const res = await api.patch('/crm-settings/', form.value)
    Object.assign(form.value, res.data)
    savedAt.value = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
    $q.notify({ type: 'positive', message: 'Settings saved', timeout: 1500 })
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Error saving settings' })
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.section-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 14px; font-weight: 700; color: #212121; margin-bottom: 4px;
}
.field-label { font-size: 12px; font-weight: 600; color: #616161; }
</style>
