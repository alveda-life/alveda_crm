<template>
  <q-page class="analytics-root q-pa-lg">

    <!-- Header -->
    <div class="row items-center justify-between q-mb-md">
      <div>
        <div class="text-h5 text-weight-bold text-dark">Producer Analytics</div>
        <div class="text-caption text-grey-6 q-mt-xs">Onboarding funnel performance &amp; operator results</div>
      </div>
      <q-btn flat round icon="refresh" color="grey-6" :loading="loading" @click="load">
        <q-tooltip>Refresh</q-tooltip>
      </q-btn>
    </div>

    <!-- Section switcher -->
    <div class="row items-center q-mb-md" style="gap:8px">
      <button v-for="s in sections" :key="s.key"
        class="section-btn" :class="section === s.key ? 'section-btn--active' : ''"
        @click="section = s.key">
        <q-icon :name="s.icon" size="15px" style="margin-right:5px" />
        {{ s.label }}
      </button>
    </div>

    <!-- Period tabs -->
    <div class="row items-center q-mb-md">
      <q-tabs v-model="period" dense align="left" active-color="primary" indicator-color="primary">
        <q-tab name="today"  label="Today" />
        <q-tab name="week"   label="Last 7 Days" />
        <q-tab name="month"  label="Last 30 Days" />
        <q-tab name="all"    label="All Time" />
        <q-tab name="custom" label="Custom" icon="date_range" />
      </q-tabs>
    </div>

    <!-- Custom range -->
    <transition name="slide-down">
      <div v-if="period === 'custom'" class="custom-range-bar q-mb-lg">
        <q-icon name="date_range" color="primary" size="18px" />
        <span class="text-caption text-grey-6">From</span>
        <q-input v-model="customFrom" type="date" dense outlined :max="customTo || todayStr"
          hide-bottom-space style="width:148px" bg-color="white" @update:model-value="onDateChange" />
        <span class="text-caption text-grey-5">—</span>
        <span class="text-caption text-grey-6">To</span>
        <q-input v-model="customTo" type="date" dense outlined :min="customFrom" :max="todayStr"
          hide-bottom-space style="width:148px" bg-color="white" @update:model-value="onDateChange" />
        <q-btn unelevated color="primary" label="Apply" dense
          style="height:36px;padding:0 16px;border-radius:8px"
          :disable="!customFrom || !customTo" @click="loadCustom" />
        <span v-if="customFrom && customTo" class="text-caption text-grey-5">
          {{ customDayCount }} day{{ customDayCount !== 1 ? 's' : '' }}
        </span>
      </div>
    </transition>

    <!-- Loading -->
    <div v-if="loading" class="flex flex-center q-py-xl">
      <q-spinner-dots color="primary" size="48px" />
    </div>

    <template v-else-if="data">

      <!-- ══════ OVERVIEW SECTION ══════════════════════════════════════════ -->
      <template v-if="section === 'overview'">

      <!-- ── KPI Cards ──────────────────────────────────────────────────── -->
      <div class="kpi-grid q-mb-lg">

        <div class="kpi-card">
          <div class="kpi-icon" style="background:#E8F5E9">
            <q-icon name="rocket_launch" color="green-8" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#2E7D32">{{ data.totals.onboarding }}</div>
            <div class="kpi-label">In Onboarding</div>
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-icon" style="background:#E3F2FD">
            <q-icon name="support_agent" color="blue-8" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#1565C0">{{ data.totals.support }}</div>
            <div class="kpi-label">In Support</div>
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-icon" style="background:#F3E5F5">
            <q-icon name="person_add" color="purple-7" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#6A1B9A">{{ data.totals.new_period }}</div>
            <div class="kpi-label">New ({{ periodLabel }})</div>
          </div>
        </div>

        <div class="kpi-card" :class="data.totals.moved_to_support > 0 ? 'kpi-card--good' : ''">
          <div class="kpi-icon" style="background:#E8F5E9">
            <q-icon name="check_circle" color="green-7" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#2E7D32">{{ data.totals.moved_to_support }}</div>
            <div class="kpi-label">Moved to Support</div>
          </div>
        </div>

        <div class="kpi-card" :class="data.totals.stopped > 0 ? 'kpi-card--warn' : ''">
          <div class="kpi-icon" style="background:#FFEBEE">
            <q-icon name="block" color="red-6" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#C62828">{{ data.totals.stopped }}</div>
            <div class="kpi-label">Stopped</div>
          </div>
        </div>

        <div class="kpi-card" v-if="convRate !== null">
          <div class="kpi-icon" style="background:#FFF3E0">
            <q-icon name="trending_up" color="orange-8" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#E65100">{{ convRate }}%</div>
            <div class="kpi-label">Conversion Rate</div>
          </div>
        </div>

      </div>

      <!-- ── Two-column layout: Stage Funnel + Weekly Chart ─────────────── -->
      <div class="two-col q-mb-lg">

        <!-- Onboarding stage funnel -->
        <div class="acard" style="grid-column: span 6 / span 6">
          <div class="acard-header q-mb-md">
            <div class="acard-title">Onboarding Stage Funnel</div>
            <div class="text-caption text-grey-5">Current distribution across stages</div>
          </div>

          <div v-for="s in data.by_stage" :key="s.key" class="stage-row q-mb-sm">
            <div class="stage-label-wrap">
              <div class="stage-dot" :style="`background:${stageColor(s.key)}`" />
              <span class="stage-label">{{ s.label }}</span>
            </div>
            <div class="stage-bar-wrap">
              <div class="stage-bar-bg">
                <div
                  class="stage-bar-fill"
                  :style="`width:${s.bar_pct}%;background:${stageColor(s.key)}`"
                />
              </div>
            </div>
            <div class="stage-meta">
              <span class="stage-count" :style="`color:${stageColor(s.key)}`">{{ s.count }}</span>
              <span class="stage-pct text-grey-5">{{ s.pct }}%</span>
              <span v-if="s.avg_days !== null" class="stage-days text-grey-4">
                ~{{ s.avg_days }}d
              </span>
            </div>
          </div>
        </div>

        <!-- Weekly new producers sparkline -->
        <div class="acard" style="grid-column: span 6 / span 6">
          <div class="acard-header q-mb-md">
            <div class="acard-title">New Producers — Last 10 Weeks</div>
            <div class="text-caption text-grey-5">Added to onboarding funnel per week</div>
          </div>

          <div v-if="data.weekly_new && data.weekly_new.some(w => w.count > 0)" class="weekly-chart">
            <div
              v-for="w in data.weekly_new" :key="w.label"
              class="weekly-col"
            >
              <div class="weekly-bar-wrap">
                <div
                  class="weekly-bar"
                  :style="`height:${weeklyMax > 0 ? Math.max(4, w.count / weeklyMax * 100) : 4}%;background:${w.count > 0 ? '#43A047' : '#E0E0E0'}`"
                  :title="`${w.label}: ${w.count}`"
                />
              </div>
              <div class="weekly-label">{{ w.label }}</div>
              <div class="weekly-count" :style="`color:${w.count > 0 ? '#2E7D32' : '#BDBDBD'}`">{{ w.count }}</div>
            </div>
          </div>
          <div v-else class="flex flex-center q-py-xl text-grey-4" style="flex-direction:column;gap:8px">
            <q-icon name="bar_chart" size="40px" />
            <div class="text-caption">No data yet</div>
          </div>
        </div>

      </div>

      <!-- ── Operator Performance Table ────────────────────────────────── -->
      <div class="acard q-mb-lg" v-if="data.operators && data.operators.length">
        <div class="acard-header q-mb-md">
          <div class="acard-title">Operator Performance — Onboarding</div>
          <div class="text-caption text-grey-5">Who is handling which producers and their progress</div>
        </div>

        <div class="op-table-wrap">
          <table class="op-table">
            <thead>
              <tr>
                <th class="col-operator">Operator</th>
                <th class="cell-center">Assigned</th>
                <th class="cell-center">Advanced<br><span style="font-weight:400;font-size:9px">(Signing Contract+)</span></th>
                <th class="cell-center">Moved to<br>Support</th>
                <th class="cell-center">Conversion %</th>
                <th class="cell-center">Stopped</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="op in data.operators" :key="op.name" class="op-row">
                <td>
                  <div class="row items-center" style="gap:8px">
                    <q-avatar size="28px" color="green-8" text-color="white" style="font-size:11px;flex-shrink:0">
                      {{ initials(op.name) }}
                    </q-avatar>
                    <span style="font-weight:600;font-size:12px;color:#212121">{{ op.name }}</span>
                  </div>
                </td>
                <td class="cell-center"><b>{{ op.assigned }}</b></td>
                <td class="cell-center">
                  <span v-if="op.advanced > 0" class="num-chip" style="background:#E3F2FD;color:#1565C0">{{ op.advanced }}</span>
                  <span v-else class="num-dim">—</span>
                </td>
                <td class="cell-center">
                  <span v-if="op.moved_to_support > 0" class="num-chip" style="background:#E8F5E9;color:#2E7D32">{{ op.moved_to_support }}</span>
                  <span v-else class="num-dim">—</span>
                </td>
                <td class="cell-center">
                  <span :class="op.conv_pct >= 30 ? 'conv-good' : op.conv_pct > 0 ? 'conv-mid' : 'num-dim'">
                    {{ op.conv_pct > 0 ? op.conv_pct + '%' : '—' }}
                  </span>
                </td>
                <td class="cell-center">
                  <span v-if="op.stopped > 0" class="num-chip num--orange">{{ op.stopped }}</span>
                  <span v-else class="num-dim">—</span>
                </td>
              </tr>
            </tbody>
            <tfoot v-if="data.operators.length > 1">
              <tr class="totals-row">
                <td style="font-size:10px;color:#9E9E9E;font-weight:600;text-transform:uppercase">Team</td>
                <td class="cell-center"><b>{{ teamTotals.assigned }}</b></td>
                <td class="cell-center"><span class="num-chip" style="background:#E3F2FD;color:#1565C0">{{ teamTotals.advanced }}</span></td>
                <td class="cell-center"><span class="num-chip" style="background:#E8F5E9;color:#2E7D32">{{ teamTotals.moved_to_support }}</span></td>
                <td class="cell-center">
                  <span :class="teamConv >= 30 ? 'conv-good' : teamConv > 0 ? 'conv-mid' : 'num-dim'">
                    {{ teamConv > 0 ? teamConv + '%' : '—' }}
                  </span>
                </td>
                <td class="cell-center">
                  <span v-if="teamTotals.stopped > 0" class="num-chip num--orange">{{ teamTotals.stopped }}</span>
                  <span v-else class="num-dim">—</span>
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <div v-else-if="!loading" class="acard text-center text-grey-5 q-py-xl q-mb-lg">
        <q-icon name="people" size="40px" class="q-mb-sm" />
        <div>No producers assigned to operators yet</div>
      </div>

      <!-- ── Upcoming Planned Connections ─────────────────────────────────── -->
      <div class="acard q-mb-lg" v-if="data.upcoming_connections && data.upcoming_connections.length">
        <div class="acard-header q-mb-md">
          <div class="row items-center" style="gap:8px">
            <q-icon name="event_available" color="teal-7" size="18px" />
            <div class="acard-title">Planned Connections</div>
          </div>
          <div class="text-caption text-grey-5">{{ data.upcoming_connections.length }} producers with a target date</div>
        </div>
        <q-markup-table flat dense separator="horizontal" style="font-size:12px;">
          <thead>
            <tr style="color:#9E9E9E;">
              <th class="text-left">Producer</th>
              <th class="text-left">Stage</th>
              <th class="text-left">Plan. Date</th>
              <th class="text-left">Days</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in data.upcoming_connections" :key="p.id"
              style="cursor:pointer;" @click="$router.push(`/producers/${p.id}`)">
              <td>
                <span style="font-weight:600;color:#212121;">{{ p.name }}</span>
                <span v-if="p.company" style="color:#9E9E9E;font-size:11px;margin-left:5px;">{{ p.company }}</span>
              </td>
              <td style="color:#546E7A;">{{ p.stage_display }}</td>
              <td>
                <span :style="p.is_overdue ? 'color:#C62828;font-weight:700;' : 'color:#00897B;font-weight:600;'">
                  <q-icon v-if="p.is_overdue" name="warning" size="11px" />
                  {{ fmtConnDate(p.planned_connection_date) }}
                </span>
              </td>
              <td>
                <span :style="connDaysStyle(p.planned_connection_date, p.is_overdue)">
                  {{ connDaysLabel(p.planned_connection_date, p.is_overdue) }}
                </span>
              </td>
            </tr>
          </tbody>
        </q-markup-table>
      </div>

      </template><!-- /overview -->

      <!-- ══════ DEEP DIVE SECTION ════════════════════════════════════════ -->
      <template v-if="section === 'deep_dive'">

      <!-- Support Funnel -->
      <div class="acard q-mb-lg" v-if="data.support_stages && data.support_stages.length">
        <div class="acard-header q-mb-md">
          <div class="acard-title">Support Funnel — Current State</div>
          <div class="text-caption text-grey-5">{{ data.totals.support }} producers in support pipeline</div>
        </div>
        <div v-for="s in data.support_stages" :key="s.key" class="stage-row q-mb-sm">
          <div class="stage-label-wrap">
            <div class="stage-dot" :style="`background:${supportStageColor(s.key)}`" />
            <span class="stage-label">{{ s.label }}</span>
          </div>
          <div class="stage-bar-wrap">
            <div class="stage-bar-bg">
              <div class="stage-bar-fill"
                :style="`width:${data.totals.support > 0 ? Math.round(s.count / data.totals.support * 100) : 0}%;background:${supportStageColor(s.key)}`" />
            </div>
          </div>
          <div class="stage-meta">
            <span class="stage-count" :style="`color:${supportStageColor(s.key)}`">{{ s.count }}</span>
            <span v-if="s.avg_days !== null" class="stage-days text-grey-4">~{{ s.avg_days }}d</span>
          </div>
        </div>
      </div>

      <!-- Weekly Comments + Task Stats -->
      <div class="two-col q-mb-lg">
        <!-- Weekly comments chart -->
        <div class="acard" style="grid-column: span 7 / span 7">
          <div class="acard-header q-mb-md">
            <div class="acard-title">Comment Activity — Last 10 Weeks</div>
            <div class="text-caption text-grey-5">comments added per week across all producers</div>
          </div>
          <div v-if="data.weekly_comments && data.weekly_comments.some(w => w.count > 0)" class="weekly-chart">
            <div v-for="w in data.weekly_comments" :key="w.label" class="weekly-col">
              <div class="weekly-bar-wrap">
                <div class="weekly-bar"
                  :style="`height:${weeklyCommentsMax > 0 ? Math.max(4, w.count / weeklyCommentsMax * 100) : 4}%;background:${w.count > 0 ? '#5C6BC0' : '#E0E0E0'}`"
                  :title="`${w.label}: ${w.count}`" />
              </div>
              <div class="weekly-label">{{ w.label }}</div>
              <div class="weekly-count" :style="`color:${w.count > 0 ? '#3949AB' : '#BDBDBD'}`">{{ w.count }}</div>
            </div>
          </div>
          <div v-else class="flex flex-center q-py-xl text-grey-4" style="flex-direction:column;gap:8px">
            <q-icon name="chat_bubble_outline" size="40px" />
            <div class="text-caption">No comments yet</div>
          </div>
        </div>

        <!-- Task Stats KPIs -->
        <div class="acard" style="grid-column: span 5 / span 5">
          <div class="acard-header q-mb-md">
            <div class="acard-title">Producer Task Stats</div>
          </div>
          <template v-if="data.task_stats">
            <div class="kpi-grid" style="grid-template-columns: 1fr 1fr; gap: 10px">
              <div class="kpi-card" style="flex-direction:column;align-items:flex-start;gap:4px;padding:12px">
                <div class="kpi-val" style="font-size:20px">{{ data.task_stats.total }}</div>
                <div class="kpi-label">Total Tasks</div>
              </div>
              <div class="kpi-card kpi-card--warn" v-if="data.task_stats.open > 0" style="flex-direction:column;align-items:flex-start;gap:4px;padding:12px">
                <div class="kpi-val" style="font-size:20px;color:#1565C0">{{ data.task_stats.open }}</div>
                <div class="kpi-label">Open</div>
              </div>
              <div class="kpi-card" style="flex-direction:column;align-items:flex-start;gap:4px;padding:12px">
                <div class="kpi-val" style="font-size:20px;color:#2E7D32">{{ data.task_stats.done }}</div>
                <div class="kpi-label">Done</div>
              </div>
              <div class="kpi-card" :class="data.task_stats.overdue > 0 ? 'kpi-card--warn' : ''" style="flex-direction:column;align-items:flex-start;gap:4px;padding:12px">
                <div class="kpi-val" style="font-size:20px;color:#C62828">{{ data.task_stats.overdue }}</div>
                <div class="kpi-label">Overdue</div>
              </div>
            </div>
            <div class="q-mt-md" style="text-align:center">
              <div style="font-size:28px;font-weight:800;color:#43A047">{{ data.task_stats.completion_rate }}%</div>
              <div style="font-size:11px;color:#9E9E9E">Completion Rate</div>
              <div style="height:8px;background:#F5F5F5;border-radius:4px;margin-top:8px;overflow:hidden">
                <div :style="`width:${data.task_stats.completion_rate}%;height:100%;background:#43A047;border-radius:4px`" />
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- Priority + Cooperation + Follow-up KPIs -->
      <div class="two-col q-mb-lg">

        <!-- Priority breakdown -->
        <div class="acard" style="grid-column: span 4 / span 4">
          <div class="acard-header q-mb-md">
            <div class="acard-title">Priority Distribution</div>
          </div>
          <template v-if="data.by_priority">
            <div v-for="p in data.by_priority" :key="p.value" class="seg-row q-mb-xs">
              <div class="seg-label" style="max-width:80px;font-weight:600;" :style="`color:${p.color}`">{{ p.label }}</div>
              <div class="seg-bars">
                <div class="seg-bar-wrap">
                  <div class="seg-bar" :style="`width:${p.pct}%;background:${p.color};`" />
                </div>
              </div>
              <span class="seg-chip" :style="`background:${p.color}18;color:${p.color};border:1px solid ${p.color}44;`">{{ p.count }}</span>
            </div>
          </template>
          <div v-if="data.overdue_followups > 0" class="q-mt-md"
            style="background:#FFEBEE;border-radius:8px;padding:8px 12px;display:flex;align-items:center;gap:8px;">
            <q-icon name="event_busy" color="red-7" size="18px" />
            <div>
              <div style="font-size:16px;font-weight:700;color:#C62828;">{{ data.overdue_followups }}</div>
              <div style="font-size:11px;color:#C62828;">overdue follow-ups</div>
            </div>
          </div>
        </div>

        <!-- Cooperation Potential -->
        <div class="acard" style="grid-column: span 4 / span 4">
          <div class="acard-header q-mb-md">
            <div class="acard-title">Cooperation Potential</div>
          </div>
          <template v-if="data.by_coop">
            <div v-for="c in data.by_coop" :key="c.value" class="seg-row q-mb-xs">
              <div class="seg-label" style="max-width:100px;font-weight:600;" :style="`color:${c.color}`">{{ c.label }}</div>
              <div class="seg-bars">
                <div class="seg-bar-wrap">
                  <div class="seg-bar" :style="`width:${c.pct}%;background:${c.color};`" />
                </div>
              </div>
              <span class="seg-chip" :style="`background:${c.color}18;color:${c.color};border:1px solid ${c.color}44;`">{{ c.count }}</span>
            </div>
          </template>
        </div>

        <!-- Product Categories -->
        <div class="acard" style="grid-column: span 4 / span 4" v-if="data.by_product_type && data.by_product_type.length">
          <div class="acard-title q-mb-md">Product Categories</div>
          <div v-for="pt in data.by_product_type.slice(0,8)" :key="pt.product_type" class="seg-row q-mb-xs">
            <div class="seg-label" style="max-width:130px;font-size:11px;">{{ pt.product_type }}</div>
            <div class="seg-bars">
              <div class="seg-bar-wrap">
                <div class="seg-bar" :style="`width:${productTypeMax > 0 ? pt.count / productTypeMax * 100 : 0}%;background:#AB47BC`" />
              </div>
            </div>
            <span class="seg-chip seg-chip--count">{{ pt.count }}</span>
          </div>
        </div>

      </div>

      <!-- Geography -->
      <div class="two-col q-mb-lg">
        <div class="acard" style="grid-column: span 6 / span 6" v-if="data.by_country && data.by_country.length">
          <div class="acard-title q-mb-md">Top Countries</div>
          <div v-for="c in data.by_country" :key="c.country" class="seg-row">
            <div class="seg-label" style="max-width:120px">{{ c.country }}</div>
            <div class="seg-bars">
              <div class="seg-bar-wrap">
                <div class="seg-bar" :style="`width:${countryMax > 0 ? c.count / countryMax * 100 : 0}%;background:#5C6BC0`" />
              </div>
            </div>
            <span class="seg-chip seg-chip--count">{{ c.count }}</span>
          </div>
        </div>

        <div class="acard" style="grid-column: span 6 / span 6" v-if="data.by_product_type && data.by_product_type.length">
          <div class="acard-title q-mb-md">All Product Categories</div>
          <div v-for="pt in data.by_product_type" :key="pt.product_type" class="seg-row">
            <div class="seg-label" style="max-width:150px;font-size:11px;">{{ pt.product_type }}</div>
            <div class="seg-bars">
              <div class="seg-bar-wrap">
                <div class="seg-bar" :style="`width:${productTypeMax > 0 ? pt.count / productTypeMax * 100 : 0}%;background:#AB47BC`" />
              </div>
            </div>
            <span class="seg-chip seg-chip--count">{{ pt.count }}</span>
          </div>
        </div>
      </div>

      </template><!-- /deep_dive -->

      <!-- ══════ AI CHAT SECTION ═══════════════════════════════════════════ -->
      <template v-if="section === 'ai_chat'">
      <div class="acard q-mb-lg" style="min-height:500px;display:flex;flex-direction:column">
        <div class="acard-header q-mb-md">
          <div class="row items-center" style="gap:8px">
            <q-icon name="smart_toy" color="deep-purple-5" size="20px" />
            <div class="acard-title">AI Analytics Assistant — Producers</div>
          </div>
          <div class="text-caption text-grey-5">Ask questions about your producer pipeline</div>
        </div>
        <div ref="chatBox" class="chat-box" style="flex:1;overflow-y:auto;min-height:300px;max-height:480px;display:flex;flex-direction:column;gap:10px;margin-bottom:12px">
          <div v-if="!chatMessages.length" class="flex flex-center q-py-xl text-grey-4" style="flex-direction:column;gap:8px">
            <q-icon name="chat_bubble_outline" size="40px" />
            <div class="text-caption">Ask me anything about your producer analytics</div>
          </div>
          <div v-for="(msg, i) in chatMessages" :key="i" :class="msg.role === 'user' ? 'chat-msg chat-msg--user' : 'chat-msg chat-msg--ai'">
            <div class="chat-bubble" :class="msg.role === 'user' ? 'chat-bubble--user' : 'chat-bubble--ai'">
              {{ msg.text }}
            </div>
          </div>
          <div v-if="chatTyping" class="chat-msg chat-msg--ai">
            <div class="chat-bubble chat-bubble--ai" style="padding:8px 14px"><q-spinner-dots color="deep-purple-4" size="20px" /></div>
          </div>
        </div>
        <div class="row items-center" style="gap:8px">
          <q-input v-model="chatInput" outlined dense placeholder="Ask a question about producers..." style="flex:1" bg-color="white" @keyup.enter="sendChat" />
          <q-btn unelevated color="deep-purple-5" icon="send" :loading="chatTyping" :disable="!chatInput.trim()" @click="sendChat" />
        </div>
      </div>
      </template><!-- /ai_chat -->

    </template>

  </q-page>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { api } from 'boot/axios'

