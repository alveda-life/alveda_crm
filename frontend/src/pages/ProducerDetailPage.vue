<template>
  <q-page class="q-pa-md">

    <div v-if="!producer" class="flex flex-center" style="min-height:300px;">
      <q-spinner-dots color="primary" size="48px" />
    </div>

    <div v-else>
      <!-- Breadcrumb -->
      <div class="row items-center justify-between q-mb-md">
        <div class="row items-center q-gutter-xs">
          <q-btn flat dense icon="arrow_back" color="grey-7" @click="$router.back()" />
          <q-breadcrumbs>
            <q-breadcrumbs-el
              :label="producer.funnel === 'support' ? 'Support' : 'Onboarding'"
              :to="producer.funnel === 'support' ? '/producers/support' : '/producers/onboarding'"
            />
            <q-breadcrumbs-el :label="producer.name" />
          </q-breadcrumbs>
        </div>
        <q-btn flat icon="edit" label="Edit" color="grey-7" @click="showEditDialog = true" />
      </div>

      <div class="row q-gutter-md">

        <!-- LEFT: Info card -->
        <div style="min-width:280px;max-width:320px;flex-shrink:0;">
          <q-card flat bordered style="border-radius:12px;" class="q-mb-md">
            <q-card-section>
              <!-- Name badge -->
              <div class="name-badge q-mb-sm" :style="`background:${nameColor.bg};color:${nameColor.text}`">
                {{ producer.name }}
              </div>
              <div v-if="producer.company" class="text-subtitle2 text-grey-7 q-mb-sm">{{ producer.company }}</div>

              <q-separator class="q-my-sm" />

              <!-- Stage -->
              <div class="field-label q-mb-xs">Stage</div>
              <q-select
                :model-value="producer.stage"
                :options="activeStageOptions"
                emit-value map-options
                outlined dense
                class="q-mb-sm"
                @update:model-value="changeStage"
              />

              <!-- Control date -->
              <div class="field-label q-mb-xs">Follow-up Date</div>
              <q-input
                :model-value="producer.control_date"
                outlined dense type="date" clearable
                class="q-mb-sm"
                @update:model-value="val => updateField('control_date', val || null)"
              />

              <!-- Planned connection date -->
              <div class="field-label q-mb-xs">Plan. Connection Date</div>
              <q-input
                :model-value="producer.planned_connection_date"
                outlined dense type="date" clearable
                class="q-mb-sm"
                @update:model-value="val => updateField('planned_connection_date', val || null)"
              />

              <!-- Product categories -->
              <div class="field-label q-mb-xs">Product Categories</div>
              <q-select
                :model-value="productTypeArr"
                :options="productTypeOptions"
                outlined dense multiple
                use-chips use-input input-debounce="0"
                new-value-mode="add-unique"
                placeholder="Ayurvedic, Supplements…"
                class="q-mb-sm"
                @update:model-value="val => updateField('product_type', val.join(', '))"
              />

              <q-separator class="q-my-sm" />

              <!-- Assigned operator -->
              <div class="field-label q-mb-xs">Responsible</div>
              <div class="operator-pill" :class="producer.assigned_to_detail ? '' : 'operator-pill--empty'">
                <template v-if="producer.assigned_to_detail">
                  <q-avatar size="28px" color="primary" text-color="white" style="font-size:11px;flex-shrink:0;">
                    {{ initials(producer.assigned_to_detail) }}
                  </q-avatar>
                  <div style="flex:1;min-width:0;">
                    <div style="font-size:13px;font-weight:600;color:#212121;">
                      {{ producer.assigned_to_detail.full_name || producer.assigned_to_detail.username }}
                    </div>
                    <div style="font-size:11px;color:#9E9E9E;">Operator</div>
                  </div>
                </template>
                <template v-else>
                  <q-icon name="person_add" size="20px" color="grey-5" />
                  <span style="font-size:13px;color:#9E9E9E;">Not assigned</span>
                </template>
                <q-icon name="edit" size="14px" color="grey-4" style="margin-left:auto;" />
                <q-menu>
                  <q-list dense style="min-width:180px;">
                    <q-item-label header class="text-caption">Assign operator</q-item-label>
                    <q-item
                      v-for="user in store.users" :key="user.id"
                      clickable v-close-popup
                      :disable="user.id === producer.assigned_to"
                      @click="assignOperator(user)"
                    >
                      <q-item-section avatar>
                        <q-avatar size="26px" :color="user.id === producer.assigned_to ? 'primary' : 'grey-4'" text-color="white" style="font-size:10px;">
                          {{ initials(user) }}
                        </q-avatar>
                      </q-item-section>
                      <q-item-section>{{ user.full_name || user.username }}</q-item-section>
                      <q-item-section side v-if="user.id === producer.assigned_to">
                        <q-icon name="check" size="14px" color="primary" />
                      </q-item-section>
                    </q-item>
                  </q-list>
                </q-menu>
              </div>

              <q-separator class="q-my-sm" />

              <!-- Contact info -->
              <div v-if="producer.phone" class="info-row">
                <q-icon name="phone" color="grey-5" size="16px" />
                <span>{{ producer.phone }}</span>
              </div>
              <div v-if="producer.email" class="info-row">
                <q-icon name="email" color="grey-5" size="16px" />
                <a :href="`mailto:${producer.email}`" class="text-primary">{{ producer.email }}</a>
              </div>
              <div v-if="producer.website" class="info-row">
                <q-icon name="language" color="grey-5" size="16px" />
                <a :href="producer.website" target="_blank" class="text-primary ellipsis" style="max-width:180px;">
                  {{ producer.website }}
                </a>
              </div>
              <div v-if="producer.city" class="info-row">
                <q-icon name="location_on" color="grey-5" size="16px" />
                <span>{{ producer.city }}</span>
              </div>
            </q-card-section>
          </q-card>

          <!-- Pharma Details card -->
          <q-card flat bordered style="border-radius:12px;" class="q-mb-md">
            <q-card-section class="q-pa-sm q-pb-xs">
              <div class="row items-center justify-between">
                <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#9E9E9E;">
                  Pharma Details
                </div>
                <div v-if="editingPharma" class="row items-center q-gutter-xs">
                  <q-btn flat dense round icon="close" size="xs" color="grey-5" @click="cancelPharmaEdit">
                    <q-tooltip>Cancel</q-tooltip>
                  </q-btn>
                  <q-btn flat dense round icon="check" size="xs" color="positive"
                    :loading="savingPharma" @click="savePharma">
                    <q-tooltip>Save</q-tooltip>
                  </q-btn>
                </div>
                <q-btn v-else flat dense round icon="edit" size="xs" color="grey-5" @click="startPharmaEdit">
                  <q-tooltip>Edit pharma details</q-tooltip>
                </q-btn>
              </div>
            </q-card-section>

            <!-- VIEW MODE -->
            <q-card-section class="q-pt-xs" v-if="!editingPharma">
              <div class="row items-center justify-between q-mb-xs">
                <span class="text-caption text-grey-6">Priority</span>
                <q-chip dense size="xs" :style="priorityChipStyle(producer.priority)" style="font-weight:600;">
                  {{ producer.priority_display || producer.priority }}
                </q-chip>
              </div>
              <div class="row items-center justify-between q-mb-xs">
                <span class="text-caption text-grey-6">Coop. Potential</span>
                <q-chip dense size="xs" :style="coopChipStyle(producer.cooperation_potential)">
                  {{ producer.cooperation_potential_display || producer.cooperation_potential }}
                </q-chip>
              </div>
              <div v-if="producer.product_count" class="row items-center justify-between q-mb-xs">
                <span class="text-caption text-grey-6">SKUs / Products</span>
                <span class="text-caption text-weight-medium">{{ producer.product_count }}</span>
              </div>
              <div class="row items-center justify-between q-mb-xs">
                <span class="text-caption text-grey-6">Last Contact</span>
                <span v-if="producer.last_contact" class="text-caption" style="color:#424242;">
                  {{ producer.last_contact }}
                </span>
                <span v-else class="text-caption text-grey-4">—</span>
              </div>
              <template v-if="producer.next_step">
                <q-separator class="q-my-xs" />
                <div class="text-caption text-grey-6 q-mb-xs">Next Step</div>
                <div class="text-caption text-grey-8" style="line-height:1.5;">{{ producer.next_step }}</div>
              </template>
              <template v-if="producer.certifications">
                <q-separator class="q-my-xs" />
                <div class="text-caption text-grey-6 q-mb-xs">Certifications</div>
                <div class="row q-gutter-xs flex-wrap">
                  <q-chip v-for="cert in splitTags(producer.certifications)" :key="cert"
                    dense size="xs" style="background:#E8F5E9;color:#2E7D32;border:1px solid #A5D6A7;">
                    {{ cert }}
                  </q-chip>
                </div>
              </template>
              <template v-if="producer.communication_status">
                <q-separator class="q-my-xs" />
                <div class="text-caption text-grey-6 q-mb-xs">Comm. Status</div>
                <div class="row q-gutter-xs flex-wrap">
                  <q-chip v-for="tag in splitTags(producer.communication_status)" :key="tag"
                    dense size="xs" style="background:#FFF3E0;color:#E65100;border:1px solid #FFCC80;">
                    {{ tag }}
                  </q-chip>
                </div>
              </template>
              <template v-if="producer.contact_info">
                <q-separator class="q-my-xs" />
                <div class="text-caption text-grey-6 q-mb-xs">Key Contacts</div>
                <div class="text-caption text-grey-8" style="white-space:pre-wrap;line-height:1.5;">{{ producer.contact_info }}</div>
              </template>
              <template v-if="producer.notes">
                <q-separator class="q-my-xs" />
                <div class="text-caption text-grey-6 q-mb-xs">Notes</div>
                <div class="text-body2 text-grey-8" style="white-space:pre-wrap;line-height:1.5;font-size:12px;">{{ producer.notes }}</div>
              </template>
            </q-card-section>

            <!-- EDIT MODE -->
            <q-card-section class="q-pt-xs" v-else>
              <div style="display:flex;flex-direction:column;gap:8px;">
                <div>
                  <div class="field-label q-mb-xs">Priority</div>
                  <q-select v-model="pharmaForm.priority" :options="priorityOptions"
                    emit-value map-options outlined dense />
                </div>
                <div>
                  <div class="field-label q-mb-xs">Coop. Potential</div>
                  <q-select v-model="pharmaForm.cooperation_potential" :options="coopOptions"
                    emit-value map-options outlined dense />
                </div>
                <div>
                  <div class="field-label q-mb-xs">Product Count (SKUs)</div>
                  <q-input v-model.number="pharmaForm.product_count" outlined dense
                    type="number" min="0" clearable />
                </div>
                <div>
                  <div class="field-label q-mb-xs">Last Contact Date</div>
                  <q-input v-model="pharmaForm.last_contact" outlined dense type="date" clearable />
                </div>
                <div>
                  <div class="field-label q-mb-xs">Product Categories</div>
                  <q-select
                    v-model="pharmaForm.product_type_arr"
                    :options="productTypeOptions"
                    outlined dense multiple
                    use-chips use-input input-debounce="0"
                    new-value-mode="add-unique"
                    placeholder="Ayurvedic, Supplements…"
                  />
                </div>
                <div>
                  <div class="field-label q-mb-xs">Next Step</div>
                  <q-select
                    v-model="pharmaForm.next_step"
                    :options="nextStepOptions"
                    outlined dense
                    use-input input-debounce="0"
                    new-value-mode="add"
                    clearable
                    placeholder="Select or type…"
                  />
                </div>
                <div>
                  <div class="field-label q-mb-xs">Certifications</div>
                  <q-select
                    v-model="pharmaForm.certifications_arr"
                    :options="certOptions"
                    outlined dense multiple
                    use-chips use-input input-debounce="0"
                    new-value-mode="add-unique"
                    placeholder="GMP, ISO, FSSAI…"
                  />
                </div>
                <div>
                  <div class="field-label q-mb-xs">Communication Status</div>
                  <q-select
                    v-model="pharmaForm.communication_status_arr"
                    :options="commStatusOptions"
                    outlined dense multiple
                    use-chips use-input input-debounce="0"
                    new-value-mode="add-unique"
                    placeholder="Not Contacted, Email Sent…"
                  />
                </div>
                <div>
                  <div class="field-label q-mb-xs">Key Contacts</div>
                  <q-input v-model="pharmaForm.contact_info" outlined dense
                    type="textarea" rows="2" autogrow
                    placeholder="Names, emails, phones of key contacts" />
                </div>
                <div>
                  <div class="field-label q-mb-xs">Notes</div>
                  <q-input v-model="pharmaForm.notes" outlined dense
                    type="textarea" rows="4" autogrow
                    placeholder="Negotiation notes, agreements, context…" />
                </div>
                <div class="row q-gutter-sm q-mt-xs">
                  <q-btn unelevated color="primary" size="sm" label="Save"
                    :loading="savingPharma" @click="savePharma" style="border-radius:6px;" />
                  <q-btn flat color="grey-7" size="sm" label="Cancel" @click="cancelPharmaEdit" />
                </div>
              </div>
            </q-card-section>
          </q-card>

          <!-- Stage history -->
          <q-card flat bordered style="border-radius:12px;" class="q-mb-md">
            <q-card-section class="q-pa-sm">
              <div class="row items-center q-gutter-xs">
                <q-icon name="history" color="grey-5" size="16px" />
                <span class="text-caption text-grey-6">Stage since:</span>
                <span class="text-caption text-weight-medium">{{ formatDate(producer.stage_changed_at) }}</span>
              </div>
              <div class="row items-center q-gutter-xs q-mt-xs">
                <q-icon name="person" color="grey-5" size="16px" />
                <span class="text-caption text-grey-6">Created by:</span>
                <span class="text-caption text-weight-medium">
                  {{ producer.created_by_detail?.full_name || producer.created_by_detail?.username || '—' }}
                </span>
              </div>
            </q-card-section>
          </q-card>
        </div>

        <!-- RIGHT: Tasks + Comments -->
        <div style="flex:1;min-width:0;">

          <!-- Tasks section -->
          <q-card flat bordered style="border-radius:12px;" class="q-mb-md">
            <q-card-section>
              <div class="row items-center justify-between q-mb-sm">
                <div class="text-subtitle1 text-weight-bold">
                  Tasks
                  <q-badge v-if="openTasksCount > 0" color="negative" class="q-ml-xs">{{ openTasksCount }} open</q-badge>
                </div>
                <q-btn unelevated color="primary" icon="add" label="Add Task" size="sm"
                  style="border-radius:8px;" @click="showTaskDialog = true" />
              </div>

              <!-- Task list -->
              <div v-if="!producer.tasks?.length" class="text-caption text-grey-5 q-py-sm">
                No tasks yet
              </div>

              <q-list separator v-else>
                <q-item
                  v-for="task in producer.tasks" :key="task.id"
                  class="q-px-none"
                  :class="task.is_overdue ? 'task-overdue' : ''"
                >
                  <q-item-section avatar>
                    <q-checkbox
                      :model-value="task.status === 'done'"
                      color="positive"
                      @update:model-value="toggleTask(task)"
                    />
                  </q-item-section>
                  <q-item-section>
                    <div class="row items-center q-gutter-xs">
                      <span :class="task.status === 'done' ? 'text-strike text-grey-5' : 'text-weight-medium'">
                        {{ task.title }}
                      </span>
                      <q-badge
                        :color="priorityColor(task.priority)"
                        text-color="white"
                        dense size="xs"
                      >{{ task.priority_display }}</q-badge>
                      <q-badge
                        v-if="task.status !== 'done' && task.status !== 'open'"
                        color="orange" text-color="white" dense size="xs"
                      >{{ task.status_display }}</q-badge>
                    </div>
                    <div class="row items-center q-gutter-xs" style="font-size:11px;color:#9E9E9E;">
                      <span v-if="task.due_date" :class="task.is_overdue ? 'text-negative' : ''">
                        <q-icon name="event" size="11px" />
                        {{ task.due_date }}
                        <span v-if="task.is_overdue"> (overdue)</span>
                      </span>
                      <span v-if="task.assigned_to_detail">
                        <q-icon name="person" size="11px" />
                        {{ task.assigned_to_detail.full_name || task.assigned_to_detail.username }}
                      </span>
                    </div>
                    <div v-if="task.description" class="text-caption text-grey-6 q-mt-xs">
                      {{ task.description }}
                    </div>
                    <div class="task-audit q-mt-xs">
                      <span class="task-audit-row">
                        <q-icon name="person_add" size="10px" /> Created by
                        <strong>{{ taskUserName(task.created_by_detail) || '—' }}</strong>
                        <span class="task-audit-time">· {{ fmtTaskDatetime(task.created_at) }}</span>
                      </span>
                      <span v-if="task.completed_at" class="task-audit-row task-audit-row--done">
                        <q-icon name="check_circle" size="10px" color="green-6" /> Closed by
                        <strong>{{ taskUserName(task.completed_by_detail) || '—' }}</strong>
                        <span class="task-audit-time">· {{ fmtTaskDatetime(task.completed_at) }}</span>
                      </span>
                    </div>
                  </q-item-section>
                  <q-item-section v-if="authStore.isAdmin" side>
                    <q-btn flat round dense icon="delete" size="xs" color="grey-4"
                      @click.stop="deleteTask(task)" />
                  </q-item-section>
                </q-item>
              </q-list>
            </q-card-section>
          </q-card>

          <!-- Comments section -->
          <q-card flat bordered style="border-radius:12px;">
            <q-card-section>
              <div class="text-subtitle1 text-weight-bold q-mb-sm">Comments</div>

              <!-- Existing comments -->
              <div v-if="!producer.comments?.length" class="text-caption text-grey-5 q-mb-md">
                No comments yet
              </div>
              <div v-else class="q-mb-md">
                <div
                  v-for="comment in [...producer.comments].reverse()" :key="comment.id"
                  class="comment-bubble q-mb-sm"
                >
                  <div class="row items-center justify-between q-mb-xs">
                    <div class="row items-center q-gutter-xs">
                      <q-avatar size="24px" color="primary" text-color="white" style="font-size:10px;">
                        {{ initials(comment.author_detail) }}
                      </q-avatar>
                      <span class="text-caption text-weight-bold">
                        {{ comment.author_detail?.full_name || comment.author_detail?.username || '?' }}
                      </span>
                      <span class="text-caption text-grey-5">{{ formatDate(comment.created_at) }}</span>
                    </div>
                    <q-btn
                      v-if="canDeleteComment(comment)"
                      flat round dense icon="delete" size="xs" color="grey-4"
                      @click="deleteComment(comment)"
                    />
                  </div>
                  <div v-if="comment.text" class="text-body2" style="white-space:pre-wrap;">{{ comment.text }}</div>
                  <div v-if="comment.attachment_url" class="q-mt-xs">
                    <a :href="comment.attachment_url" target="_blank" class="text-primary text-caption row items-center q-gutter-xs">
                      <q-icon name="attach_file" size="14px" />
                      <span>{{ comment.attachment_name || 'Attachment' }}</span>
                    </a>
                  </div>
                </div>
              </div>

              <!-- Add comment form -->
              <q-separator class="q-mb-sm" />
              <div class="row items-end q-gutter-sm">
                <q-input
                  v-model="commentText"
                  outlined dense
                  placeholder="Write a comment..."
                  type="textarea"
                  autogrow
                  style="flex:1;"
                  @keydown.ctrl.enter="submitComment"
                />
              </div>
              <div class="row items-center justify-between q-mt-xs">
                <div class="row items-center q-gutter-sm">
                  <q-btn flat dense icon="attach_file" size="sm" color="grey-6"
                    @click="$refs.fileInput.click()" label="Attach file" />
                  <span v-if="attachFile" class="text-caption text-grey-6">
                    {{ attachFile.name }}
                    <q-btn flat dense round icon="close" size="xs" @click="attachFile = null" />
                  </span>
                </div>
                <q-btn unelevated color="primary" icon="send" label="Send" size="sm"
                  :loading="commentSaving"
                  :disable="!commentText.trim() && !attachFile"
                  style="border-radius:8px;"
                  @click="submitComment"
                />
              </div>
              <input ref="fileInput" type="file" style="display:none;" @change="onFileSelected" />
            </q-card-section>
          </q-card>

        </div>
      </div>
    </div>

    <!-- Edit dialog -->
    <AddProducerDialog
      v-model="showEditDialog"
      :users="store.users"
      :producer="producer"
      @updated="onUpdated"
    />

    <!-- Add Task dialog -->
    <ProducerTaskDialog
      v-model="showTaskDialog"
      :users="store.users"
      @save="saveTask"
    />

  </q-page>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuasar } from 'quasar'
