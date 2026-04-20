<template>
  <div class="login-page flex flex-center">
    <div class="login-wrapper">
      <!-- Logo card -->
      <div class="text-center q-mb-xl">
        <q-icon name="spa" size="52px" color="primary" />
        <div style="font-size:26px; font-weight:800; color:#1C2526; letter-spacing:0.5px; margin-top:8px;">
          Ask Ayurveda
        </div>
        <div style="font-size:13px; color:#9E9E9E; letter-spacing:2px; text-transform:uppercase; margin-top:2px;">
          Partner CRM
        </div>
      </div>

      <q-card class="login-card" flat bordered>
        <q-card-section class="q-pa-xl">
          <div class="text-h6 text-weight-bold q-mb-xs">Sign in</div>
          <div class="text-caption text-grey-6 q-mb-lg">Enter your credentials to continue</div>

          <q-form @submit.prevent="handleLogin">
            <div class="q-mb-md">
              <div class="field-label">Username</div>
              <q-input
                v-model="form.username"
                outlined
                dense
                placeholder="Enter username"
                :disable="loading"
                autofocus
                :rules="[val => !!val || 'Required']"
              >
                <template #prepend>
                  <q-icon name="person" color="grey-5" />
                </template>
              </q-input>
            </div>

            <div class="q-mb-lg">
              <div class="field-label">Password</div>
              <q-input
                v-model="form.password"
                outlined
                dense
                :type="showPassword ? 'text' : 'password'"
                placeholder="Enter password"
                :disable="loading"
                :rules="[val => !!val || 'Required']"
              >
                <template #prepend>
                  <q-icon name="lock" color="grey-5" />
                </template>
                <template #append>
                  <q-icon
                    :name="showPassword ? 'visibility_off' : 'visibility'"
                    class="cursor-pointer text-grey-5"
                    @click="showPassword = !showPassword"
                  />
                </template>
              </q-input>
            </div>

            <q-btn
              type="submit"
              color="primary"
              label="Sign In"
              class="full-width"
              size="md"
              :loading="loading"
              unelevated
              style="border-radius: 8px; height: 44px; font-weight: 600;"
            />
          </q-form>

          <div v-if="error" class="text-negative text-center text-caption q-mt-md">
            <q-icon name="error_outline" size="14px" /> {{ error }}
          </div>
        </q-card-section>
      </q-card>

      <div class="text-center text-caption text-grey-5 q-mt-lg">
        Ask Ayurveda © {{ new Date().getFullYear() }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from 'src/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({ username: '', password: '' })
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(form.value.username, form.value.password)
    router.push('/kanban')
  } catch (e) {
    const detail = e.response?.data?.detail
    error.value = detail || 'Invalid username or password'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  background: linear-gradient(135deg, #E8F5E9 0%, #F5F7FA 50%, #E1F5FE 100%);
  min-height: 100vh;
}

.login-wrapper {
  width: 100%;
  max-width: 400px;
  padding: 24px;
}

.login-card {
  border-radius: 16px !important;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.08) !important;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: #424242;
  margin-bottom: 6px;
}
</style>