const period    = ref('all')
const section   = ref('overview')
const sections  = [
  { key: 'overview',   label: 'Overview',     icon: 'bar_chart' },
  { key: 'deep_dive',  label: 'Deep Dive',    icon: 'analytics' },
  { key: 'ai_chat',    label: 'AI Chat',      icon: 'smart_toy' },
]
const data      = ref(null)
const loading   = ref(false)

const todayStr  = new Date().toISOString().slice(0, 10)

function fmtConnDate(iso) {
  if (!iso) return '—'
  return new Date(iso + 'T12:00:00').toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
}
function connDaysLabel(iso, isOverdue) {
  if (!iso) return ''
  const diff = Math.round((new Date(iso + 'T12:00:00') - new Date()) / 86400000)
  if (diff === 0) return 'today'
  if (isOverdue) return `${Math.abs(diff)}d overdue`
  return `in ${diff}d`
}
function connDaysStyle(iso, isOverdue) {
  if (!iso) return ''
  const diff = Math.round((new Date(iso + 'T12:00:00') - new Date()) / 86400000)
  if (isOverdue) return 'color:#C62828;font-weight:700;'
  if (diff <= 7)  return 'color:#E65100;font-weight:600;'
  if (diff <= 30) return 'color:#F57F17;'
  return 'color:#757575;'
}
const customFrom = ref('')
const customTo   = ref(todayStr)

