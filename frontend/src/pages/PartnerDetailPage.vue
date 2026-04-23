<template>
  <q-page class="q-pa-md">

    <div v-if="!partner" class="flex flex-center" style="min-height:300px;">
      <q-spinner-dots color="primary" size="48px" />
    </div>

    <div v-else>
      <!-- Breadcrumb + actions -->
      <div class="row items-center justify-between q-mb-md">
        <div class="row items-center q-gutter-xs">
          <q-btn flat dense icon="arrow_back" color="grey-7" @click="goBack" />
          <q-breadcrumbs>
            <q-breadcrumbs-el label="Partners" to="/partners" />
            <q-breadcrumbs-el :label="partner.name" />
          </q-breadcrumbs>
        </div>
        <div class="row q-gutter-sm">
          <q-btn v-if="!isOperator" flat icon="edit" label="Edit" color="grey-7" @click="showEditDialog = true" />
          <q-btn unelevated icon="add_comment" label="Add Record" color="primary"
            @click="showContactDialog = true" style="border-radius:8px;" />
        </div>
      </div>

      <div class="row q-gutter-md">
        <!-- LEFT column -->
        <div style="min-width:300px; max-width:340px; flex-shrink:0;">

          <!-- Identity card -->
          <q-card flat bordered style="border-radius:12px;" class="q-mb-md">
            <q-card-section>
              <div class="q-mb-md">
                <div class="row items-center q-gutter-sm q-mb-xs">
                  <div class="detail-name-tag"
                    :style="`background:${nameColor(partner).bg};color:${nameColor(partner).text}`">
                    {{ partner.name }}
                  </div>
                  <span v-if="partner.created_at" style="font-size:11px;color:#BDBDBD;">
                    <q-icon name="calendar_today" size="11px" />
                    {{ new Date(partner.created_at).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' }) }}
                  </span>
                </div>
                <div class="row q-gutter-xs q-mt-sm">
                  <q-chip dense size="sm" :class="`chip-type-${partner.type}`">
                    {{ partner.type_display }}
                  </q-chip>
                  <q-chip v-if="partner.category" dense size="sm" :class="`chip-${partner.category}`">
                    {{ partner.category_display }}
                  </q-chip>
                </div>
              </div>

              <!-- Status -->
              <div class="q-mb-sm">
                <div class="field-label q-mb-xs">
                  Status
                  <q-icon v-if="isOperator && !hasOwnActivity" name="lock" size="11px" color="grey-5" />
                </div>
                <div class="row q-gutter-xs">
                  <q-btn
                    v-for="s in statusOptions" :key="s.value"
                    :outline="partner.status !== s.value"
                    :unelevated="partner.status === s.value"
                    :color="s.color"
                    size="sm"
                    :label="s.label"
                    dense
                    :disable="isOperator && !hasOwnActivity"
                    style="border-radius:6px;"
                    @click="changeStatus(s.value)"
                  >
                    <q-tooltip v-if="isOperator && !hasOwnActivity">
                      Add an Activity record before changing status
                    </q-tooltip>
                  </q-btn>
                </div>
              </div>

              <q-separator class="q-my-sm" />

              <!-- Control date -->
              <div class="q-mb-sm">
                <div class="field-label q-mb-xs">
                  <q-icon name="event" size="12px" /> Follow-up Date
                  <q-icon v-if="isOperator && !hasOwnActivity" name="lock" size="11px" color="grey-5" />
                </div>
                <q-input
                  :model-value="partner.control_date"
                  outlined dense
                  type="date"
                  :max="maxControlDate"
                  :readonly="isOperator && !hasOwnActivity"
                  :class="isOverdue ? 'overdue-date' : ''"
                  @update:model-value="saveControlDate"
                >
                  <q-tooltip v-if="isOperator && !hasOwnActivity">
                    Add an Activity record before changing follow-up date
                  </q-tooltip>
                </q-input>
                <div v-if="isOverdue" class="text-caption text-negative q-mt-xs">
                  <q-icon name="warning" size="12px" /> Overdue
                </div>
              </div>

              <q-separator class="q-my-sm" />

              <!-- Funnel Stage -->
              <div class="q-mb-md">
                <div class="field-label q-mb-xs">
                  Funnel Stage
                  <q-icon v-if="stageSelectDisabled" name="lock" size="11px" color="grey-5" />
                </div>
                <q-select
                  :model-value="partner.stage"
                  :options="visibleStageOptions"
                  emit-value map-options
                  outlined dense
                  :disable="stageSelectDisabled"
                  @update:model-value="changeStage"
                >
                  <q-tooltip v-if="stageSelectDisabled">
                    Add a call record to advance the partner, or close the card / confirm there are no calls to move to a Dead stage.
                  </q-tooltip>
                </q-select>
              </div>

              <div class="info-row">
                <q-icon name="phone" color="grey-5" size="16px" />
                <span>{{ partner.phone || '—' }}</span>
              </div>
              <div class="info-row">
                <q-icon name="fingerprint" color="grey-5" size="16px" />
                <span>{{ partner.user_id || '—' }}</span>
                <q-badge color="grey-3" text-color="grey-7" class="q-ml-xs">Platform ID</q-badge>
              </div>
              <div class="info-row" v-if="partner.referred_by">
                <q-icon name="person_add" color="grey-5" size="16px" />
                <span>Referred by: {{ partner.referred_by }}</span>
              </div>
              <!-- Operator — inline assign -->
              <div class="q-mb-sm">
                <div class="field-label q-mb-xs">Responsible operator</div>
                <div class="operator-pill" :class="partner.assigned_to_detail ? '' : 'operator-pill--empty'">
                  <template v-if="partner.assigned_to_detail">
                    <q-avatar size="28px" color="primary" text-color="white" style="font-size:11px;flex-shrink:0;">
                      {{ (partner.assigned_to_detail.full_name || partner.assigned_to_detail.username).split(' ').map(n=>n[0]).join('').toUpperCase().slice(0,2) }}
                    </q-avatar>
                    <div style="flex:1;min-width:0;">
                      <div style="font-size:13px;font-weight:600;color:#212121;line-height:1.2;">
                        {{ partner.assigned_to_detail.full_name || partner.assigned_to_detail.username }}
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
                      <template v-if="isOperator">
                        <q-item
                          clickable v-close-popup
                          :disable="authStore.user?.id === partner.assigned_to"
                          @click="assignOperator(authStore.user)"
                        >
                          <q-item-section avatar>
                            <q-avatar size="26px" color="primary" text-color="white" style="font-size:10px;">
                              {{ (authStore.user?.full_name || authStore.user?.username || '').split(' ').map(n=>n[0]).join('').toUpperCase().slice(0,2) }}
                            </q-avatar>
                          </q-item-section>
                          <q-item-section>Assign to me</q-item-section>
                          <q-item-section side v-if="authStore.user?.id === partner.assigned_to">
                            <q-icon name="check" size="14px" color="primary" />
                          </q-item-section>
                        </q-item>
                      </template>
                      <template v-else>
                        <q-item
                          v-for="user in store.users"
                          :key="user.id"
                          clickable v-close-popup
                          :disable="user.id === partner.assigned_to"
                          @click="assignOperator(user)"
                        >
                          <q-item-section avatar>
                            <q-avatar size="26px" :color="user.id === partner.assigned_to ? 'primary' : 'grey-4'" text-color="white" style="font-size:10px;">
                              {{ (user.full_name || user.username).split(' ').map(n=>n[0]).join('').toUpperCase().slice(0,2) }}
                            </q-avatar>
                          </q-item-section>
                          <q-item-section>{{ user.full_name || user.username }}</q-item-section>
                          <q-item-section side v-if="user.id === partner.assigned_to">
                            <q-icon name="check" size="14px" color="primary" />
                          </q-item-section>
                        </q-item>
                      </template>
                    </q-list>
                  </q-menu>
                </div>
              </div>

              <q-separator class="q-my-sm" />

              <!-- WhatsApp channel -->
              <div class="q-mb-sm">
                <q-checkbox
                  :model-value="partner.whatsapp_added"
                  color="green-8"
                  @update:model-value="saveWhatsapp"
                >
                  <span class="text-caption" style="font-weight:600;color:#212121;">
                    <q-icon name="whatsapp" size="14px" :color="partner.whatsapp_added ? 'green-8' : 'grey-5'" class="q-mr-xs" />
                    Added to WhatsApp channel
                  </span>
                </q-checkbox>
              </div>

              <q-separator class="q-my-sm" />

              <!-- Profile info — inline editable -->
              <div class="row items-center justify-between q-mb-sm">
                <div class="field-label">Profile Info</div>
                <q-btn v-if="!editProfile && !profileFullyLockedForOperator" flat dense round icon="edit" size="xs" color="grey-5"
                  @click="startEditProfile" />
              </div>

              <div v-if="!editProfile" class="row q-col-gutter-xs">
                <!-- Gender -->
                <div class="col-6">
                  <div :class="['profile-field', !partner.gender ? 'profile-field--empty' : '']"
                    @click="startEditProfile">
                    <q-icon name="person" size="13px" :color="partner.gender ? 'grey-6' : 'negative'" />
                    <span v-if="partner.gender" class="text-caption">{{ partner.gender_display }}</span>
                    <span v-else class="text-caption text-negative">+ Gender</span>
                  </div>
                </div>
                <!-- Experience -->
                <div class="col-6">
                  <div :class="['profile-field', partner.experience_years == null ? 'profile-field--empty' : '']"
                    @click="startEditProfile">
                    <q-icon name="workspace_premium" size="13px" :color="partner.experience_years != null ? 'grey-6' : 'negative'" />
                    <span v-if="partner.experience_years != null" class="text-caption">{{ partner.experience_years }} yrs</span>
                    <span v-else class="text-caption text-negative">+ Experience</span>
                  </div>
                </div>
                <!-- City -->
                <div class="col-6">
                  <div :class="['profile-field', !partner.city ? 'profile-field--empty' : '']"
                    @click="startEditProfile">
                    <q-icon name="location_city" size="13px" :color="partner.city ? 'grey-6' : 'negative'" />
                    <span v-if="partner.city" class="text-caption">{{ partner.city }}</span>
                    <span v-else class="text-caption text-negative">+ City</span>
                  </div>
                </div>
                <!-- State -->
                <div class="col-6">
                  <div :class="['profile-field', !partner.state ? 'profile-field--empty' : '']"
                    @click="startEditProfile">
                    <q-icon name="map" size="13px" :color="partner.state ? 'grey-6' : 'negative'" />
                    <span v-if="partner.state" class="text-caption">{{ partner.state }}</span>
                    <span v-else class="text-caption text-negative">+ State</span>
                  </div>
                </div>
              </div>

              <div v-else class="q-mt-xs">
                <div v-if="isOperator" class="text-caption text-grey-7 q-mb-sm" style="background:#FFF8E1; border-left:3px solid #FFB300; padding:6px 10px; border-radius:4px;">
                  <q-icon name="info" size="13px" /> You can fill empty fields once. Filled fields cannot be changed.
                </div>
                <div class="row q-col-gutter-sm">
                  <div class="col-6">
                    <div class="field-label q-mb-xs">Gender</div>
                    <q-select v-model="profileForm.gender" :options="genderOptions"
                      emit-value map-options outlined dense :clearable="!isProfileFieldLocked('gender')" placeholder="—"
                      :readonly="isProfileFieldLocked('gender')" :disable="isProfileFieldLocked('gender')" />
                  </div>
                  <div class="col-6">
                    <div class="field-label q-mb-xs">Experience (yrs)</div>
                    <q-input v-model.number="profileForm.experience_years" outlined dense
                      type="number" min="0" max="60" placeholder="—"
                      :readonly="isProfileFieldLocked('experience_years')" :disable="isProfileFieldLocked('experience_years')" />
                  </div>
                  <div class="col-6">
                    <div class="field-label q-mb-xs">State</div>
                    <q-select
                      v-model="profileForm.state"
                      :options="profileStateOptions"
                      use-input input-debounce="0"
                      @filter="filterProfileStates"
                      outlined dense :clearable="!isProfileFieldLocked('state')"
                      placeholder="Search..."
                      :readonly="isProfileFieldLocked('state')" :disable="isProfileFieldLocked('state')"
                      @update:model-value="profileForm.city = ''"
                    />
                  </div>
                  <div class="col-6">
                    <div class="field-label q-mb-xs">City</div>
                    <q-select
                      v-model="profileForm.city"
                      :options="profileCityOptions"
                      use-input input-debounce="0"
                      @filter="filterProfileCities"
                      outlined dense :clearable="!isProfileFieldLocked('city')"
                      placeholder="Search..."
                      :readonly="isProfileFieldLocked('city')" :disable="isProfileFieldLocked('city')"
                    />
                  </div>
                </div>
                <div class="row q-gutter-sm q-mt-sm">
                  <q-btn unelevated color="primary" label="Save" size="sm"
                    style="border-radius:6px;" :loading="profileSaving" @click="saveProfile" />
                  <q-btn flat color="grey-7" label="Cancel" size="sm" @click="editProfile = false" />
                </div>
              </div>
            </q-card-section>
          </q-card>

          <!-- Stats card -->
          <q-card flat bordered style="border-radius:12px;" class="q-mb-md">
            <q-card-section>
              <div class="text-subtitle2 text-weight-bold q-mb-md">Statistics</div>
              <div class="row q-col-gutter-sm">
                <div class="col-6">
                  <div class="stat-tile">
                    <q-icon name="medical_services" color="blue" size="20px" />
                    <div class="text-h6 text-weight-bold">{{ partner.medical_sets_count }}</div>
                    <div class="stat-tile-label">Med. Sets</div>
                  </div>
                </div>
                <div class="col-6">
                  <div class="stat-tile">
                    <q-icon name="shopping_cart" color="orange" size="20px" />
                    <div class="text-h6 text-weight-bold">{{ partner.orders_count }}</div>
                    <div class="stat-tile-label">Orders</div>
                  </div>
                </div>
                <div class="col-6">
                  <div class="stat-tile">
                    <q-icon name="check_circle" color="green" size="20px" />
                    <div class="text-h6 text-weight-bold">{{ partner.paid_orders_count }}</div>
                    <div class="stat-tile-label">Paid</div>
                  </div>
                </div>
                <div class="col-6">
                  <div class="stat-tile">
                    <q-icon name="group_add" color="purple" size="20px" />
                    <div class="text-h6 text-weight-bold">{{ partner.referrals_count }}</div>
                    <div class="stat-tile-label">Referrals</div>
                  </div>
                </div>
              </div>
              <q-separator class="q-my-md" />
              <!-- Call stats -->
              <div class="row q-col-gutter-sm q-mb-md">
                <div class="col-6">
                  <div class="stat-tile">
                    <q-icon name="phone" color="primary" size="20px" />
                    <div class="text-h6 text-weight-bold">{{ partner.contacts_count || 0 }}</div>
                    <div class="stat-tile-label">Calls</div>
                  </div>
                </div>
                <div class="col-6">
                  <div class="stat-tile">
                    <q-icon name="phone_missed" color="negative" size="20px" />
                    <div class="text-h6 text-weight-bold" style="color:#E53935;">{{ partner.missed_calls_count || 0 }}</div>
                    <div class="stat-tile-label">Missed</div>
                  </div>
                </div>
              </div>
              <q-separator class="q-my-md" />
              <div class="row justify-between">
                <div>
                  <div class="stat-label">Paid Revenue</div>
                  <div class="stat-value text-positive">₹{{ formatMoney(partner.paid_orders_sum) }}</div>
                </div>
                <div class="text-right">
                  <div class="stat-label">Unpaid</div>
                  <div class="stat-value text-warning">₹{{ formatMoney(partner.unpaid_orders_sum) }}</div>
                </div>
              </div>
            </q-card-section>
          </q-card>

          <!-- Notes -->
          <q-card flat bordered style="border-radius:12px;">
            <q-card-section>
              <div class="row items-center justify-between q-mb-sm">
                <div class="text-subtitle2 text-weight-bold">
                  Internal Notes
                  <q-icon v-if="isOperator && !hasOwnActivity" name="lock" size="11px" color="grey-5" />
                </div>
                <q-btn v-if="!isOperator || hasOwnActivity" flat dense icon="edit" size="xs" color="grey-6" @click="editNotes = !editNotes">
                  <q-tooltip v-if="isOperator && !hasOwnActivity">
                    Add an Activity record before editing notes
                  </q-tooltip>
                </q-btn>
              </div>
              <q-input v-if="editNotes" v-model="notesValue" type="textarea" outlined dense rows="4"
                autogrow placeholder="Add notes..." />
              <div v-else class="text-body2 text-grey-7" style="white-space:pre-wrap; min-height:40px;">
                {{ partner.notes || 'No notes yet.' }}
              </div>
              <q-btn v-if="editNotes" color="primary" label="Save" size="sm" unelevated
                class="q-mt-sm" @click="saveNotes" />
            </q-card-section>
          </q-card>
        </div>

        <!-- RIGHT: Tasks + Activity -->
        <div style="flex:1; min-width:0; display:flex; flex-direction:column; gap:16px;">

          <!-- Tasks card -->
          <q-card flat bordered style="border-radius:12px;">
            <q-card-section>
              <div class="row items-center justify-between q-mb-md">
                <div class="text-subtitle1 text-weight-bold row items-center q-gutter-xs">
                  <q-icon name="task_alt" color="deep-orange-6" />
                  <span>Tasks</span>
                  <q-badge v-if="openTasksCount > 0" color="deep-orange-6" rounded class="q-ml-xs">
                    {{ openTasksCount }}
                  </q-badge>
                </div>
                <q-btn unelevated icon="add" label="Add Task" color="deep-orange-6" size="sm"
                  @click="openTaskCreate" style="border-radius:8px;" />
              </div>

              <div v-if="tasksLoading" class="text-center q-py-md">
                <q-spinner-dots color="deep-orange" size="28px" />
              </div>

              <div v-else-if="tasks.length === 0" class="text-center q-py-lg text-grey-4" style="font-size:13px">
                <q-icon name="task_alt" size="32px" class="q-mb-xs" />
                <div>No tasks yet</div>
              </div>

              <div v-else class="q-gutter-sm">
                <div v-for="task in tasks" :key="task.id"
                  class="task-row"
                  :class="task.status === 'done' ? 'task-row--done' : task.is_overdue ? 'task-row--overdue' : ''"
                  @click="openTaskDetail(task)"
                >
                  <!-- Done checkbox -->
                  <q-checkbox
                    :model-value="task.status === 'done'"
                    dense color="green-6"
                    :disable="!canToggleTaskDone(task)"
                    @update:model-value="toggleTaskDone(task)"
                    @click.stop
                    style="flex-shrink:0"
                  />

                  <!-- Content -->
                  <div style="flex:1;min-width:0">
                    <div class="row items-center q-gutter-xs">
                      <q-icon :name="priorityIcon(task.priority)" :color="priorityColor(task.priority)" size="13px" />
                      <span class="task-title" :class="task.status === 'done' ? 'task-title--done' : ''">
                        {{ task.title }}
                      </span>
                    </div>
                    <div v-if="task.description" class="text-caption text-grey-5 ellipsis">{{ task.description }}</div>
                    <div class="row items-center q-gutter-xs q-mt-xs">
                      <span v-if="task.due_date"
                        class="task-due"
                        :class="task.is_overdue && task.status !== 'done' ? 'task-due--overdue' : isToday(task.due_date) ? 'task-due--today' : ''"
                      >
                        <q-icon name="event" size="11px" />
                        {{ fmtTaskDate(task.due_date) }}
                      </span>
                      <span v-if="task.assigned_to_detail" class="task-assignee">
                        <q-icon name="person" size="11px" />
                        {{ task.assigned_to_detail.full_name || task.assigned_to_detail.username }}
                      </span>
                    </div>
                    <div class="task-audit">
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
                  </div>

                  <!-- Edit/delete -->
                  <div class="row" style="flex-shrink:0" @click.stop>
                    <q-btn v-if="canEditTask(task)" flat round dense icon="edit" size="xs" color="grey-5" @click="openTaskEdit(task)" />
                    <q-btn v-if="canDeleteTask(task)" flat round dense icon="delete" size="xs" color="grey-4" @click="deleteTask(task)" />
                  </div>
                </div>
              </div>
            </q-card-section>
          </q-card>

          <!-- Activity card -->
          <q-card flat bordered style="border-radius:12px;">
            <q-card-section>
              <div class="row items-center justify-between q-mb-md">
                <div class="text-subtitle1 text-weight-bold row items-center q-gutter-xs">
                  <q-icon name="feed" color="primary" />
                  <span>Activity</span>
                  <q-badge color="primary" rounded class="q-ml-xs">{{ contacts.length }}</q-badge>
                </div>
                <q-btn unelevated icon="add" label="Add Record" color="primary" size="sm"
                  @click="showContactDialog = true" style="border-radius:8px;" />
              </div>

              <div v-if="contactsLoading" class="text-center q-py-lg">
                <q-spinner-dots color="primary" size="32px" />
              </div>

              <div v-else-if="contacts.length === 0" class="text-center q-py-xl text-grey-5">
                <q-icon name="feed" size="48px" class="q-mb-sm" />
                <div class="text-body1">No records yet</div>
                <div class="text-caption">Add the first record</div>
              </div>

              <div v-for="contact in contacts" :key="contact.id" class="q-mb-md">
                <q-card flat :style="contact.is_missed_call
                  ? 'border-radius:10px; border:1px solid #FFCDD2; background:#FFF8F8;'
                  : contact.callback_later
                    ? 'border-radius:10px; border:1px solid #FFE082; background:#FFFDE7;'
                    : 'border-radius:10px; border:1px solid #E0E0E0;'">
                  <q-card-section class="q-pb-sm">
                    <!-- Header: date + author + actions -->
                    <div class="row items-center justify-between q-mb-sm">
                      <div class="row items-center q-gutter-sm">
                        <q-icon name="schedule" color="grey-5" size="16px" />
                        <span class="text-caption text-grey-6">{{ formatDate(contact.date) }}</span>
                        <q-chip v-if="contact.is_missed_call" dense size="xs"
                          color="negative" text-color="white" icon="phone_missed">
                          No Answer
                        </q-chip>
                        <q-chip v-else-if="contact.callback_later" dense size="xs"
                          color="warning" text-color="white" icon="phone_callback">
                          Call Back Later
                        </q-chip>
                        <q-chip v-if="contact.created_by_detail" dense size="xs"
                          color="blue-grey-1" text-color="blue-grey-8" icon="person">
                          {{ contact.created_by_detail.full_name }}
                        </q-chip>
                      </div>
                      <div class="row q-gutter-xs">
                        <q-btn v-if="canEditContact(contact)" flat round dense icon="edit" size="xs" color="grey-6" @click="editContact(contact)" />
                        <q-btn v-if="canDeleteContact(contact)" flat round dense icon="delete" size="xs" color="negative" @click="deleteContact(contact)" />
                      </div>
                    </div>

                    <!-- Transcription status -->
                    <div v-if="contact.transcription_status === 'pending' || contact.transcription_status === 'processing'"
                      class="row items-center q-gutter-xs q-mb-sm"
                      style="background:#E3F2FD; border-radius:8px; padding:8px 12px;">
                      <q-spinner-dots color="primary" size="18px" />
                      <span class="text-caption text-primary text-weight-medium">Transcribing audio...</span>
                    </div>
                    <div v-else-if="contact.transcription_status === 'failed'"
                      class="row items-center justify-between q-mb-sm"
                      style="background:#FFEBEE; border-radius:8px; padding:8px 12px;">
                      <div class="row items-center q-gutter-xs">
                        <q-icon name="error_outline" color="negative" size="16px" />
                        <span class="text-caption text-negative text-weight-medium">Transcription failed</span>
                      </div>
                      <q-btn
                        flat dense size="sm" color="negative" icon="refresh" label="Retry"
                        :loading="retryingContact === contact.id"
                        @click="retryTranscription(contact)"
                      />
                    </div>

                    <!-- Operator comment -->
                    <div v-if="contact.notes" class="q-mb-sm"
                      style="background:#F5F5F5; border-radius:8px; padding:10px 12px; font-size:14px; color:#212121; white-space:pre-wrap;">
                      {{ contact.notes }}
                    </div>

                    <!-- Summary generating — show spinner + transcript underneath -->
                    <div v-if="contact.summary_status === 'pending' || contact.summary_status === 'processing'">
                      <div class="row items-center q-gutter-xs q-mb-sm"
                        style="background:#F3E5F5; border-radius:8px; padding:8px 12px;">
                        <q-spinner-dots color="purple" size="18px" />
                        <span class="text-caption text-weight-medium" style="color:#7B1FA2;">
                          AI is generating summary...
                        </span>
                      </div>
                      <!-- Show transcript while waiting -->
                      <div v-if="contact.diarized_transcript || contact.transcription" class="q-mb-sm">
                        <div :style="expandedContacts.has(contact.id) ? '' : 'max-height:160px; overflow:hidden; -webkit-mask-image:linear-gradient(to bottom, black 50%, transparent 100%);'">
                          <TranscriptChat
                            :diarized="contact.diarized_transcript"
                            :raw="contact.transcription"
                            compact
                          />
                        </div>
                        <q-btn flat dense size="xs" color="grey-6"
                          :label="expandedContacts.has(contact.id) ? 'Show less' : 'Show full transcript'"
                          :icon="expandedContacts.has(contact.id) ? 'expand_less' : 'expand_more'"
                          class="q-mt-xs"
                          @click="toggleExpand(contact.id)"
                        />
                      </div>
                    </div>

                    <div v-else-if="contact.summary_status === 'failed'"
                      class="row items-center justify-between q-mb-sm"
                      style="background:#F3E5F5; border-radius:8px; padding:8px 12px;">
                      <div class="row items-center q-gutter-xs">
                        <q-icon name="error_outline" size="16px" style="color:#7B1FA2;" />
                        <span class="text-caption text-weight-medium" style="color:#7B1FA2;">Summary failed</span>
                      </div>
                      <q-btn flat dense size="sm" icon="refresh" label="Retry"
                        style="color:#7B1FA2;"
                        :loading="retryingContact === contact.id + '-summary'"
                        @click="retrySummary(contact)"
                      />
                    </div>

                    <div v-else-if="contact.summary" class="q-mb-sm">
                      <div class="row items-center q-gutter-xs q-mb-xs">
                        <q-icon name="auto_awesome" size="14px" style="color:#7B1FA2;" />
                        <span class="field-label" style="color:#7B1FA2;">AI Summary</span>
                      </div>
                      <div
                        class="summary-md"
                        :class="expandedSummaries.has(contact.id) ? '' : 'summary-collapsed'"
                        v-html="renderMd(contact.summary)"
                        style="background:#F9F0FF; border-left:3px solid #CE93D8; border-radius:0 8px 8px 0; padding:10px 14px;"
                      />

                      <div class="row items-center q-gutter-sm q-mt-xs">
                        <q-btn flat dense size="xs" color="deep-purple-4"
                          :icon="expandedSummaries.has(contact.id) ? 'expand_less' : 'expand_more'"
                          :label="expandedSummaries.has(contact.id) ? 'Show less' : 'Show more'"
                          @click="toggleSummary(contact.id)"
                        />
                        <q-btn flat dense size="xs" color="grey-6" icon="article"
                          :label="expandedContacts.has(contact.id) ? 'Hide transcript' : 'Show transcript'"
                          @click="toggleExpand(contact.id)"
                        />
                      </div>
                      <!-- Diarized transcript (hidden by default) -->
                      <div v-if="expandedContacts.has(contact.id)" class="q-mt-sm">
                        <TranscriptChat
                          :diarized="contact.diarized_transcript"
                          :raw="contact.transcription"
                          compact
                        />
                      </div>
                    </div>

                    <!-- Transcription without summary (collapsible) -->
                    <div v-else-if="contact.diarized_transcript || contact.transcription" class="q-mb-sm">
                      <div :style="expandedContacts.has(contact.id) ? '' : 'max-height:160px; overflow:hidden; -webkit-mask-image:linear-gradient(to bottom, black 50%, transparent 100%);'">
                        <TranscriptChat
                          :diarized="contact.diarized_transcript"
                          :raw="contact.transcription"
                          compact
                        />
                      </div>
                      <q-btn flat dense size="xs" color="primary"
                        :label="expandedContacts.has(contact.id) ? 'Show less' : 'Show more'"
                        :icon="expandedContacts.has(contact.id) ? 'expand_less' : 'expand_more'"
                        class="q-mt-xs"
                        @click="toggleExpand(contact.id)"
                      />
                    </div>

                    <!-- Partner call insights (admin) -->
                    <div
                      v-if="authStore.isAdmin && contact.transcription_status === 'done'
                        && (contact.diarized_transcript || contact.transcription)"
                      class="q-mb-sm"
                      style="background:#E0F7FA; border-left:3px solid #00838F; border-radius:0 8px 8px 0; padding:10px 14px;"
                    >
                      <div class="row items-center q-gutter-xs q-mb-xs">
                        <q-icon name="lightbulb" size="14px" color="teal-9" />
                        <span class="field-label" style="color:#006064;">Partner call insights</span>
                        <q-space />
                        <router-link
                          v-if="insightByContactId[contact.id]?.id"
                          :to="{ path: '/admin/call-insights', query: { contact: String(contact.id) } }"
                          class="text-caption text-primary text-weight-medium"
                          style="text-decoration:none;"
                        >
                          Open in list
                        </router-link>
                      </div>
                      <div v-if="!insightByContactId[contact.id]" class="text-caption text-grey-7">
                        Generating… refresh will update automatically.
                      </div>
                      <div v-else-if="insightByContactId[contact.id].status === 'pending'
                        || insightByContactId[contact.id].status === 'processing'"
                        class="row items-center q-gutter-xs"
                      >
                        <q-spinner-dots color="teal" size="18px" />
                        <span class="text-caption text-teal-9">Extracting insights…</span>
                      </div>
                      <div v-else-if="insightByContactId[contact.id].status === 'failed'"
                        class="row items-center justify-between"
                      >
                        <span class="text-caption text-negative">Insight extraction failed</span>
                        <q-btn flat dense size="sm" color="negative" icon="refresh" label="Retry"
                          :loading="retryingInsightContactId === contact.id"
                          @click="retryCallInsights(contact)"
                        />
                      </div>
                      <template v-else-if="insightByContactId[contact.id].status === 'done'">
                        <div class="text-caption text-grey-7 q-mb-sm">
                          {{ insightByContactId[contact.id].insight_count }} items
                          <span v-if="insightByContactId[contact.id].density_bucket">
                            · {{ insightByContactId[contact.id].density_bucket }} density
                          </span>
                        </div>
                        <div v-if="insightItemsForContact(contact.id).length">
                          <div
                            v-for="(it, idx) in insightItemsForContact(contact.id).slice(0, expandedInsights.has(contact.id) ? 50 : 2)"
                            :key="`${contact.id}-ins-${idx}`"
                            class="q-mb-sm"
                            style="background:#F2FDFF; border:1px solid #B2EBF2; border-radius:8px; padding:10px 12px;"
                          >
                            <div class="text-body2 text-weight-bold q-mb-xs" style="color:#004D40;">
                              {{ idx + 1 }}. {{ it.title || 'Insight' }}
                            </div>
                            <div class="text-caption q-mb-xs" style="color:#006064;">
                              {{ formatInsightCategory(it.category) }} · {{ formatInsightSentiment(it.sentiment) }}
                            </div>
                            <div class="text-body2 q-mb-xs" style="white-space:pre-wrap;">
                              {{ it.detail_english }}
                            </div>
                            <div class="text-caption text-grey-8" style="white-space:pre-wrap;">
                              <b>Partner quote:</b> {{ it.verbatim_partner_quote || '—' }}
                            </div>
                          </div>
                        </div>
                        <div
                          v-else
                          class="summary-md"
                          :class="expandedInsights.has(contact.id) ? '' : 'summary-collapsed'"
                          v-html="renderMd(insightMarkdownForContact(contact.id))"
                          style="font-size:13px;"
                        />
                        <q-btn flat dense size="xs" color="teal-9"
                          :icon="expandedInsights.has(contact.id) ? 'expand_less' : 'expand_more'"
                          :label="expandedInsights.has(contact.id) ? 'Show less' : 'Show more insights'"
                          class="q-mt-xs"
                          :loading="insightExpandLoading === contact.id"
                          @click="toggleInsightExpand(contact.id)"
                        />
                      </template>
                    </div>

                    <!-- Audio + transcript download -->
                    <div v-if="contact.audio_url">
                      <div class="row items-center justify-between q-mb-xs">
                        <div class="field-label"><q-icon name="graphic_eq" size="14px" /> Audio</div>
                        <div class="row items-center q-gutter-xs">
                          <q-btn
                            v-if="contact.diarized_transcript || contact.transcription"
                            flat dense size="sm" color="primary" icon="visibility"
                            label="View transcript"
                            @click="openTranscriptViewer(contact)"
                          />
                          <a v-if="contact.transcript_url"
                            :href="contact.transcript_url" download
                            class="row items-center q-gutter-xs no-decoration"
                            style="font-size:11px; color:#1976D2; font-weight:600;">
                            <q-icon name="download" size="14px" />
                            <span>Download transcript (.txt)</span>
                          </a>
                        </div>
                      </div>
                      <audio controls :src="contact.audio_url" style="width:100%; height:36px;" />
                    </div>
                  </q-card-section>
                </q-card>
              </div>
            </q-card-section>
          </q-card>

        </div><!-- /right column -->
      </div>

    </div>

    <!-- Dialogs -->
    <AddContactDialog v-if="partner" v-model="showContactDialog" :partner-id="partner.id"
      :contact="editingContact" @saved="onContactSaved" />
    <AddPartnerDialog v-if="partner" v-model="showEditDialog" :partner="partner"
      :users="store.users" @created="onPartnerUpdated" />
    <TaskDialog v-if="partner" v-model="showTaskDialog" :task="editingTask" :partner-id="partner.id"
      @saved="onTaskSaved" />
    <TaskDetailDialog
      v-if="detailTaskObj"
      v-model="showTaskDetail"
      :task="detailTaskObj"
      @updated="onTaskDetailUpdated"
      @edit="openTaskEdit"
    />

    <q-dialog v-model="showTranscriptDialog">
      <q-card style="width:min(1100px,96vw); max-width:96vw; border-radius:12px;">
        <q-card-section class="row items-center q-pb-none">
          <div class="text-subtitle1 text-weight-bold">Transcript Viewer</div>
          <q-space />
          <q-btn flat round dense icon="close" v-close-popup />
        </q-card-section>
        <q-card-section style="max-height:75vh; overflow:auto;">
          <TranscriptChat
            :diarized="transcriptViewerContact?.diarized_transcript || ''"
            :raw="transcriptViewerContact?.transcription || ''"
            :compact="false"
            initial-view="chat"
          />
        </q-card-section>
      </q-card>
    </q-dialog>

  </q-page>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { INDIA_STATES, INDIA_CITIES_WITH_OTHER, ALL_INDIA_CITIES } from 'src/data/india-locations'
import { useQuasar } from 'quasar'
import { api } from 'boot/axios'
import { useAuthStore } from 'src/stores/auth'
import { usePartnersStore } from 'src/stores/partners'
import { useTasksStore } from 'src/stores/tasks'
import { nameColor } from 'src/utils/partnerColors'
import AddContactDialog from 'src/components/AddContactDialog.vue'
import AddPartnerDialog from 'src/components/AddPartnerDialog.vue'
import TaskDialog from 'src/components/TaskDialog.vue'
import TaskDetailDialog from 'src/components/TaskDetailDialog.vue'
import TranscriptChat from 'src/components/TranscriptChat.vue'

const $q = useQuasar()
const route = useRoute()
const router = useRouter()

function goBack() {
  if (window.history.state?.back) {
    router.back()
  } else {
    router.push('/partners')
  }
}
const authStore = useAuthStore()
const store = usePartnersStore()
const tasksStore = useTasksStore()
const partner = ref(null)
const contacts = ref([])
const contactsLoading = ref(false)
const partnerCallInsights = ref([])
const insightDetailById = ref({})
const showContactDialog = ref(false)
const showEditDialog = ref(false)
const editNotes = ref(false)
const notesValue = ref('')
const editingContact = ref(null)
const editProfile = ref(false)
const profileSaving = ref(false)
const profileForm = ref({ gender: '', experience_years: null, city: '', state: '' })

// Tasks
const tasks        = ref([])
const tasksLoading = ref(false)
const showTaskDialog  = ref(false)
const editingTask     = ref(null)
const showTaskDetail  = ref(false)
const detailTaskObj   = ref(null)

const openTasksCount = computed(() =>
  tasks.value.filter(t => t.status === 'open' || t.status === 'in_progress').length
)

// ── Operator restriction helpers ────────────────────────────────────
const isOperator = computed(() => authStore.isOperator)

const hasOwnActivity = computed(() => {
  if (!authStore.user?.id) return false
  if (partner.value?.current_user_has_activity) return true
  return contacts.value.some(c => c.created_by_detail?.id === authStore.user.id)
})

const profileFullyLockedForOperator = computed(() => {
  if (!isOperator.value || !partner.value) return false
  return !!partner.value.gender
    && partner.value.experience_years != null
    && !!partner.value.city
    && !!partner.value.state
})

function isProfileFieldLocked(field) {
  if (!isOperator.value || !partner.value) return false
  if (field === 'experience_years') return partner.value.experience_years != null
  return !!partner.value[field]
}

function isOwnTask(task) {
  return task?.created_by_detail?.id === authStore.user?.id
}
function isAssignedTask(task) {
  return task?.assigned_to === authStore.user?.id
}
function canEditTask(task) {
  if (!isOperator.value) return true
  return isOwnTask(task)
}
function canDeleteTask(task) {
  if (authStore.isAdmin) return true
  if (!isOperator.value) return false
  return isOwnTask(task)
}
function canToggleTaskDone(task) {
  if (!isOperator.value) return true
  return isOwnTask(task) || isAssignedTask(task)
}
function canEditContact(contact) {
  if (!isOperator.value) return true
  return contact?.created_by_detail?.id === authStore.user?.id
}
function canDeleteContact(contact) {
  if (authStore.isAdmin) return true
  if (!isOperator.value) return false
  return contact?.created_by_detail?.id === authStore.user?.id
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    const data = await tasksStore.fetchTasks({ partner: route.params.id, page_size: 100 })
    tasks.value = data.results || data
  } finally {
    tasksLoading.value = false
  }
}

function openTaskCreate() {
  editingTask.value  = null
  showTaskDialog.value = true
}
function openTaskEdit(task) {
  editingTask.value  = task
  showTaskDialog.value = true
}
function openTaskDetail(task) {
  detailTaskObj.value  = task
  showTaskDetail.value = true
}
function onTaskDetailUpdated(updated) {
  const idx = tasks.value.findIndex(t => t.id === updated.id)
  if (idx !== -1) tasks.value[idx] = updated
  detailTaskObj.value = updated
}

async function toggleTaskDone(task) {
  const newStatus = task.status === 'done' ? 'open' : 'done'
  await tasksStore.updateTask(task.id, { status: newStatus })
  await tasksStore.refreshOpenCount()
  loadTasks()
}

async function deleteTask(task) {
  $q.dialog({
    title: 'Delete Task',
    message: `Delete "${task.title}"?`,
    cancel: true,
    ok: { label: 'Delete', color: 'negative' },
  }).onOk(async () => {
    await tasksStore.deleteTask(task.id)
    await tasksStore.refreshOpenCount()
    loadTasks()
  })
}

async function onTaskSaved() {
  await loadTasks()
  $q.notify({ type: 'positive', message: 'Task saved' })
}

function priorityIcon(p)  { return { low: 'arrow_downward', medium: 'remove', high: 'arrow_upward' }[p] || 'remove' }
function priorityColor(p) { return { low: 'grey-5', medium: 'orange', high: 'red-6' }[p] || 'grey' }

const todayStr2 = new Date().toISOString().slice(0, 10)
const isToday   = (d) => d === todayStr2
function fmtTaskDate(d) {
  if (!d) return ''
  return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { day: 'numeric', month: 'short' })
}
function fmtTaskDatetime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('en-US', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}
function taskUserName(detail) {
  if (!detail) return ''
  return detail.full_name || detail.username || ''
}