import { useProducersStore } from 'src/stores/producers'
import { useAuthStore } from 'src/stores/auth'
import AddProducerDialog from 'src/components/AddProducerDialog.vue'
import ProducerTaskDialog from 'src/components/ProducerTaskDialog.vue'

const $q        = useQuasar()
const route     = useRoute()
const store     = useProducersStore()
const authStore = useAuthStore()

const showEditDialog = ref(false)
const showTaskDialog = ref(false)
const commentText    = ref('')
const attachFile     = ref(null)
const commentSaving  = ref(false)
const fileInput      = ref(null)

// ── Pharma inline edit ────────────────────────────────────────────────────────
const editingPharma = ref(false)
const savingPharma  = ref(false)
const pharmaForm    = ref({})

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

const producer = computed(() => store.currentProducer)

const PALETTE = [
  ['#E3F2FD','#1565C0'], ['#F3E5F5','#6A1B9A'], ['#E8F5E9','#2E7D32'],
  ['#FFF8E1','#F57F17'], ['#FCE4EC','#880E4F'], ['#E0F2F1','#004D40'],
]
const nameColor = computed(() => {
  const id = producer.value?.id ?? 0
  const p = PALETTE[id % PALETTE.length]
  return { bg: p[0], text: p[1] }
})

const onboardingStageOptions = [
  { label: 'Interest',         value: 'interest' },
  { label: 'In Communication', value: 'in_communication' },
  { label: 'Signing Contract',     value: 'negotiation' },
  { label: 'Contract Signed',  value: 'contract_signed' },
  { label: 'On the Platform',  value: 'on_platform' },
  { label: 'Stopped',          value: 'stopped' },
]
const supportStageOptions = [
  { label: 'Agreed',           value: 'agreed' },
  { label: 'Signed',           value: 'signed' },
  { label: 'Products Received',value: 'products_received' },
  { label: 'Ready to Sell',    value: 'ready_to_sell' },
  { label: 'In Store',         value: 'in_store' },
]
const activeStageOptions = computed(() =>
  producer.value?.funnel === 'onboarding' ? onboardingStageOptions : supportStageOptions
)

