<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" persistent>
    <q-card style="min-width: 500px; max-width: 600px; border-radius: 16px;">
      <q-card-section class="row items-center q-pb-none">
        <q-icon name="add_comment" color="primary" size="24px" class="q-mr-sm" />
        <div class="text-h6 text-weight-bold">{{ contact ? 'Edit Record' : 'New Record' }}</div>
        <q-space />
        <q-btn icon="close" flat round dense @click="close" />
      </q-card-section>

      <q-card-section class="q-pt-md">

        <!-- Missed call / callback checkboxes -->
        <div class="row q-gutter-md q-mb-sm">
          <q-checkbox
            v-model="form.is_missed_call"
            label="No Answer"
            color="negative"
            @update:model-value="onMissedCallChange"
          />
          <q-checkbox
            v-model="form.callback_later"
            label="Call Back Later"
            color="warning"
            @update:model-value="onCallbackChange"
          />
        </div>

        <!-- Call Back Later date picker -->
        <div v-if="form.callback_later" class="q-mb-md">
          <div class="field-label q-mb-xs">
            <q-icon name="event" size="13px" /> Call Back Date — will update control date
          </div>
          <q-input
            v-model="form.callback_date"
            outlined dense
            type="date"
            :min="todayStr"
            :max="maxDateStr"
            style="max-width: 220px;"
          >
            <template #append>
              <q-icon name="event" class="cursor-pointer">
                <q-popup-proxy cover transition-show="scale" transition-hide="scale">
                  <q-date
                    v-model="form.callback_date"
                    mask="YYYY-MM-DD"
                    :options="dateOptions"
                    today-btn
                  />
                </q-popup-proxy>
              </q-icon>
            </template>
          </q-input>
        </div>

        <!-- Banner when not a real call -->
        <div v-if="form.is_missed_call || form.callback_later"
          class="q-mb-md q-pa-sm row items-center q-gutter-xs"
          style="background:#FFF3E0; border-radius:8px; border-left:3px solid #FF6F00;">
          <q-icon name="info_outline" color="warning" size="16px" />
          <span class="text-caption" style="color:#E65100;">
            <template v-if="form.is_missed_call">This record will not count as a call — it will be tracked as a missed call.</template>
            <template v-else-if="form.callback_date">This record will not count as a call. Control date will be set to {{ formatDate(form.callback_date) }}.</template>
            <template v-else>This record will not count as a call.</template>
          </span>
        </div>

        <!-- Operator comment -->
        <div class="field-label q-mb-xs">Comment</div>
        <q-input
          v-model="form.notes"
          type="textarea"
          outlined dense
          rows="3"
          placeholder="Write about the call, agreements, observations..."
          autogrow
          class="q-mb-md"
          autofocus
        />

        <!-- Audio -->
        <div class="field-label q-mb-xs">Audio Recording (optional)</div>
        <div
          class="audio-drop-zone q-mb-md"
          :class="{ 'drop-active': isDragOver }"
          @dragover.prevent="isDragOver = true"
          @dragleave="isDragOver = false"
          @drop.prevent="onFileDrop"
          @click="triggerFileInput"
        >
          <div v-if="!audioFile && !form.existing_audio" class="text-center">
            <q-icon name="cloud_upload" size="28px" color="grey-4" />
            <div class="text-caption text-grey-5 q-mt-xs">Drop audio file here or click to browse</div>
            <div class="text-caption text-grey-4">MP3, WAV, M4A · max 100MB</div>
          </div>
          <div v-else class="row items-center justify-center q-gutter-sm">
            <q-icon name="audio_file" color="primary" size="22px" />
            <span class="text-body2 text-weight-medium">{{ audioFile?.name || 'Current recording' }}</span>
            <q-btn flat round dense icon="close" size="sm" color="grey-6" @click.stop="removeAudio" />
          </div>
        </div>
        <input ref="fileInput" type="file" accept="audio/*" style="display:none;" @change="onFileChange" />

        <!-- Error message -->
        <div v-if="errorMsg" class="text-negative text-caption q-mt-xs">
          <q-icon name="error_outline" size="14px" /> {{ errorMsg }}
        </div>
      </q-card-section>

      <q-card-actions align="right" class="q-pa-md q-pt-none">
        <q-btn flat label="Cancel" color="grey-7" @click="close" />
        <q-btn
          unelevated color="primary"
          :label="contact ? 'Save' : 'Add Record'"
          :loading="saving"
          :disable="!canSave"
          @click="save"
          style="border-radius: 8px; min-width: 130px;"
        >
          <q-tooltip v-if="!canSave">
            Attach an audio file or check "No Answer" / "Call Back Later" to save
          </q-tooltip>
        </q-btn>
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { usePartnersStore } from 'src/stores/partners'