const genderOptions = [
  { label: 'Male', value: 'male' },
  { label: 'Female', value: 'female' },
]

const profileStateOptions = ref(INDIA_STATES)
const profileCityOptions = ref(ALL_INDIA_CITIES)

const filterProfileStates = (val, update) => {
  update(() => {
    const q = val.toLowerCase()
    profileStateOptions.value = q ? INDIA_STATES.filter(s => s.toLowerCase().includes(q)) : INDIA_STATES
  })
}

const filterProfileCities = (val, update) => {
  update(() => {
    const base = profileForm.value.state && INDIA_CITIES_WITH_OTHER[profileForm.value.state]
      ? INDIA_CITIES_WITH_OTHER[profileForm.value.state]
      : ALL_INDIA_CITIES
    const q = val.toLowerCase()
    profileCityOptions.value = q ? base.filter(c => c.toLowerCase().includes(q)) : base
  })
}

const statusOptions = [
  { label: 'New', value: 'new', color: 'grey-7' },
  { label: 'In Support', value: 'in_support', color: 'blue' },
  { label: 'Closed', value: 'closed', color: 'red' },
]

const stageOptions = [
  { label: 'New', value: 'new' },
  { label: 'Agreed to Create First Set', value: 'trained' },
  { label: 'Medical Set Created', value: 'set_created' },
  { label: 'Has Sale', value: 'has_sale' },
  { label: 'Dead (No Answer)', value: 'no_answer' },
  { label: 'Dead (Declined)', value: 'declined' },
  { label: 'Dead (No Sales)', value: 'no_sales' },
]

