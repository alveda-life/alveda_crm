<template>
  <q-card
    flat
    :class="cardClass"
    style="background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.07);"
  >
    <div class="card-inner">

      <!-- Row 1: name + reg date + menu -->
      <div class="row items-start justify-between" style="gap:2px;">
        <div style="flex:1;min-width:0;">
          <div class="name-tag" :style="`background:${nameColor(partner).bg};color:${nameColor(partner).text}`">
            {{ partner.name }}<span v-if="partner.created_at" style="font-size:9px;font-weight:400;opacity:0.55;margin-left:5px;">{{ fmtDate(partner.created_at) }}</span>
          </div>
        </div>
        <q-btn flat round dense icon="more_vert" size="xs" color="grey-5" style="margin-top:-2px;margin-right:-4px;" @click.stop>
          <q-menu>
            <q-list dense style="min-width:170px;">
              <q-item-label header class="text-caption">Assign to</q-item-label>
              <q-item
                v-for="user in users" :key="user.id"
                clickable v-close-popup
                :disable="user.id === partner.assigned_to"
                @click.stop="$emit('assign', { partnerId: partner.id, userId: user.id, userDetail: user })"
              >
                <q-item-section avatar>
                  <q-avatar size="22px" :color="user.id === partner.assigned_to ? 'primary' : 'grey-4'" text-color="white" style="font-size:10px;">
                    {{ userInitials(user) }}
                  </q-avatar>
                </q-item-section>
                <q-item-section>{{ user.full_name || user.username }}</q-item-section>
                <q-item-section side v-if="user.id === partner.assigned_to">
                  <q-icon name="check" size="14px" color="primary" />
                </q-item-section>
              </q-item>
              <q-separator spaced />
              <q-item-label header class="text-caption">Move to stage</q-item-label>
              <q-item
                v-for="stage in stageOptions" :key="stage.value"
                clickable v-close-popup
                :disable="stage.value === partner.stage"
                @click.stop="$emit('stage-change', { partnerId: partner.id, newStage: stage.value })"
              >
                <q-item-section avatar>
                  <div :style="`width:8px;height:8px;border-radius:50%;background:${stage.color}`" />
                </q-item-section>
                <q-item-section>{{ stage.label }}</q-item-section>
                <q-item-section side v-if="stage.value === partner.stage">
                  <q-icon name="check" size="14px" color="primary" />
                </q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
      </div>

      <!-- Row 2: phone · city · gender · exp — one compact line -->
      <div class="row items-center" style="gap:6px;font-size:10px;color:#9E9E9E;margin-top:2px;flex-wrap:wrap;">
        <span v-if="partner.phone">{{ partner.phone }}</span>
        <span v-if="partner.city || partner.state">
          <q-icon name="location_on" size="10px" />{{ [partner.city, partner.state].filter(Boolean).join(', ') }}
        </span>
        <span v-if="partner.gender">{{ partner.gender_display }}</span>
        <span v-if="partner.experience_years != null">
          <q-icon name="workspace_premium" size="10px" />{{ partner.experience_years }}y
        </span>
      </div>

      <!-- Row 3: chips + control date inline -->
      <div class="row items-center q-gutter-xs" style="margin-top:4px;flex-wrap:wrap;">
        <q-chip dense size="xs" :class="`chip-type-${partner.type}`">{{ partner.type_display }}</q-chip>
        <q-chip v-if="partner.category" dense size="xs" :class="`chip-${partner.category}`">{{ partner.category_display }}</q-chip>
        <q-chip dense size="xs" :color="statusColor(partner.status)" text-color="white">{{ partner.status_display || partner.status }}</q-chip>
        <q-chip dense size="xs"
          :style="partner.whatsapp_added
            ? 'background:#E8F5E9;color:#2E7D32;border:1px solid #A5D6A7;'
            : 'background:transparent;color:#B71C1C;border:1px solid #EF9A9A;'"
        ><q-icon name="whatsapp" size="11px" class="q-mr-xs" />{{ partner.whatsapp_added ? 'WA' : 'WA?' }}</q-chip>
        <!-- Control date inline -->
        <span v-if="partner.control_date"
          :style="isOverdue(partner.control_date)
            ? 'background:#FFEBEE;color:#C62828;border:1px solid #FFCDD2;border-radius:5px;padding:1px 6px;font-size:10px;font-weight:600;display:inline-flex;align-items:center;gap:3px;'
            : isToday(partner.control_date)
              ? 'background:#FFF3E0;color:#E65100;border:1px solid #FFCC80;border-radius:5px;padding:1px 6px;font-size:10px;font-weight:600;display:inline-flex;align-items:center;gap:3px;'
              : 'background:#E3F2FD;color:#0277BD;border:1px solid #BBDEFB;border-radius:5px;padding:1px 6px;font-size:10px;font-weight:600;display:inline-flex;align-items:center;gap:3px;'"
        >
          <q-icon :name="isOverdue(partner.control_date) ? 'warning' : isToday(partner.control_date) ? 'today' : 'event'" size="10px" />
          {{ isToday(partner.control_date) ? 'Today' : formatControlDate(partner.control_date) }}
        </span>
      </div>

      <!-- Row 4: stats — compact 3-col -->
      <div class="row justify-between" style="margin-top:5px;padding-top:5px;border-top:1px solid #F5F5F5;">
        <div class="col text-center">
          <div style="font-size:13px;font-weight:700;color:#2E7D32;line-height:1.2;">₹{{ formatMoney(partner.paid_orders_sum) }}</div>
          <div style="font-size:9px;color:#9E9E9E;">{{ partner.paid_orders_count }} paid</div>
        </div>
        <div class="col text-center" style="border-left:1px solid #F5F5F5;">
          <div style="font-size:13px;font-weight:700;color:#1565C0;line-height:1.2;">{{ partner.medical_sets_count }}</div>
          <div style="font-size:9px;color:#9E9E9E;">Sets</div>
        </div>
        <div class="col text-center" style="border-left:1px solid #F5F5F5;">
          <div style="font-size:13px;font-weight:700;color:#424242;line-height:1.2;">
            {{ partner.contacts_count }}<span v-if="partner.missed_calls_count" style="font-size:9px;color:#E53935;"> -{{ partner.missed_calls_count }}</span>
          </div>
          <div style="font-size:9px;color:#9E9E9E;">Calls</div>
        </div>
      </div>

      <!-- Row 5: footer — last contact + operator -->
      <div class="row items-center justify-between" style="margin-top:4px;padding-top:4px;border-top:1px solid #F5F5F5;">
        <span style="font-size:10px;color:#9E9E9E;">
          <template v-if="partner.last_contact_date">
            <q-icon name="access_time" size="11px" /> {{ timeAgo(partner.last_contact_date) }}
          </template>
          <template v-else><span style="color:#BDBDBD;">No calls</span></template>
        </span>
        <div v-if="partner.assigned_to_detail"
          class="operator-badge"
          :style="`background:${opColor(partner.assigned_to).bg};color:${opColor(partner.assigned_to).text}`">
          <q-avatar size="16px" text-color="white" style="font-size:7px;"
            :style="`background:${opColor(partner.assigned_to).avatar}`">
            {{ userInitials(partner.assigned_to_detail) }}
          </q-avatar>
          <span>{{ partner.assigned_to_detail.full_name?.split(' ')[0] }}</span>
        </div>
        <div v-else class="operator-badge operator-badge--empty">
          <q-icon name="person_add" size="11px" />
          <span>Assign</span>
        </div>
      </div>

    </div>
  </q-card>
