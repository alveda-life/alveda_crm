<template>
  <q-card
    flat
    class="producer-card cursor-pointer"
    style="background:white; box-shadow:0 2px 8px rgba(0,0,0,0.07); border-radius:10px;"
    @click="$emit('click')"
  >
    <q-card-section class="q-pa-sm q-pb-xs">
      <!-- Header row -->
      <div class="row items-start justify-between q-mb-xs">
        <div style="flex:1;min-width:0;">
          <div class="name-tag" :style="`background:${activityBg};color:${activityText};`">
            {{ producer.name }}
          </div>
          <div v-if="producer.company" class="text-caption text-grey-6 ellipsis">{{ producer.company }}</div>
          <!-- Plan date + product categories -->
          <div class="row items-center q-mt-xs" style="gap:5px;flex-wrap:wrap;">
            <div v-if="producer.planned_connection_date" class="row items-center" style="gap:3px;">
              <q-icon name="event_available" size="11px" color="teal-6" />
              <span style="font-size:11px;color:#00897B;font-weight:600;">{{ fmtDate(producer.planned_connection_date) }}</span>
            </div>
            <span v-for="pt in productTypes" :key="pt"
              style="font-size:10px;background:#EDE7F6;color:#4527A0;border-radius:4px;padding:1px 5px;font-weight:600;">
              {{ pt }}
            </span>
          </div>
        </div>

        <!-- Card menu -->
        <q-btn flat round dense icon="more_vert" size="xs" color="grey-5" @click.stop>
          <q-menu>
            <q-list dense style="min-width:180px;">

              <!-- Assign operator -->
              <q-item-label header class="text-caption">Assign to</q-item-label>
              <q-item
                v-for="user in users" :key="user.id"
                clickable v-close-popup
                :disable="user.id === producer.assigned_to"
                @click.stop="$emit('assign', { producerId: producer.id, userId: user.id, userDetail: user })"
              >
                <q-item-section avatar>
                  <q-avatar size="22px" :color="user.id === producer.assigned_to ? 'primary' : 'grey-4'" text-color="white" style="font-size:10px;">
                    {{ initials(user) }}
                  </q-avatar>
                </q-item-section>
                <q-item-section>{{ user.full_name || user.username }}</q-item-section>
                <q-item-section side v-if="user.id === producer.assigned_to">
                  <q-icon name="check" size="14px" color="primary" />
                </q-item-section>
              </q-item>

              <q-separator spaced />

              <!-- Move to other funnel -->
              <q-item-label header class="text-caption">Move to funnel</q-item-label>
              <q-item
                v-if="activeFunnel === 'onboarding'"
                clickable v-close-popup
                @click.stop="$emit('move-funnel', { producerId: producer.id, targetFunnel: 'support', targetStage: 'agreed' })"
              >
                <q-item-section avatar>
                  <q-icon name="support_agent" size="18px" color="teal" />
                </q-item-section>
                <q-item-section>Move to Support</q-item-section>
              </q-item>
              <q-item
                v-else
                clickable v-close-popup
                @click.stop="$emit('move-funnel', { producerId: producer.id, targetFunnel: 'onboarding', targetStage: 'interest' })"
              >
                <q-item-section avatar>
                  <q-icon name="rocket_launch" size="18px" color="blue" />
                </q-item-section>
                <q-item-section>Move to Onboarding</q-item-section>
              </q-item>

            </q-list>
          </q-menu>
        </q-btn>
      </div>

      <!-- Task / comment counters + follow-up (support only) -->
      <div class="row items-center q-gutter-xs" style="font-size:11px;flex-wrap:wrap;">
        <!-- Tasks -->
        <span v-if="producer.open_tasks_count > 0" class="row items-center" style="color:#E53935;">
          <q-icon name="assignment_late" size="13px" class="q-mr-xs" />
          {{ producer.open_tasks_count }} open
        </span>
        <span v-else-if="producer.tasks_count > 0" class="row items-center" style="color:#43A047;">
          <q-icon name="task_alt" size="13px" class="q-mr-xs" />
          {{ producer.tasks_count }} tasks
        </span>
        <!-- Comments: count + age -->
        <span v-if="producer.comments_count > 0" class="row items-center" :style="lastCommentAgeStyle">
          <q-icon name="chat_bubble_outline" size="12px" class="q-mr-xs" />
          {{ producer.comments_count }}
          <span v-if="lastCommentAge !== null" style="margin-left:3px;opacity:0.75;">· {{ lastCommentAgeLabel }}</span>
          <q-tooltip>Last comment: {{ lastCommentDate }}</q-tooltip>
        </span>
        <span v-else class="row items-center" style="color:#BDBDBD;">
          <q-icon name="chat_bubble_outline" size="12px" class="q-mr-xs" />
          no comments
        </span>
        <!-- Follow-up: support funnel only -->
        <template v-if="activeFunnel === 'support'">
          <span v-if="isFollowUpOverdue" class="row items-center" style="color:#C62828;font-weight:600;">
            <q-icon name="event_busy" size="12px" class="q-mr-xs" />
            Follow-up!
          </span>
          <span v-else-if="isFollowUpSoon" class="row items-center" style="color:#E65100;">
            <q-icon name="event" size="12px" class="q-mr-xs" />
            {{ producer.control_date }}
          </span>
        </template>
      </div>
    </q-card-section>

    <!-- Footer: assigned operator + coop potential -->
    <q-card-section class="q-pa-sm q-pt-xs">
      <div class="row items-center justify-between">
        <div class="row items-center" style="gap:4px;">
          <template v-if="producer.assigned_to_detail">
            <q-avatar size="20px" color="primary" text-color="white" style="font-size:9px;">
              {{ initials(producer.assigned_to_detail) }}
            </q-avatar>
            <span style="font-size:11px;color:#616161;">
              {{ producer.assigned_to_detail.full_name || producer.assigned_to_detail.username }}
            </span>
          </template>
          <span v-else style="font-size:11px;color:#BDBDBD;">Unassigned</span>
        </div>
        <div class="row items-center" style="gap:6px;">
          <!-- Control date -->
          <span v-if="producer.control_date" :style="controlDateStyle" style="font-size:10px;font-weight:600;">
            {{ controlDateLabel }}
            <q-tooltip>Follow-up: {{ producer.control_date }}</q-tooltip>
          </span>
          <!-- Cooperation potential dot -->
          <div v-if="producer.cooperation_potential"
            :style="`width:7px;height:7px;border-radius:50%;background:${coopDotColor(producer.cooperation_potential)};`"
            style="flex-shrink:0;">
            <q-tooltip>Coop: {{ producer.cooperation_potential_display || producer.cooperation_potential }}</q-tooltip>
          </div>
          <div :style="`width:8px;height:8px;border-radius:50%;background:${stageColor};flex-shrink:0;`" />
        </div>
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  producer:    { type: Object, required: true },
  stageColor:  { type: String, default: '#9E9E9E' },
  users:       { type: Array, default: () => [] },
  activeFunnel:{ type: String, default: 'onboarding' },
})
defineEmits(['click', 'assign', 'move-funnel'])