const DEAD_STAGES = ['no_answer', 'declined', 'no_sales']

const operatorCanGoDead = computed(() => !!partner.value)

const operatorAllowedStageTargets = computed(() => {
  const set = new Set()
  if (operatorCanGoDead.value) DEAD_STAGES.forEach(s => set.add(s))
  if (hasOwnActivity.value) set.add('trained')
  return set
})

const stageSelectDisabled = computed(
  () => isOperator.value && operatorAllowedStageTargets.value.size === 0
)

const visibleStageOptions = computed(() => {
  if (!isOperator.value) return stageOptions
  const allowed = operatorAllowedStageTargets.value
  return stageOptions.filter(
    o => o.value === partner.value?.stage || allowed.has(o.value)
  )
})

const isOverdue = computed(() => {
  if (!partner.value?.control_date) return false
  return partner.value.control_date < new Date().toISOString().slice(0, 10)
})

const maxControlDate = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() + 14)
  return d.toISOString().slice(0, 10)
})

const formatMoney = (val) => val ? Number(val).toLocaleString('en-US', { minimumFractionDigits: 0 }) : '0'

const formatDate = (dt) => new Date(dt).toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })

const loadPartner = async () => {
  partner.value = await store.fetchPartner(route.params.id)
  notesValue.value = partner.value?.notes || ''
}