</template>

<script setup>
import { computed } from 'vue'
import { nameColor, opColor } from 'src/utils/partnerColors'

const props = defineProps({
  partner: { type: Object, required: true },
  stageColor: { type: String, default: '#9E9E9E' },
  users: { type: Array, default: () => [] },
})

defineEmits(['stage-change', 'assign'])

const userInitials = (user) => {
  const name = user.full_name || user.username || ''
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

const cardClass = computed(() => {
  if (props.partner.stage === 'trained' &&
      !props.partner.medical_sets_count &&
      !props.partner.paid_orders_count) {
    return 'partner-card stage-trained-inactive'
  }
  return `partner-card stage-${props.partner.stage}`
})

const stageOptions = [
  { label: 'New',        value: 'new',        color: '#F44336' },
  { label: 'Agreed to Create First Set', value: 'trained', color: '#FFB300' },
  { label: 'Set Created',value: 'set_created',color: '#0277BD' },
  { label: 'Has Sale',   value: 'has_sale',   color: '#2E7D32' },
  { label: 'Dead (No Answer)', value: 'no_answer', color: '#546E7A' },
  { label: 'Dead (Declined)',  value: 'declined',  color: '#B71C1C' },
  { label: 'Dead (No Sales)', value: 'no_sales',  color: '#E65100' },
]

const statusColor = (s) => ({ new: 'grey', in_support: 'blue', closed: 'red' }[s] || 'grey')

const todayStr = () => new Date().toISOString().slice(0, 10)
const isToday = (dateStr) => dateStr === todayStr()
const isOverdue = (dateStr) => dateStr && dateStr < todayStr()

const fmtDate = (isoStr) => {
  const d = new Date(isoStr)
  return d.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })
}

const formatControlDate = (dateStr) => {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { day: 'numeric', month: 'short' })
}

const formatMoney = (val) => {
  if (!val || Number(val) === 0) return '0'
  const n = Number(val)
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return n.toLocaleString('en-US', { minimumFractionDigits: 0 })
}

const timeAgo = (dateStr) => {
  const now = new Date()
  const date = new Date(dateStr)
  const diff = Math.floor((now - date) / 86400000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Yesterday'
  if (diff < 7) return `${diff}d ago`
  if (diff < 30) return `${Math.floor(diff / 7)}w ago`
  return `${Math.floor(diff / 30)}mo ago`
}
</script>

<style scoped>
.card-inner { padding: 7px 9px 6px; }
.name-tag {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 6px;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.operator-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border-radius: 20px;
  padding: 1px 6px 1px 3px;
  font-size: 10px;
  font-weight: 600;
}
.operator-badge--empty {
  background: #F5F5F5;
  color: #9E9E9E;
}
</style>
