<template>
  <q-page class="q-pa-md">
    <div class="text-h6 text-weight-bold q-mb-md">Access Permissions</div>

    <div v-if="loading" class="row justify-center q-mt-xl">
      <q-spinner-dots color="primary" size="48px" />
    </div>

    <template v-else>
      <!-- Role tabs -->
      <q-tabs
        v-model="activeRole"
        dense
        align="left"
        active-color="primary"
        indicator-color="primary"
        class="q-mb-md"
      >
        <q-tab
          v-for="r in roles" :key="r.value"
          :name="r.value"
          :label="r.label"
        />
      </q-tabs>

      <q-tab-panels v-model="activeRole" animated>
        <q-tab-panel v-for="r in roles" :key="r.value" :name="r.value" class="q-pa-none">

          <q-card flat bordered style="border-radius:12px;">
            <q-card-section>
              <div class="row items-center justify-between q-mb-md">
                <div>
                  <div class="text-subtitle1 text-weight-bold">{{ r.label }}</div>
                  <div class="text-caption text-grey-6">{{ r.description }}</div>
                </div>
                <div class="row q-gutter-sm">
                  <q-btn flat color="grey-7" icon="refresh" label="Reset to defaults" size="sm"
                    @click="resetRole(r.value)" :loading="resetting === r.value" />
                  <q-btn unelevated color="primary" icon="save" label="Save" size="sm"
                    style="border-radius:8px;"
                    @click="saveRole(r.value)" :loading="saving === r.value" />
                </div>
              </div>

              <!-- Permissions table -->
              <q-markup-table flat bordered separator="cell" dense>
                <thead>
                  <tr>
                    <th class="text-left" style="min-width:180px;">Section</th>
                    <th v-for="action in allActions" :key="action" class="text-center" style="min-width:80px;">
                      {{ actionLabel(action) }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(actions, section) in sectionsMeta" :key="section">
                    <td>
                      <div class="row items-center q-gutter-xs">
                        <q-icon :name="sectionIcon(section)" size="16px" color="grey-6" />
                        <span class="text-weight-medium">{{ sectionLabel(section) }}</span>
                      </div>
                    </td>
                    <td v-for="action in allActions" :key="action" class="text-center">
                      <q-checkbox
                        v-if="actions.includes(action)"
                        v-model="draft[r.value][section][action]"
                        color="primary"
                        dense
                      />
                      <span v-else class="text-grey-4">—</span>
                    </td>
                  </tr>
                </tbody>
              </q-markup-table>

            </q-card-section>
          </q-card>

        </q-tab-panel>
      </q-tab-panels>
    </template>
  </q-page>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { api } from 'boot/axios'

const $q = useQuasar()

const loading    = ref(true)
const saving     = ref(null)
const resetting  = ref(null)
const activeRole = ref('operator')

const sectionsMeta = ref({})
const draft        = reactive({})

const roles = [
  { value: 'operator',            label: 'Operator',            description: 'Works with Partners CRM' },
  { value: 'producer_onboarding', label: 'Producer Onboarding', description: 'Onboarding funnel only' },
  { value: 'producer_support',    label: 'Producer Support',    description: 'Support funnel only' },
  { value: 'producer_operator',   label: 'Producer Manager',    description: 'Both producer funnels' },
]

const allActions = ['view', 'create', 'edit', 'delete']

const actionLabel = (a) => ({ view: 'View', create: 'Create', edit: 'Edit', delete: 'Delete' }[a] || a)

const sectionLabel = (s) => ({
  partners:             'Partners',
  producers_onboarding: 'Producers – Onboarding',
  producers_support:    'Producers – Support',
  tasks:                'Tasks',
  reports:              'AI Reports',
  analytics:            'Analytics',
  operators:            'Operator Stats',
}[s] || s)

const sectionIcon = (s) => ({
  partners:             'people',
  producers_onboarding: 'rocket_launch',
  producers_support:    'support_agent',
  tasks:                'task_alt',
  reports:              'auto_awesome',
  analytics:            'analytics',
  operators:            'bar_chart',
}[s] || 'settings')

const buildDraft = (rolePerms) => {
  const result = {}
  for (const [section, actions] of Object.entries(sectionsMeta.value)) {
    result[section] = {}
    for (const action of actions) {
      result[section][action] = rolePerms?.[section]?.[action] ?? false
    }
  }
  return result
}

const saveRole = async (role) => {
  saving.value = role
  try {
    await api.put(`/role-permissions/${role}/`, { permissions: draft[role] })
    $q.notify({ type: 'positive', message: 'Permissions saved', timeout: 1500 })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to save' })
  } finally {
    saving.value = null
  }
}

const resetRole = async (role) => {
  resetting.value = role
  try {
    const res = await api.post(`/role-permissions/${role}/reset/`)
    draft[role] = buildDraft(res.data.permissions)
    $q.notify({ type: 'positive', message: 'Reset to defaults', timeout: 1500 })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to reset' })
  } finally {
    resetting.value = null
  }
}

onMounted(async () => {
  try {
    const [metaRes, permsRes] = await Promise.all([
      api.get('/sections-meta/'),
      api.get('/role-permissions/'),
    ])
    sectionsMeta.value = metaRes.data
    for (const r of roles) {
      draft[r.value] = buildDraft(permsRes.data[r.value])
    }
  } finally {
    loading.value = false
  }
})
</script>
