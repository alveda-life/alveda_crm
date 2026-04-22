<template>
  <q-layout view="lHh Lpr lFf">
    <!-- Sidebar -->
    <q-drawer
      v-model="drawer"
      show-if-above
      :width="220"
      :breakpoint="800"
      bordered
      class="bg-dark text-white"
    >
      <div style="height:100%; display:flex; flex-direction:column;">

        <!-- Scrollable top content -->
        <q-scroll-area style="flex:1; min-height:0;">
          <!-- Logo -->
          <div class="q-pa-md q-pt-lg">
            <div class="row items-center q-gutter-sm q-mb-xs">
              <q-icon name="spa" size="28px" color="primary" />
              <div>
                <div class="sidebar-logo text-white">Ask Ayurveda</div>
                <div style="font-size:11px; color:#81C784; letter-spacing:1px;">CRM</div>
              </div>
            </div>
          </div>

          <q-separator dark class="q-mb-sm" />

          <!-- Partner section (admin + operator) -->
          <template v-if="showPartnerNav">
            <div class="nav-section-label">Partners</div>
            <q-list padding class="q-pt-none">
              <q-item
                v-for="item in partnerNavItems"
                :key="item.path"
                :to="item.path"
                exact
                clickable v-ripple
                active-class="nav-active"
                class="rounded-borders q-mx-sm q-mb-xs"
                style="border-radius:8px;"
              >
                <q-item-section avatar>
                  <q-icon :name="item.icon" size="20px" />
                </q-item-section>
                <q-item-section>{{ item.label }}</q-item-section>
                <q-item-section v-if="item.badge" side>
                  <q-badge :label="item.badge" color="deep-orange-7" rounded style="font-size:11px;font-weight:800;min-width:20px" />
                </q-item-section>
              </q-item>
            </q-list>
          </template>

          <!-- Tools section: Tasks + AI Report (independent of partner access) -->
          <template v-if="showToolsNav">
            <q-separator dark class="q-my-xs" v-if="showPartnerNav" />
            <div class="nav-section-label">Tools</div>
            <q-list padding class="q-pt-none">
              <q-item
                v-for="item in toolNavItems"
                :key="item.path"
                :to="item.path"
                exact
                clickable v-ripple
                active-class="nav-active"
                class="rounded-borders q-mx-sm q-mb-xs"
                style="border-radius:8px;"
              >
                <q-item-section avatar>
                  <q-icon :name="item.icon" size="20px" />
                </q-item-section>
                <q-item-section>{{ item.label }}</q-item-section>
                <q-item-section v-if="item.badge" side>
                  <q-badge :label="item.badge" color="deep-orange-7" rounded style="font-size:11px;font-weight:800;min-width:20px" />
                </q-item-section>
              </q-item>
            </q-list>
          </template>

          <!-- Monitoring (visible to everyone) -->
          <q-separator dark class="q-my-xs" />
          <div class="nav-section-label">Monitoring</div>
          <q-list padding class="q-pt-none">
            <q-item
              clickable v-ripple
              class="rounded-borders q-mx-sm q-mb-xs"
              style="border-radius:8px;"
              @click="onScreenRecordingsClick"
            >
              <q-item-section avatar>
                <q-icon name="videocam" size="20px" />
              </q-item-section>
              <q-item-section>Operator Screen Recordings of CRM</q-item-section>
            </q-item>
          </q-list>

          <!-- Producers section (admin + producer_operator) -->
          <template v-if="showProducerNav">
            <q-separator dark class="q-my-xs" v-if="showPartnerNav || showToolsNav" />
            <div class="nav-section-label">Producers</div>
            <q-list padding class="q-pt-none">
              <q-item
                v-for="item in producerNavItems"
                :key="item.path"
                :to="item.path"
                exact
                clickable v-ripple
                active-class="nav-active"
                class="rounded-borders q-mx-sm q-mb-xs"
                style="border-radius:8px;"
              >
                <q-item-section avatar>
                  <q-icon :name="item.icon" size="20px" />
                </q-item-section>
                <q-item-section>{{ item.label }}</q-item-section>
              </q-item>
            </q-list>
          </template>

          <!-- Admin-only items -->
          <template v-if="authStore.isAdmin">
            <q-separator dark class="q-my-xs" />
            <div class="nav-section-label">Admin</div>
            <q-list padding class="q-pt-none">
              <q-item
                v-for="item in adminNavItems"
                :key="item.path"
                :to="item.path"
                exact
                clickable v-ripple
                active-class="nav-active"
                class="rounded-borders q-mx-sm q-mb-xs"
                style="border-radius:8px;"
              >
                <q-item-section avatar>
                  <q-icon :name="item.icon" size="20px" />
                </q-item-section>
                <q-item-section>{{ item.label }}</q-item-section>
              </q-item>
            </q-list>
          </template>

          <!-- Partner pipeline stats (only when partner nav visible) -->
          <div class="q-pa-md q-mt-sm" v-if="showPartnerNav && partnersStore.stats">
            <div class="text-caption text-grey-5 q-mb-sm" style="letter-spacing:1px;text-transform:uppercase;">Pipeline</div>
            <div v-for="(stage, key) in stageInfo" :key="key" class="row items-center justify-between q-mb-xs">
              <div class="row items-center q-gutter-xs">
                <div :style="`width:8px;height:8px;border-radius:50%;background:${stage.color}`" />
                <span class="text-caption text-grey-4">{{ stage.label }}</span>
              </div>
              <span class="text-caption text-white text-weight-bold">{{ partnersStore.stats?.by_stage?.[key] || 0 }}</span>
            </div>
          </div>

          <!-- Producer pipeline stats (only when producer nav visible) -->
          <div class="q-pa-md q-mt-sm" v-if="showProducerNav && producersStore.stats">
            <div class="text-caption text-grey-5 q-mb-sm" style="letter-spacing:1px;text-transform:uppercase;">Producers</div>
            <div class="row items-center justify-between q-mb-xs">
              <span class="text-caption text-grey-4">Onboarding</span>
              <span class="text-caption text-white text-weight-bold">{{ producersStore.stats.onboarding }}</span>
            </div>
            <div class="row items-center justify-between q-mb-xs">
              <span class="text-caption text-grey-4">Support</span>
              <span class="text-caption text-white text-weight-bold">{{ producersStore.stats.support }}</span>
            </div>
          </div>
        </q-scroll-area>

        <!-- Fixed bottom user info -->
        <div>
          <q-separator dark />
          <div class="q-pa-md row items-center q-gutter-sm">
            <q-avatar size="34px" :color="authStore.isAdmin ? 'primary' : 'secondary'" text-color="white">
              {{ userInitials }}
            </q-avatar>
            <div style="flex:1; min-width:0;">
              <div class="text-body2 text-white ellipsis">{{ authStore.fullName }}</div>
              <div class="text-caption text-grey-5 text-capitalize">{{ authStore.user?.role }}</div>
            </div>
            <q-btn flat round icon="logout" size="sm" color="grey-5" @click="logout" />
          </div>
        </div>

      </div>
    </q-drawer>

    <!-- Header -->
    <q-header elevated class="bg-white text-dark" style="border-bottom:1px solid #E0E0E0;">
      <q-toolbar>
        <q-btn flat round dense icon="menu" class="lt-md text-dark" @click="drawer = !drawer" />
        <q-toolbar-title class="text-dark text-weight-medium">{{ currentPageTitle }}</q-toolbar-title>
        <q-btn flat round icon="refresh" color="grey-6" size="sm" @click="refreshData" :loading="loading">
          <q-tooltip>Refresh data</q-tooltip>
        </q-btn>
      </q-toolbar>
    </q-header>

    <!-- Main content -->
    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import { useAuthStore } from 'src/stores/auth'
