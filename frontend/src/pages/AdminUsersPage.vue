<template>
  <q-page class="q-pa-md">

    <div class="row items-center q-mb-md">
      <div class="text-h6 text-weight-bold">Operators & Users</div>
      <q-space />
      <q-btn unelevated color="green-8" icon="person_add" label="New User"
        style="border-radius:8px"
        @click="openCreate" />
    </div>

    <q-card flat bordered style="border-radius:12px;overflow:hidden;">
      <q-table
        :rows="users"
        :columns="columns"
        row-key="id"
        :loading="loading"
        flat
        :rows-per-page-options="[25, 50, 0]"
        no-data-label="No users found"
      >
        <template #body-cell-name="props">
          <q-td :props="props">
            <div class="row items-center q-gutter-sm">
              <q-avatar size="32px" :color="props.row.role === 'admin' ? 'primary' : 'secondary'" text-color="white" style="font-size:11px;flex-shrink:0;">
                {{ initials(props.row) }}
              </q-avatar>
              <div>
                <div class="text-weight-medium">{{ props.row.full_name || props.row.username }}</div>
                <div class="text-caption text-grey-5">@{{ props.row.username }}</div>
              </div>
            </div>
          </q-td>
        </template>

        <template #body-cell-role="props">
          <q-td :props="props">
            <q-chip dense size="sm"
              :color="roleColor(props.row.role)"
              :text-color="roleTextColor(props.row.role)"
              style="font-size:10px;font-weight:700;"
            >
              {{ roleLabel(props.row.role) }}
            </q-chip>
          </q-td>
        </template>

        <template #body-cell-email="props">
          <q-td :props="props">
            <span class="text-caption text-grey-7">{{ props.row.email || '—' }}</span>
          </q-td>
        </template>

        <template #body-cell-actions="props">
          <q-td :props="props" class="text-right">
            <q-btn flat round dense icon="edit" size="sm" color="grey-6" @click="openEdit(props.row)">
              <q-tooltip>Edit</q-tooltip>
            </q-btn>
            <q-btn flat round dense icon="delete" size="sm" color="grey-4"
              :disable="props.row.id === currentUserId"
              @click="confirmDelete(props.row)">
              <q-tooltip>{{ props.row.id === currentUserId ? 'Cannot delete yourself' : 'Delete' }}</q-tooltip>
            </q-btn>
          </q-td>
        </template>
      </q-table>
    </q-card>

    <!-- Create / Edit dialog -->
    <q-dialog v-model="dialogOpen" persistent>
      <q-card style="min-width:440px;border-radius:14px;">
        <q-card-section class="row items-center q-pb-none">
          <q-icon name="person" color="green-7" size="22px" class="q-mr-sm" />
          <div class="text-h6 text-weight-bold">{{ editingUser ? 'Edit User' : 'New User' }}</div>
          <q-space />
          <q-btn flat round icon="close" @click="dialogOpen = false" />
        </q-card-section>

        <q-card-section class="q-pt-md">
          <q-form class="q-gutter-sm">

            <div class="row q-gutter-sm">
              <div style="flex:1">
                <div class="field-label q-mb-xs">First Name</div>
                <q-input v-model="form.first_name" outlined dense placeholder="First name" />
              </div>
              <div style="flex:1">
                <div class="field-label q-mb-xs">Last Name</div>
                <q-input v-model="form.last_name" outlined dense placeholder="Last name" />
              </div>
            </div>

            <div v-if="!editingUser">
              <div class="field-label q-mb-xs">Username (login) *</div>
              <q-input v-model="form.username" outlined dense placeholder="e.g. anna_operator"
                :error="!!errors.username" :error-message="errors.username" />
            </div>

            <div>
              <div class="field-label q-mb-xs">Email</div>
              <q-input v-model="form.email" outlined dense type="email" placeholder="email@example.com" />
            </div>

            <div>
              <div class="field-label q-mb-xs">Role *</div>
              <q-select v-model="form.role" :options="roleOptions" emit-value map-options
                outlined dense />
            </div>

            <div>
              <div class="field-label q-mb-xs">{{ editingUser ? 'New Password (leave blank to keep)' : 'Password *' }}</div>
              <q-input v-model="form.password" outlined dense
                :type="showPwd ? 'text' : 'password'"
                :placeholder="editingUser ? 'Leave blank to keep current' : 'Min 6 characters'"
                :error="!!errors.password" :error-message="errors.password"
              >
                <template #append>
                  <q-icon :name="showPwd ? 'visibility_off' : 'visibility'" class="cursor-pointer" @click="showPwd = !showPwd" />
                </template>
              </q-input>
            </div>

          </q-form>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md q-pt-none">
          <q-btn flat label="Cancel" color="grey-7" @click="dialogOpen = false" />
          <q-btn unelevated color="green-8" :label="editingUser ? 'Save' : 'Create'"
            style="border-radius:8px;min-width:90px"
            :loading="saving"
            @click="submit" />
        </q-card-actions>
      </q-card>
    </q-dialog>

  </q-page>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { useAuthStore } from 'src/stores/auth'