// Polling for transcription status — defined before loadContacts so it can be called there
let pollTimer = null

const insightByContactId = computed(() => {
  const m = {}
  for (const row of partnerCallInsights.value) {
    if (row && row.contact != null) m[row.contact] = row
  }
  return m
})

const hasPendingInsights = () =>
  authStore.isAdmin && partnerCallInsights.value.some(ci =>
    ci.status === 'pending' || ci.status === 'processing',
  )

const hasPendingTranscription = () =>
  contacts.value.some(c =>
    c.transcription_status === 'pending' || c.transcription_status === 'processing' ||
    c.summary_status === 'pending' || c.summary_status === 'processing',
  ) || hasPendingInsights()

const pollIfNeeded = () => {
  clearTimeout(pollTimer)
  if (hasPendingTranscription()) {
    pollTimer = setTimeout(async () => {
      contacts.value = await store.fetchContacts(route.params.id)
      if (authStore.isAdmin) await loadPartnerInsights()
      pollIfNeeded()
    }, 4000)
  }
}

async function loadPartnerInsights() {
  if (!authStore.isAdmin || !route.params.id) {
    partnerCallInsights.value = []
    return
  }
  try {
    const rows = await store.fetchPartnerCallInsights(route.params.id)
    partnerCallInsights.value = rows
    const rowById = {}
    for (const r of rows) rowById[String(r.id)] = r
    const validIds = new Set(rows.map(r => r.id))
    const nextDetails = {}
    for (const [id, val] of Object.entries(insightDetailById.value || {})) {
      if (!validIds.has(Number(id))) continue
      // Invalidate ONLY when the actual insight content changed.
      // Polling (telegram retries, last_attempt_at, etc.) keeps bumping `updated_at`,
      // so we must use a content-derived fingerprint instead, otherwise the
      // expanded "Show more" panel collapses on every poll tick.
      const row = rowById[id]
      const cachedFp = val?.transcript_fingerprint || ''
      const rowFp = row?.transcript_fingerprint || ''
      const cachedCount = Number(val?.insight_count ?? -1)
      const rowCount = Number(row?.insight_count ?? -2)
      const cachedStatus = val?.status || ''
      const rowStatus = row?.status || ''
      if (cachedFp && rowFp && cachedFp !== rowFp) continue
      if (cachedCount !== rowCount) continue
      if (cachedStatus && rowStatus && cachedStatus !== rowStatus) continue
      nextDetails[id] = val
    }
    insightDetailById.value = nextDetails
  } catch {
    partnerCallInsights.value = []
    insightDetailById.value = {}
  }
}