import { usePartnersStore } from 'src/stores/partners'
import { useProducersStore } from 'src/stores/producers'
import { useTasksStore } from 'src/stores/tasks'

const $q       = useQuasar()
const drawer   = ref(true)
const route    = useRoute()
const router   = useRouter()
const authStore     = useAuthStore()
const partnersStore = usePartnersStore()
const producersStore = useProducersStore()
const tasksStore     = useTasksStore()

const onScreenRecordingsClick = () => {
  $q.notify({
    type: 'negative',
    icon: 'lock',
    message: 'Access denied',
    caption: 'You do not have permission to view the screen recording storage.',
    timeout: 4000,
    position: 'top',
  })
}

const abandonedCount = ref(0)
const loading        = ref(false)

// Which sections to show — driven by permissions
const showPartnerNav  = computed(() => authStore.can('partners', 'view'))
const showProducerOnboardingNav = computed(() => authStore.can('producers_onboarding', 'view'))
const showProducerSupportNav    = computed(() => authStore.can('producers_support', 'view'))
const showProducerNav = computed(() => showProducerOnboardingNav.value || showProducerSupportNav.value)

const partnerNavItems = computed(() => {
  const items = []
  if (authStore.can('partners', 'view')) {
    items.push({ path: '/kanban',    label: 'Kanban Board', icon: 'view_kanban' })
    items.push({ path: '/partners',  label: 'All Partners', icon: 'people' })
    items.push({ path: '/sales',     label: 'Sales',        icon: 'shopping_bag' })
    if (authStore.isAdmin) {
      items.push({ path: '/abandoned', label: 'Abandoned',    icon: 'person_off',
        badge: abandonedCount.value > 0 ? abandonedCount.value : null })
    }
  }
  if (authStore.can('tasks', 'view')) {
    items.push({ path: '/tasks', label: 'Tasks', icon: 'task_alt',
      badge: tasksStore.openCount > 0 ? tasksStore.openCount : null })
  }
  if (authStore.can('analytics', 'view')) {
    items.push({ path: '/analytics', label: 'Analytics', icon: 'analytics' })
  }
  if (authStore.can('operator_activity', 'view')) {
    items.push({ path: '/operator-activity', label: 'Operator Activity', icon: 'timeline' })
  }
  if (authStore.can('reports', 'view') && !authStore.isOperator) {
    items.push({ path: '/ai-report', label: 'AI Report',  icon: 'auto_awesome' })
  }
  if (authStore.isAdmin) {
    items.push({ path: '/transcriptions', label: 'Transcriptions', icon: 'mic' })
  }
  items.push({ path: '/my-feedback', label: 'My Feedback', icon: 'rate_review' })
  if (authStore.isAdmin) {
    items.push({ path: '/call-quality', label: 'Call Quality', icon: 'analytics' })
  }
  return items
})