import { api } from 'boot/axios'

const $q        = useQuasar()
const authStore = useAuthStore()

const users   = ref([])
const loading = ref(false)
const dialogOpen  = ref(false)
const editingUser = ref(null)
const saving  = ref(false)
const showPwd = ref(false)
const errors  = ref({})

const currentUserId = authStore.user?.id

const blank = () => ({
  username: '', first_name: '', last_name: '', email: '', role: 'operator', password: '',
})
const form = ref(blank())

const columns = [
  { name: 'name',    label: 'Name',     field: 'full_name',  align: 'left',  sortable: true },
  { name: 'role',    label: 'Role',     field: 'role',       align: 'left',  sortable: true },
  { name: 'email',   label: 'Email',    field: 'email',      align: 'left',  sortable: false },
  { name: 'actions', label: '',         field: 'id',         align: 'right' },
]

const roleOptions = [
  { label: 'Admin',               value: 'admin' },
  { label: 'Operator',            value: 'operator' },
  { label: 'Producer Manager',    value: 'producer_operator' },
  { label: 'Producer Onboarding', value: 'producer_onboarding' },
  { label: 'Producer Support',    value: 'producer_support' },
]

function initials(u) {
  return (u.full_name || u.username || '?').split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}
function roleLabel(r) {
  return roleOptions.find(o => o.value === r)?.label || r
}
function roleColor(r) {
  return { admin: 'deep-purple-2', operator: 'blue-2', producer_operator: 'green-2',
           producer_onboarding: 'teal-2', producer_support: 'cyan-2' }[r] || 'grey-2'
}
function roleTextColor(r) {
  return { admin: 'deep-purple-9', operator: 'blue-9', producer_operator: 'green-9',
           producer_onboarding: 'teal-9', producer_support: 'cyan-9' }[r] || 'grey-7'
}

async function loadUsers() {
  loading.value = true
  try {
    const res = await api.get('/users/')
    users.value = res.data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingUser.value = null
  form.value = blank()
  errors.value = {}
  showPwd.value = false
  dialogOpen.value = true
}

function openEdit(user) {
  editingUser.value = user
  form.value = {
    username:   user.username,
    first_name: user.first_name || '',
    last_name:  user.last_name  || '',
    email:      user.email      || '',
    role:       user.role,
    password:   '',
  }
  errors.value = {}
  showPwd.value = false
  dialogOpen.value = true
}

async function submit() {
  errors.value = {}
  if (!editingUser.value && !form.value.username.trim()) {
    errors.value.username = 'Username is required'
    return
  }
  if (!editingUser.value && !form.value.password) {
    errors.value.password = 'Password is required'
    return
  }
  saving.value = true
  try {
    const payload = {
      first_name: form.value.first_name,
      last_name:  form.value.last_name,
      email:      form.value.email,
      role:       form.value.role,
    }
    if (!editingUser.value) payload.username = form.value.username.trim()
    if (form.value.password) payload.password = form.value.password

    if (editingUser.value) {
      await api.patch(`/users/${editingUser.value.id}/`, payload)
      $q.notify({ type: 'positive', message: 'User updated' })
    } else {
      await api.post('/users/', payload)
      $q.notify({ type: 'positive', message: 'User created' })
    }

    dialogOpen.value = false
    await loadUsers()
  } catch (e) {
    const data = e?.response?.data || {}
    if (data.username) errors.value.username = Array.isArray(data.username) ? data.username[0] : data.username
    if (data.password) errors.value.password = Array.isArray(data.password) ? data.password[0] : data.password
    if (!errors.value.username && !errors.value.password) {
      $q.notify({ type: 'negative', message: data.detail || 'Error saving user' })
    }
  } finally {
    saving.value = false
  }
}

function confirmDelete(user) {
  $q.dialog({
    title: 'Delete User',
    message: `Delete user "${user.full_name || user.username}"? This cannot be undone.`,
    cancel: true,
    ok: { label: 'Delete', color: 'negative' },
  }).onOk(async () => {
    try {
      await api.delete(`/users/${user.id}/`)
      $q.notify({ type: 'positive', message: 'User deleted' })
      await loadUsers()
    } catch (e) {
      $q.notify({ type: 'negative', message: e?.response?.data?.detail || 'Error deleting user' })
    }
  })
}

onMounted(loadUsers)
</script>

<style scoped>
.field-label { font-size: 12px; font-weight: 600; color: #616161; }
</style>