const props = defineProps({
  modelValue: Boolean,
  partnerId: [Number, String],
  contact: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const store = usePartnersStore()
const fileInput = ref(null)
const audioFile = ref(null)
const isDragOver = ref(false)
const saving = ref(false)
const errorMsg = ref('')

const todayStr = computed(() => new Date().toISOString().slice(0, 10))
const maxDateStr = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() + 14)
  return d.toISOString().slice(0, 10)
})

const dateOptions = (dateStr) => dateStr >= todayStr.value && dateStr <= maxDateStr.value

const formatDate = (d) => {
  if (!d) return ''
  return new Date(d + 'T12:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

const form = ref({
  notes: '',
  existing_audio: null,
  is_missed_call: false,
  callback_later: false,
  callback_date: '',
})

const canSave = computed(() =>
  !!audioFile.value
  || !!form.value.existing_audio
  || form.value.is_missed_call
  || form.value.callback_later
)

watch(() => props.contact, (c) => {
  if (c) {
    form.value.notes = c.notes || ''
    form.value.existing_audio = c.audio_url || null
    form.value.is_missed_call = c.is_missed_call || false
    form.value.callback_later = c.callback_later || false
    form.value.callback_date = ''
    audioFile.value = null
  } else {
    reset()
  }
}, { immediate: true })

watch(() => props.modelValue, (val) => { if (!val) reset() })

const reset = () => {
  form.value = {
    notes: '',
    existing_audio: null,
    is_missed_call: false,
    callback_later: false,
    callback_date: '',
  }
  audioFile.value = null
  errorMsg.value = ''
}

const onMissedCallChange = (val) => {
  if (val) {
    form.value.callback_later = false
    form.value.callback_date = ''
  }
}

const onCallbackChange = (val) => {
  if (val) {
    form.value.is_missed_call = false
    if (!form.value.callback_date) form.value.callback_date = todayStr.value
  } else {
    form.value.callback_date = ''
  }
}

const triggerFileInput = () => fileInput.value?.click()

const onFileChange = (e) => {
  const file = e.target.files[0]
  if (file) audioFile.value = file
}

const onFileDrop = (e) => {
  isDragOver.value = false
  const file = e.dataTransfer.files[0]
  if (file && file.type.startsWith('audio/')) audioFile.value = file
}

const removeAudio = () => {
  audioFile.value = null
  form.value.existing_audio = null
  if (fileInput.value) fileInput.value.value = ''
}

const save = async () => {
  errorMsg.value = ''
  saving.value = true
  try {
    const fd = new FormData()
    fd.append('partner', props.partnerId)
    fd.append('date', new Date().toISOString())
    fd.append('notes', form.value.notes || '')
    fd.append('is_missed_call', form.value.is_missed_call ? 'true' : 'false')
    fd.append('callback_later', form.value.callback_later ? 'true' : 'false')
    if (audioFile.value) fd.append('audio_file', audioFile.value)

    if (props.contact) {
      await store.updateContact(props.contact.id, fd)
    } else {
      await store.createContact(fd)
    }

    // If callback_later with a date — update partner's control_date
    if (form.value.callback_later && form.value.callback_date) {
      await store.updatePartner(props.partnerId, { control_date: form.value.callback_date })
    }

    emit('saved')
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      errorMsg.value = Object.values(data).flat().join(' ')
    } else {
      errorMsg.value = 'Failed to save. Please try again.'
    }
  } finally {
    saving.value = false
  }
}

const close = () => emit('update:modelValue', false)
</script>

<style scoped>
.audio-drop-zone {
  border: 2px dashed #E0E0E0;
  border-radius: 10px;
  padding: 16px;
  min-height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}
.drop-active { border-color: #2E7D32; background: #E8F5E9; }
.audio-drop-zone:hover { border-color: #BDBDBD; }
.field-label { font-size: 12px; font-weight: 600; color: #757575; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
</style>