const loadContacts = async () => {
  contactsLoading.value = true
  try { contacts.value = await store.fetchContacts(route.params.id) }
  finally { contactsLoading.value = false }
  await loadPartnerInsights()
  pollIfNeeded()
}

const extractErrorDetail = (e) => {
  const data = e?.response?.data
  if (!data) return null
  if (typeof data === 'string') return data
  if (typeof data.detail === 'string') return data.detail
  if (typeof data.error === 'string') return data.error
  try {
    const flat = Object.values(data).flat().filter(Boolean)
    if (flat.length) return flat.join(' ')
  } catch { /* ignore */ }
  return null
}

const changeStatus = async (newStatus) => {
  if (partner.value.status === newStatus) return
  try {
    await store.updatePartner(partner.value.id, { status: newStatus })
    partner.value.status = newStatus
    $q.notify({ type: 'positive', message: 'Status updated', timeout: 1500 })
  } catch (e) {
    $q.notify({
      type: 'negative',
      message: extractErrorDetail(e) || 'Failed to update status',
      timeout: 4000,
      multiLine: true,
    })
  }
}

const changeStage = async (newStage) => {
  try {
    await store.updateStage(partner.value.id, newStage)
    partner.value.stage = newStage
    $q.notify({ type: 'positive', message: 'Stage updated', timeout: 1500 })
  } catch (e) {
    $q.notify({
      type: 'negative',
      message: extractErrorDetail(e) || 'Failed to update stage',
      timeout: 4000,
      multiLine: true,
    })
  }
}