async function load() {
  if (period.value === 'custom') return
  loading.value = true
  try {
    const res = await api.get('/producers/analytics/', { params: { period: period.value } })
    data.value = res.data
  } finally {
    loading.value = false
  }
}

async function loadCustom() {
  if (!customFrom.value || !customTo.value) return
  loading.value = true
  try {
    const res = await api.get('/producers/analytics/', {
      params: { period: 'custom', date_from: customFrom.value, date_to: customTo.value },
    })
    data.value = res.data
  } finally {
    loading.value = false
  }
}

function onDateChange() {
  if (customFrom.value && customTo.value && customFrom.value <= customTo.value) loadCustom()
}

watch(period, (v) => { if (v !== 'custom') load() }, { immediate: true })

const periodLabel = computed(() => {
  if (period.value === 'custom' && customFrom.value && customTo.value) {
    const fmt = s => new Date(s + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    return `${fmt(customFrom.value)} – ${fmt(customTo.value)}`
  }
  return { today: 'Today', week: 'Last 7 Days', month: 'Last 30 Days', all: 'All Time' }[period.value] || ''
})

const customDayCount = computed(() => {
  if (!customFrom.value || !customTo.value) return 0
  return Math.round((new Date(customTo.value) - new Date(customFrom.value)) / 86400000) + 1
})

const convRate = computed(() => {
  if (!data.value) return null
  const total = data.value.totals.onboarding + data.value.totals.moved_to_support
  if (!total) return null
  return Math.round(data.value.totals.moved_to_support / total * 100)
})

const weeklyMax = computed(() =>
  Math.max(...(data.value?.weekly_new?.map(w => w.count) || [0]), 1)
)

const teamTotals = computed(() => {
  const ops = data.value?.operators || []
  return {
    assigned:         ops.reduce((s, o) => s + o.assigned, 0),
    advanced:         ops.reduce((s, o) => s + o.advanced, 0),
    moved_to_support: ops.reduce((s, o) => s + o.moved_to_support, 0),
    stopped:          ops.reduce((s, o) => s + o.stopped, 0),
  }
})

const teamConv = computed(() => {
  const t = teamTotals.value
  return t.assigned ? Math.round(t.moved_to_support / t.assigned * 100) : 0
})

function initials(name) {
  return (name || '?').split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

const stageColors = {
  interest:          '#F44336',
  in_communication:  '#FF9800',
  terms_negotiation: '#EF6C00',
  negotiation:       '#9C27B0',
  contract_signed:   '#1565C0',
  on_platform:       '#2E7D32',
  stopped:           '#757575',
}

function stageColor(key) {
  return stageColors[key] || '#9E9E9E'
}

const supportStageColors = {
  agreed:           '#5C6BC0',
  signed:           '#1565C0',
  products_received:'#0097A7',
  ready_to_sell:    '#2E7D32',
  in_store:         '#43A047',
}
function supportStageColor(key) {
  return supportStageColors[key] || '#9E9E9E'
}

const weeklyCommentsMax = computed(() =>
  Math.max(...(data.value?.weekly_comments?.map(w => w.count) || [0]), 1)
)
const countryMax = computed(() =>
  Math.max(...(data.value?.by_country?.map(c => c.count) || [0]), 1)
)
const productTypeMax = computed(() =>
  Math.max(...(data.value?.by_product_type?.map(p => p.count) || [0]), 1)
)

// ── AI Chat ──────────────────────────────────────────────────────────────────
const chatMessages = ref([])
const chatInput    = ref('')
const chatTyping   = ref(false)
const chatBox      = ref(null)

function buildChatContext() {
  if (!data.value) return {}
  const d = data.value
  return {
    onboarding:       d.totals.onboarding,
    support:          d.totals.support,
    stopped:          d.totals.stopped,
    moved_to_support: d.totals.moved_to_support,
    top_stages:       (d.by_stage || []).slice(0, 4).map(s => ({ label: s.label, count: s.count, avg_days: s.avg_days })),
    task_total:       d.task_stats?.total,
    task_overdue:     d.task_stats?.overdue,
    task_completion:  d.task_stats?.completion_rate,
    top_countries:    (d.by_country || []).slice(0, 5).map(c => ({ country: c.country, count: c.count })),
    top_products:     (d.by_product_type || []).slice(0, 5).map(p => ({ type: p.product_type, count: p.count })),
  }
}

async function sendChat() {
  const q = chatInput.value.trim()
  if (!q || chatTyping.value) return
  chatMessages.value.push({ role: 'user', text: q })
  chatInput.value = ''
  chatTyping.value = true
  await nextTick()
  if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight

  try {
    const res = await api.post('/analytics/ai-chat/', {
      question: q,
      context:  buildChatContext(),
      section:  'producers',
    })
    chatMessages.value.push({ role: 'ai', text: res.data.answer || res.data.error || 'No response' })
  } catch (e) {
    chatMessages.value.push({ role: 'ai', text: 'Error: ' + (e.response?.data?.error || e.message) })
  } finally {
    chatTyping.value = false
    await nextTick()
    if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
  }
}
</script>

<style scoped>
.analytics-root { background: #F8F9FA; }

/* Period custom range */
.custom-range-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border: 1px solid #E0E0E0;
  border-radius: 10px;
  padding: 10px 16px;
}
.slide-down-enter-active, .slide-down-leave-active { transition: all 0.2s ease; }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-8px); }