const initials = (user) => {
  if (!user) return '?'
  return (user.full_name || user.username || '?')
    .split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

const coopDotColor = (p) => ({
  strong:      '#43A047',
  medium:      '#1E88E5',
  weak:        '#FF7043',
  no_response: '#9E9E9E',
}[p] || '#9E9E9E')

const lastCommentAge = computed(() => {
  if (!props.producer.last_comment_at) return null
  return Math.floor((Date.now() - new Date(props.producer.last_comment_at)) / 86400000)
})

const lastCommentDate = computed(() => {
  if (!props.producer.last_comment_at) return ''
  return new Date(props.producer.last_comment_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
})

const lastCommentAgeLabel = computed(() => {
  const d = lastCommentAge.value
  if (d === null) return ''
  if (d === 0) return 'today'
  if (d === 1) return '1d ago'
  if (d < 7)  return `${d}d ago`
  if (d < 30) return `${Math.floor(d / 7)}w ago`
  return `${Math.floor(d / 30)}mo ago`
})

const lastCommentAgeStyle = computed(() => {
  const d = lastCommentAge.value
  if (d === null) return ''
  if (d >= 14) return 'color:#C62828;font-weight:600;'
  if (d >= 7)  return 'color:#E65100;'
  return 'color:#757575;'
})

const activityBg = computed(() => {
  const d = lastCommentAge.value
  if (d === null) return '#F5F5F5'   // no comments — grey
  if (d <= 3)  return '#E8F5E9'      // 1–3 days — green
  if (d <= 7)  return '#FFFDE7'      // 4–7 days — yellow
  return '#FFEBEE'                   // 8+ days — red
})

const activityText = computed(() => {
  const d = lastCommentAge.value
  if (d === null) return '#9E9E9E'
  if (d <= 3)  return '#2E7D32'
  if (d <= 7)  return '#F57F17'
  return '#C62828'
})

const productTypes = computed(() => {
  const v = props.producer.product_type || ''
  return v ? v.split(',').map(s => s.trim()).filter(Boolean) : []
})

const fmtDate = (iso) => {
  if (!iso) return ''
  const d = new Date(iso + 'T12:00:00')
  const month = d.toLocaleDateString('en-US', { month: 'short' })
  const week  = Math.ceil(d.getDate() / 7)
  return `${month} W${week}`
}

const today = new Date(new Date().toDateString())
const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1)

const isFollowUpOverdue = computed(() => {
  if (!props.producer.control_date) return false
  return new Date(props.producer.control_date) < today
})

const isFollowUpSoon = computed(() => {
  if (!props.producer.control_date) return false
  const d = new Date(props.producer.control_date)
  return d >= today && d <= tomorrow
})

const controlDateLabel = computed(() => {
  if (!props.producer.control_date) return ''
  const d = new Date(props.producer.control_date + 'T12:00:00')
  const diff = Math.floor((d - today) / 86400000)
  if (diff < 0)  return `↑ ${d.toLocaleDateString('en-US', { day: 'numeric', month: 'short' })}`
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  return d.toLocaleDateString('en-US', { day: 'numeric', month: 'short' })
})

const controlDateStyle = computed(() => {
  if (!props.producer.control_date) return ''
  const d = new Date(props.producer.control_date + 'T12:00:00')
  const diff = Math.floor((d - today) / 86400000)
  if (diff < 0)  return 'color:#C62828;'
  if (diff === 0) return 'color:#E65100;'
  if (diff <= 2) return 'color:#F57F17;'
  return 'color:#78909C;'
})
</script>

<style scoped>
.producer-card { transition: transform 0.15s, box-shadow 0.15s; }
.producer-card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,0.12) !important; }
.name-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