const saveControlDate = async (val) => {
  if (!val) return
  const max = maxControlDate.value
  if (val > max) {
    $q.notify({ type: 'negative', message: 'Max 14 days ahead', timeout: 2000 })
    return
  }
  try {
    await store.updatePartner(partner.value.id, { control_date: val })
    partner.value.control_date = val
    $q.notify({ type: 'positive', message: 'Date saved', timeout: 1500 })
  } catch (e) {
    $q.notify({
      type: 'negative',
      message: extractErrorDetail(e) || 'Failed to save date',
      timeout: 4000,
      multiLine: true,
    })
  }
}

const startEditProfile = () => {
  profileForm.value = {
    gender: partner.value.gender || '',
    experience_years: partner.value.experience_years ?? null,
    city: partner.value.city || '',
    state: partner.value.state || '',
  }
  editProfile.value = true
}

const saveProfile = async () => {
  profileSaving.value = true
  try {
    const updated = await store.updatePartner(partner.value.id, {
      gender: profileForm.value.gender || '',
      experience_years: profileForm.value.experience_years ?? null,
      city: profileForm.value.city || '',
      state: profileForm.value.state || '',
    })
    partner.value.gender = updated.gender
    partner.value.gender_display = updated.gender_display
    partner.value.experience_years = updated.experience_years
    partner.value.city = updated.city
    partner.value.state = updated.state
    editProfile.value = false
    $q.notify({ type: 'positive', message: 'Profile updated', timeout: 1500 })
  } finally {
    profileSaving.value = false
  }
}