/* KPI grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.kpi-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #F0F0F0;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.kpi-card--good { border-left: 3px solid #43A047; }
.kpi-card--warn { border-left: 3px solid #EF5350; }
.kpi-icon {
  width: 40px; height: 40px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.kpi-val   { font-size: 24px; font-weight: 800; line-height: 1.1; }
.kpi-label { font-size: 11px; color: #9E9E9E; margin-top: 2px; }

/* Two-column card grid */
.two-col {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 14px;
}

.acard {
  background: #fff;
  border-radius: 14px;
  border: 1px solid #F0F0F0;
  padding: 20px;
}
.acard-header { display: flex; flex-direction: column; gap: 2px; }
.acard-title  { font-size: 14px; font-weight: 700; color: #212121; }

/* Stage funnel rows */
.stage-row {
  display: grid;
  grid-template-columns: 170px 1fr 100px;
  align-items: center;
  gap: 12px;
}
.stage-label-wrap {
  display: flex; align-items: center; gap: 7px;
}
.stage-dot  { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.stage-label { font-size: 12px; font-weight: 600; color: #424242; }
.stage-bar-wrap { min-width: 0; }
.stage-bar-bg   { height: 10px; background: #F5F5F5; border-radius: 5px; overflow: hidden; }
.stage-bar-fill { height: 100%; border-radius: 5px; transition: width 0.4s ease; }
.stage-meta {
  display: flex; align-items: center; gap: 8px;
  justify-content: flex-end;
}
.stage-count { font-size: 14px; font-weight: 800; }
.stage-pct   { font-size: 11px; }
.stage-days  { font-size: 10px; }

/* Weekly bar chart */
.weekly-chart {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 140px;
  padding-bottom: 24px;
  position: relative;
}
.weekly-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}
.weekly-bar-wrap {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
}
.weekly-bar {
  width: 100%;
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  transition: height 0.3s ease;
}
.weekly-label { font-size: 9px; color: #BDBDBD; margin-top: 4px; white-space: nowrap; }
.weekly-count { font-size: 10px; font-weight: 700; }

/* Operator table */
.op-table-wrap { overflow-x: auto; }
.op-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.op-table thead tr { border-bottom: 2px solid #F0F0F0; }
.op-table th {
  padding: 8px 12px;
  text-align: left;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #9E9E9E;
  white-space: nowrap;
}
.op-table td { padding: 10px 12px; border-bottom: 1px solid #F8F8F8; }
.col-operator { min-width: 160px; }
.cell-center  { text-align: center; }
.op-row:hover td { background: #FAFAFA; }
.totals-row td {
  border-top: 2px solid #F0F0F0 !important;
  border-bottom: none !important;
  padding: 12px;
  font-size: 12px;
}

.num-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 26px;
  height: 20px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 700;
  padding: 0 6px;
  background: #E3F2FD;
  color: #1565C0;
}
.num--orange { background: #FFF3E0; color: #E65100; }
.num-dim  { color: #BDBDBD; font-size: 12px; }
.conv-good { font-size: 12px; font-weight: 700; color: #2E7D32; }
.conv-mid  { font-size: 12px; font-weight: 600; color: #E65100; }

/* Section switcher */
.section-btn {
  display: inline-flex;
  align-items: center;
  padding: 7px 18px;
  border-radius: 20px;
  border: 1.5px solid #E0E0E0;
  background: #fff;
  font-size: 13px;
  font-weight: 600;
  color: #757575;
  cursor: pointer;
  transition: all 0.15s;
}
.section-btn:hover { border-color: #9FA8DA; color: #3949AB; background: #F3F4FF; }
.section-btn--active { border-color: #3F51B5; background: #3F51B5; color: #fff; }
.section-btn--active:hover { background: #3949AB; border-color: #3949AB; color: #fff; }

/* Seg rows for countries / product types */
.seg-row {
  display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
}
.seg-label {
  font-size: 12px; color: #424242;
  width: 120px; flex-shrink: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.seg-bars { flex: 1; min-width: 0; }
.seg-bar-wrap { height: 6px; background: #F5F5F5; border-radius: 3px; overflow: hidden; }
.seg-bar { height: 100%; border-radius: 3px; transition: width 0.4s ease; min-width: 1px; }
.seg-chip {
  font-size: 10px; font-weight: 700; padding: 2px 6px;
  border-radius: 8px; white-space: nowrap;
}
.seg-chip--count { background: #E3F2FD; color: #1565C0; }

/* AI Chat */
.chat-box { padding: 4px; }
.chat-msg { display: flex; }
.chat-msg--user { justify-content: flex-end; }
.chat-msg--ai   { justify-content: flex-start; }
.chat-bubble {
  max-width: 75%; padding: 10px 14px;
  border-radius: 14px; font-size: 13px; line-height: 1.55; white-space: pre-wrap;
}
.chat-bubble--user { background: #3F51B5; color: #fff; border-bottom-right-radius: 4px; }
.chat-bubble--ai   { background: #F5F5F5; color: #212121; border-bottom-left-radius: 4px; }
</style>