const toolNavItems = computed(() => [])

const showToolsNav = computed(() => false)

const producerNavItems = computed(() => {
  const items = []
  if (showProducerOnboardingNav.value) items.push({ path: '/producers/onboarding', label: 'Onboarding', icon: 'rocket_launch' })
  if (showProducerSupportNav.value)    items.push({ path: '/producers/support',    label: 'Support',    icon: 'support_agent' })
  if (showProducerOnboardingNav.value || showProducerSupportNav.value) {
    items.push({ path: '/producers/tasks', label: 'Tasks', icon: 'task_alt',
      badge: producersStore.openTasksCount > 0 ? producersStore.openTasksCount : null })
  }
  if (showProducerOnboardingNav.value || showProducerSupportNav.value) {
    items.push({ path: '/producers/abandoned', label: 'Abandoned', icon: 'person_off' })
  }
  if (showProducerOnboardingNav.value) items.push({ path: '/producers/analytics',  label: 'Analytics',  icon: 'analytics' })
  if (showProducerOnboardingNav.value) items.push({ path: '/producers/general-situation', label: 'General Situation', icon: 'leaderboard' })
  if (authStore.isAdmin) items.push({ path: '/producers/ai-report', label: 'AI Report',  icon: 'auto_awesome' })
  if (authStore.isAdmin) items.push({ path: '/producers/updates', label: 'Updates', icon: 'update' })
  return items
})