const saveNotes = async () => {
  await store.updatePartner(partner.value.id, { notes: notesValue.value })
  partner.value.notes = notesValue.value
  editNotes.value = false
  $q.notify({ type: 'positive', message: 'Notes saved', timeout: 1500 })
}

function renderMd(text) {
  if (!text) return ''
  let html = text
    // Escape HTML entities first
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // Headings (### ## #)
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Bold **text**
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Unordered list items
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    // Ordered list items
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // Wrap consecutive <li> in <ul>
    .replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
    // Paragraphs: split by blank lines
    .split(/\n{2,}/)
    .map(block => {
      block = block.trim()
      if (!block) return ''
      if (/^<(h[1-3]|ul|ol)/.test(block)) return block
      // Replace single newlines with <br> inside paragraphs
      return `<p>${block.replace(/\n/g, '<br>')}</p>`
    })
    .join('\n')
  return html
}

const expandedContacts  = ref(new Set())
const expandedSummaries = ref(new Set())
const expandedInsights  = ref(new Set())
const insightExpandLoading = ref(null)

const toggleExpand = (id) => {
  const s = new Set(expandedContacts.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expandedContacts.value = s
}
const toggleSummary = (id) => {
  const s = new Set(expandedSummaries.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expandedSummaries.value = s
}

function insightMarkdownForContact(contactId) {
  const row = insightByContactId.value[contactId]
  if (!row) return ''
  const full = insightDetailById.value[row.id]
  const md = (full && full.insights_markdown) || row.preview || ''
  return md
}

function insightItemsForContact(contactId) {
  const row = insightByContactId.value[contactId]
  if (!row?.id) return []
  const full = insightDetailById.value[row.id]
  const items = full?.insights_json?.insights
  return Array.isArray(items) ? items : []
}

function formatInsightCategory(category) {
  const labels = {
    product: 'Product / Offer',
    market_ayurveda: 'Ayurveda Market',
    competitors: 'Competitors / Alternatives',
    manufacturers: 'Manufacturers / Brands',
    platform_ask_ayurveda: 'Ask Ayurveda Platform',
    prescribing_procurement: 'Prescribing / Procurement',
    physician_practice: 'Prescribing / Procurement',
    earning_money: 'Earnings / Margins',
    other: 'Other',
  }
  return labels[String(category || '').toLowerCase()] || 'Other'
}

function formatInsightSentiment(sentiment) {
  const labels = {
    positive: 'Positive',
    negative: 'Negative',
    neutral: 'Neutral',
    mixed: 'Mixed',
  }
  return labels[String(sentiment || '').toLowerCase()] || 'Neutral'
}

async function toggleInsightExpand(contactId) {
  const s = new Set(expandedInsights.value)
  if (s.has(contactId)) {
    s.delete(contactId)
    expandedInsights.value = s
    return
  }
  const row = insightByContactId.value[contactId]
  if (row?.id && !insightDetailById.value[row.id]) {
    insightExpandLoading.value = contactId
    try {
      const res = await api.get(`/call-insights/${row.id}/`)
      insightDetailById.value = { ...insightDetailById.value, [row.id]: res.data }
    } catch {
      $q.notify({ type: 'negative', message: 'Could not load full insight text' })
      return
    } finally {
      insightExpandLoading.value = null
    }
  }
  s.add(contactId)
  expandedInsights.value = s
}

const retryingContact = ref(null)
const retryingInsightContactId = ref(null)
const showTranscriptDialog = ref(false)
const transcriptViewerContact = ref(null)

const retryTranscription = async (contact) => {
  retryingContact.value = contact.id
  try {
    const updated = await store.retryTranscription(contact.id)
    const idx = contacts.value.findIndex(c => c.id === contact.id)
    if (idx !== -1) contacts.value[idx] = updated
    pollIfNeeded()
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to retry transcription' })
  } finally {
    retryingContact.value = null
  }
}

const retrySummary = async (contact) => {
  retryingContact.value = contact.id + '-summary'
  try {
    const updated = await store.retrySummary(contact.id)
    const idx = contacts.value.findIndex(c => c.id === contact.id)
    if (idx !== -1) contacts.value[idx] = updated
    pollIfNeeded()
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to retry summary' })
  } finally {
    retryingContact.value = null
  }
}

const retryCallInsights = async (contact) => {
  retryingInsightContactId.value = contact.id
  try {
    await store.retryCallInsights(contact.id)
    $q.notify({ type: 'positive', message: 'Insight extraction queued', timeout: 1500 })
    await loadPartnerInsights()
    pollIfNeeded()
  } catch (e) {
    const msg = e?.response?.data?.error || 'Failed to retry insights'
    $q.notify({ type: 'negative', message: msg })
  } finally {
    retryingInsightContactId.value = null
  }
}

const openTranscriptViewer = (contact) => {
  transcriptViewerContact.value = contact
  showTranscriptDialog.value = true
}

const saveWhatsapp = async (val) => {
  try {
    await store.updatePartner(partner.value.id, { whatsapp_added: val })
    partner.value.whatsapp_added = val
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to update WhatsApp status' })
  }
}

const assignOperator = async (user) => {
  try {
    await store.updatePartner(partner.value.id, { assigned_to: user.id })
    partner.value.assigned_to = user.id
    partner.value.assigned_to_detail = user
    $q.notify({ type: 'positive', message: `Assigned to ${user.full_name || user.username}`, timeout: 1500 })
  } catch {
    $q.notify({ type: 'negative', message: 'Failed to assign operator' })
  }
}

const onContactSaved = async () => {
  showContactDialog.value = false
  editingContact.value = null
  loadContacts()
  // Re-fetch partner to pick up any control_date change (e.g. from Call Back Later)
  partner.value = await store.fetchPartner(route.params.id)
  $q.notify({ type: 'positive', message: 'Record saved' })
}

const editContact = (contact) => {
  editingContact.value = contact
  showContactDialog.value = true
}

const deleteContact = (contact) => {
  $q.dialog({
    title: 'Delete Record',
    message: 'Remove this record?',
    cancel: true,
    ok: { label: 'Delete', color: 'negative' }
  }).onOk(async () => {
    await store.deleteContact(contact.id)
    contacts.value = contacts.value.filter(c => c.id !== contact.id)
    $q.notify({ type: 'positive', message: 'Deleted' })
  })
}

const onPartnerUpdated = async () => {
  showEditDialog.value = false
  await loadPartner()
  $q.notify({ type: 'positive', message: 'Partner updated' })
}

watch(
  () => authStore.isAdmin,
  (is) => { if (is) loadPartnerInsights() },
)

onMounted(() => { loadPartner(); loadContacts(); loadTasks() })
onUnmounted(() => { clearTimeout(pollTimer) })
</script>

<style scoped>
.detail-name-tag {
  display: inline-block;
  font-size: 18px;
  font-weight: 700;
  padding: 3px 12px;
  border-radius: 8px;
  max-width: 100%;
  word-break: break-word;
}
.info-row { display:flex; align-items:center; gap:8px; padding:6px 0; font-size:14px; color:#424242; border-bottom:1px solid #F5F5F5; }
.info-row:last-child { border-bottom:none; }
.field-label { font-size:12px; font-weight:600; color:#9E9E9E; text-transform:uppercase; letter-spacing:0.5px; }
.stat-tile { background:#F5F7FA; border-radius:8px; padding:10px; text-align:center; }
.stat-tile-label { font-size:10px; color:#9E9E9E; text-transform:uppercase; letter-spacing:0.5px; }
.stat-label { font-size:12px; color:#9E9E9E; }
.stat-value { font-size:18px; font-weight:700; }
.record-text { font-size:14px; line-height:1.6; color:#212121; white-space:pre-wrap; background:#FAFAFA; border-radius:6px; padding:10px 12px; }
.overdue-date :deep(.q-field__control) { border-color: #C10015 !important; }
.profile-field {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 8px;
  border-radius: 6px;
  border: 1px solid #E0E0E0;
  cursor: pointer;
  min-height: 30px;
  transition: border-color 0.15s;
}
.profile-field:hover { border-color: #9E9E9E; }
.profile-field--empty { border: 1.5px solid #C10015; background: #FFF8F8; }
.operator-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1.5px solid #C8E6C9;
  background: #F1F8E9;
  cursor: pointer;
  transition: box-shadow 0.15s;
}
.operator-pill:hover { box-shadow: 0 2px 8px rgba(46,125,50,0.15); }
.operator-pill--empty {
  border-color: #E0E0E0;
  background: #FAFAFA;
}
.summary-md { font-size: 14px; color: #212121; line-height: 1.7; }
.summary-collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.summary-md :deep(p) { margin: 0 0 8px; }
.summary-md :deep(p:last-child) { margin-bottom: 0; }
.summary-md :deep(ul), .summary-md :deep(ol) { margin: 4px 0 8px 18px; padding: 0; }
.summary-md :deep(li) { margin-bottom: 3px; }
.summary-md :deep(strong) { font-weight: 700; color: #5E35B1; }
.summary-md :deep(h1), .summary-md :deep(h2), .summary-md :deep(h3) {
  font-size: 14px; font-weight: 700; margin: 8px 0 4px; color: #4A148C;
}


/* ── Tasks ─────────────────────────────────────────────── */
.task-row {
  display: flex;
  align-items: flex-start;
  cursor: pointer;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #F0F0F0;
  background: #fff;
  transition: border-color 0.15s;
}
.task-row:hover        { border-color: #E0E0E0; }
.task-row--done        { background: #FAFAFA; opacity: 0.7; }
.task-row--overdue     { border-color: #FFCDD2; background: #FFF8F8; }
.task-title            { font-size: 13px; font-weight: 600; color: #212121; }
.task-title--done      { text-decoration: line-through; color: #9E9E9E; font-weight: 400; }
.task-due              { font-size: 10px; color: #757575; display:inline-flex; align-items:center; gap:2px; }
.task-due--overdue     { color: #C62828; font-weight: 700; }
.task-due--today       { color: #E65100; font-weight: 700; }
.task-assignee         { font-size: 10px; color: #9E9E9E; display:inline-flex; align-items:center; gap:2px; }

.task-audit {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 10px;
  color: #9E9E9E;
  margin-top: 4px;
}
.task-audit-row { display: inline-flex; align-items: center; gap: 3px; }
.task-audit-row strong {
  font-weight: 600;
  color: #424242;
  margin: 0 2px;
}
.task-audit-row--done strong { color: #2E7D32; }
.task-audit-time { color: #BDBDBD; }
</style>