const openTasksCount = computed(() =>
  producer.value?.tasks?.filter(t => t.status === 'open' || t.status === 'in_progress').length ?? 0
)

const initials = (user) => {
  if (!user) return '?'
  return (user.full_name || user.username || '?')
    .split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

const formatDate = (dt) => {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

const fmtTaskDatetime = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

const taskUserName = (detail) => {
  if (!detail) return ''
  return detail.full_name || detail.username || ''
}

const priorityColor = (p) => ({ high: 'negative', medium: 'orange', low: 'grey-5' }[p] || 'grey-5')

// ── Pharma field options ──────────────────────────────────────────────────────
const productTypeOptions = [
  'Ayurveda', 'Herbal', 'Supplements', 'Cosmetics', 'Wellness',
  'Pharmaceuticals', 'Food & Nutrition', 'Other',
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

const toArr = (str) => (str || '').split(',').map(s => s.trim()).filter(Boolean)

const startPharmaEdit = () => {
  const p = producer.value
  pharmaForm.value = {
    priority:                   p.priority || 'medium',
    product_count:              p.product_count ?? null,
    cooperation_potential:      p.cooperation_potential || 'medium',
    certifications_arr:         toArr(p.certifications),
    communication_status_arr:   toArr(p.communication_status),
    product_type_arr:           toArr(p.product_type),
    next_step:                  p.next_step || '',
    contact_info:               p.contact_info || '',
    last_contact:               p.last_contact || null,
    notes:                      p.notes || '',
  }
  editingPharma.value = true
}

const cancelPharmaEdit = () => { editingPharma.value = false }

const savePharma = async () => {
  savingPharma.value = true
  try {
    const payload = {
      ...pharmaForm.value,
      product_type:         pharmaForm.value.product_type_arr.join(', '),
      certifications:       pharmaForm.value.certifications_arr.join(', '),
      communication_status: pharmaForm.value.communication_status_arr.join(', '),
    }
    delete payload.product_type_arr
    delete payload.certifications_arr
    delete payload.communication_status_arr
    delete payload.control_date  // managed via immediate-save field, not pharma form
    // notes already in payload as-is
    await store.updateProducer(producer.value.id, payload)
    editingPharma.value = false
    $q.notify({ type: 'positive', message: 'Pharma details saved', timeout: 1500 })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to save' })
  } finally {
    savingPharma.value = false
  }
}

const priorityChipStyle = (p) => ({
  high:   'background:#FFEBEE;color:#C62828;border:1px solid #FFCDD2;',
  medium: 'background:#FFF3E0;color:#E65100;border:1px solid #FFCC80;',
  low:    'background:#F5F5F5;color:#616161;border:1px solid #E0E0E0;',
}[p] || 'background:#F5F5F5;color:#616161;')

const coopChipStyle = (p) => ({
  strong:      'background:#E8F5E9;color:#2E7D32;border:1px solid #A5D6A7;',
  medium:      'background:#E3F2FD;color:#1565C0;border:1px solid #90CAF9;',
  weak:        'background:#FFF3E0;color:#E65100;border:1px solid #FFCC80;',
  no_response: 'background:#F5F5F5;color:#757575;border:1px solid #E0E0E0;',
}[p] || 'background:#F5F5F5;color:#616161;')

const splitTags = (str) => (str || '').split(',').map(s => s.trim()).filter(Boolean)

const isDateOverdue = (date) => date && new Date(date) < new Date(new Date().toDateString())

const canDeleteComment = (comment) => {
  return authStore.isAdmin || comment.author_detail?.id === authStore.user?.id
}

// ── Actions ──────────────────────────────────────────────────────────────────

const changeStage = async (newStage) => {
  try {
    const result = await store.updateStage(producer.value.id, newStage)
    if (result.support_created) {
      $q.notify({ type: 'info', message: 'Producer reached On the Platform — added to Support funnel', timeout: 3000 })
    } else {
      $q.notify({ type: 'positive', message: 'Stage updated', timeout: 1500 })
    }
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to update stage' })
  }
}

const productTypeArr = computed(() => {
  const v = producer.value?.product_type || ''
  return v ? v.split(',').map(s => s.trim()).filter(Boolean) : []
})

const updateField = async (field, value) => {
  try {
    await store.updateProducer(producer.value.id, { [field]: value })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to save' })
  }
}

const assignOperator = async (user) => {
  try {
    await store.updateProducer(producer.value.id, { assigned_to: user.id })
    $q.notify({ type: 'positive', message: `Assigned to ${user.full_name || user.username}`, timeout: 1500 })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to assign' })
  }
}

const saveTask = async (taskData) => {
  try {
    await store.addTask(producer.value.id, taskData)
    showTaskDialog.value = false
    $q.notify({ type: 'positive', message: 'Task added', timeout: 1500 })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to add task' })
  }
}

const toggleTask = async (task) => {
  const newStatus = task.status === 'done' ? 'open' : 'done'
  try {
    await store.updateTask(producer.value.id, task.id, { status: newStatus })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to update task' })
  }
}

const deleteTask = async (task) => {
  try {
    await store.deleteTask(producer.value.id, task.id)
    $q.notify({ type: 'positive', message: 'Task deleted', timeout: 1500 })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to delete task' })
  }
}

const onFileSelected = (e) => {
  attachFile.value = e.target.files[0] || null
}

const submitComment = async () => {
  if (!commentText.value.trim() && !attachFile.value) return
  commentSaving.value = true
  try {
    const fd = new FormData()
    if (commentText.value.trim()) fd.append('text', commentText.value)
    if (attachFile.value) {
      fd.append('attachment', attachFile.value)
      fd.append('attachment_name', attachFile.value.name)
    }
    await store.addComment(producer.value.id, fd)
    commentText.value = ''
    attachFile.value  = null
    if (fileInput.value) fileInput.value.value = ''
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to send comment' })
  } finally {
    commentSaving.value = false
  }
}

const deleteComment = async (comment) => {
  try {
    await store.deleteComment(producer.value.id, comment.id)
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to delete comment' })
  }
}

const onUpdated = () => {
  showEditDialog.value = false
  store.fetchProducer(route.params.id)
  $q.notify({ type: 'positive', message: 'Producer updated', timeout: 1500 })
}

onMounted(async () => {
  await Promise.all([
    store.fetchProducer(route.params.id),
    store.fetchUsers(),
  ])
})
</script>

<style scoped>
.name-badge {
  display: inline-block;
  padding: 4px 14px;
  border-radius: 20px;
  font-size: 16px;
  font-weight: 700;
}
.field-label { font-size: 12px; font-weight: 600; color: #616161; }
.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #424242;
  margin-bottom: 6px;
}
.operator-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #e0e0e0;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 8px;
}
.operator-pill:hover { background: #f5f5f5; }
.operator-pill--empty { border-style: dashed; }
.comment-bubble {
  background: #f5f5f5;
  border-radius: 10px;
  padding: 10px 12px;
}
.task-overdue { background: #fff8f8; }

.task-audit {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 10.5px;
  color: #9E9E9E;
  margin-top: 4px;
}
.task-audit-row {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.task-audit-row strong {
  font-weight: 600;
  color: #424242;
  margin: 0 2px;
}
.task-audit-row--done strong { color: #2E7D32; }
.task-audit-time { color: #BDBDBD; }
</style>