const adminNavItems = [
  { path: '/admin/users',          label: 'Users',          icon: 'manage_accounts' },
  { path: '/permissions',          label: 'Permissions',    icon: 'admin_panel_settings' },
  { path: '/admin/settings',       label: 'AI Settings',    icon: 'tune' },
  { path: '/admin/ai-operations',  label: 'Background Operations',  icon: 'monitor_heart' },
]

const stageInfo = {
  new:        { label: 'New',        color: '#F44336' },
  trained:    { label: 'Agreed to Create First Set', color: '#FFB300' },
  set_created:{ label: 'Set Created',color: '#29B6F6' },
  has_sale:   { label: 'Has Sale',   color: '#43A047' },
  no_answer:  { label: 'Dead (No Answer)', color: '#546E7A' },
  declined:   { label: 'Dead (Declined)',  color: '#B71C1C' },
  no_sales:   { label: 'Dead (No Sales)', color: '#E65100' },
}

const pageTitles = {
  '/kanban':            'Kanban Board',
  '/partners':          'All Partners',
  '/sales':             'Sales',
  '/analytics':         'Analytics',
  '/operators':         'Operator Stats',
  '/operator-activity': 'Operator Activity',
  '/tasks':             'Tasks',
  '/abandoned':         'Abandoned Partners',
  '/ai-report':         'AI Report',
  '/producers/onboarding': 'Producer Onboarding',
  '/producers/support':    'Producer Support',
  '/producers/tasks':      'Producer Tasks',
  '/producers/abandoned':  'Producer Abandoned',
  '/producers/analytics':  'Producer Analytics',
  '/producers/ai-report':  'Producer AI Report',
  '/producers/updates':    'Producer Updates',
  '/producers/general-situation': 'General Situation',
  '/transcriptions':       'Transcriptions',
  '/call-quality':         'AI Call Quality',
  '/my-feedback':          'My Feedback',
  '/admin/users':          'User Management',
  '/admin/settings':       'AI Settings',
  '/admin/ai-operations':  'Background Operations',
  '/permissions':          'Access Permissions',
}

const currentPageTitle = computed(() => {
  if (route.path.startsWith('/partners/'))  return 'Partner Details'
  if (/^\/producers\/\d+$/.test(route.path)) return 'Producer Details'
  return pageTitles[route.path] || 'CRM'
})

const userInitials = computed(() => {
  const name = authStore.fullName
  if (!name) return '?'
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
})

const logout = () => {
  authStore.logout()
  router.push('/login')
}

const refreshData = async () => {
  loading.value = true
  try {
    if (showPartnerNav.value)  await partnersStore.fetchStats()
    if (showProducerNav.value) await producersStore.fetchStats()
    if (route.path === '/kanban')               await partnersStore.fetchKanban()
    if (route.path === '/partners')             await partnersStore.fetchPartners()
    if (route.path === '/producers/onboarding') await producersStore.fetchKanban('onboarding')
    if (route.path === '/producers/support')    await producersStore.fetchKanban('support')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!authStore.user) await authStore.fetchMe()
  if (authStore.can('partners', 'view')) {
    partnersStore.fetchStats()
    partnersStore.fetchUsers()
    partnersStore.fetchAbandonedCount().then(c => { abandonedCount.value = c })
  }
  if (authStore.can('tasks', 'view')) {
    tasksStore.refreshOpenCount()
  }
  if (authStore.can('producers_onboarding', 'view') || authStore.can('producers_support', 'view')) {
    producersStore.fetchStats()
    producersStore.fetchUsers()
    producersStore.refreshOpenTasksCount()
  }
})
</script>

<style scoped>
.nav-active {
  background: rgba(46, 125, 50, 0.3) !important;
  color: #81C784 !important;
}
.nav-section-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: #616161;
  padding: 8px 16px 2px;
}
</style>
