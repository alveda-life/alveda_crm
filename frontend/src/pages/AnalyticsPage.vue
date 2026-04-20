<template>
  <q-page class="analytics-root q-pa-lg">

    <!-- ══════════════════════════ HEADER ══════════════════════════════ -->
    <div class="row items-center justify-between q-mb-md">
      <div>
        <div class="text-h5 text-weight-bold text-dark">Analytics</div>
        <div class="text-caption text-grey-6 q-mt-xs">
          Partner pipeline health &amp; operator performance
        </div>
      </div>
      <q-btn flat round icon="refresh" color="grey-6" :loading="loading" @click="load">
        <q-tooltip>Refresh</q-tooltip>
      </q-btn>
    </div>

    <!-- Section switcher -->
    <div class="row items-center q-mb-md" style="gap:8px">
      <button
        v-for="s in sections" :key="s.key"
        class="section-btn"
        :class="section === s.key ? 'section-btn--active' : ''"
        @click="section = s.key"
      >
        <q-icon :name="s.icon" size="15px" style="margin-right:5px" />
        {{ s.label }}
      </button>
    </div>

    <!-- Period tabs -->
    <div class="row items-center q-mb-lg" style="gap:0">
      <q-tabs v-model="period" dense align="left"
        active-color="primary" indicator-color="primary"
        style="flex-shrink:0"
      >
        <q-tab name="today" label="Today" />
        <q-tab name="week"  label="Last 7 Days" />
        <q-tab name="month" label="Last 30 Days" />
        <q-tab name="all"   label="All Time" />
        <q-tab name="custom" label="Custom range" icon="date_range" />
      </q-tabs>
    </div>

    <!-- Custom date range picker -->
    <transition name="slide-down">
      <div v-if="period === 'custom'" class="custom-range-bar q-mb-lg">
        <q-icon name="date_range" color="primary" size="18px" />
        <span class="text-caption text-grey-6">From</span>
        <q-input
          v-model="customFrom"
          type="date"
          dense outlined
          :max="customTo || todayStr"
          hide-bottom-space
          style="width:148px"
          bg-color="white"
          @update:model-value="onCustomDateChange"
        />
        <span class="text-caption text-grey-5">—</span>
        <span class="text-caption text-grey-6">To</span>
        <q-input
          v-model="customTo"
          type="date"
          dense outlined
          :min="customFrom || undefined"
          :max="todayStr"
          hide-bottom-space
          style="width:148px"
          bg-color="white"
          @update:model-value="onCustomDateChange"
        />
        <q-btn
          unelevated color="primary" label="Apply"
          dense style="height:36px; padding:0 16px; border-radius:8px"
          :disable="!customFrom || !customTo"
          @click="loadCustom"
        />
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

      <!-- ══════════════════ PARTNER ANALYTICS ══════════════════════════ -->
      <template v-if="section === 'partners'">

      <!-- Partner KPIs -->
      <div class="kpi-grid q-mb-lg">

        <div class="kpi-card">
          <div class="kpi-icon" style="background:#E3F2FD">
            <q-icon name="people" color="blue-7" size="20px" />
          </div>
          <div>
            <div class="kpi-val">{{ data.overview.total_partners }}</div>
            <div class="kpi-label">Total Partners</div>
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-icon" style="background:#E8F5E9">
            <q-icon name="trending_up" color="green-7" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#2E7D32">{{ data.overview.active_partners }}</div>
            <div class="kpi-label">Active in Pipeline</div>
          </div>
        </div>

        <div class="kpi-card" :class="data.overview.dead_rate > 40 ? 'kpi-card--alert' : ''">
          <div class="kpi-icon" style="background:#FFEBEE">
            <q-icon name="person_remove" color="red-6" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#C62828">{{ data.overview.dead_partners }}</div>
            <div class="kpi-label">Dead ({{ data.overview.dead_rate }}%)</div>
          </div>
        </div>

        <div class="kpi-card" :class="data.overview.unassigned_partners > 0 ? 'kpi-card--warn' : ''">
          <div class="kpi-icon" style="background:#FFF3E0">
            <q-icon name="person_off" color="orange-7" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#E65100">{{ data.overview.unassigned_partners }}</div>
            <div class="kpi-label">Unassigned (active)</div>
          </div>
        </div>

        <div class="kpi-card" :class="data.overview.never_contacted > 0 ? 'kpi-card--warn' : ''">
          <div class="kpi-icon" style="background:#FCE4EC">
            <q-icon name="voice_over_off" color="pink-6" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#AD1457">{{ data.overview.never_contacted }}</div>
            <div class="kpi-label">Never Contacted</div>
          </div>
        </div>

        <div class="kpi-card" :class="data.overview.stagnant_partners > 0 ? 'kpi-card--warn' : ''">
          <div class="kpi-icon" style="background:#F3E5F5">
            <q-icon name="hourglass_empty" color="purple-6" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#6A1B9A">{{ data.overview.stagnant_partners }}</div>
            <div class="kpi-label">Stagnant &gt;21d</div>
          </div>
        </div>

      </div>

      <!-- Donut Charts Row -->
      <div class="two-col q-mb-lg" style="grid-template-columns: repeat(3, 1fr)">

        <!-- Stage donut -->
        <div class="acard">
          <div class="acard-title q-mb-md">Stage Distribution</div>
          <DonutChart :items="stagePieItems" centerLabel="Partners" />
        </div>

        <!-- Category donut -->
        <div class="acard">
          <div class="acard-title q-mb-md">By Category</div>
          <DonutChart :items="categoryPieItems" centerLabel="Partners" />
        </div>

        <!-- Type donut -->
        <div class="acard">
          <div class="acard-title q-mb-md">Type Split</div>
          <DonutChart :items="typePieItems" centerLabel="Partners" />
        </div>

      </div>

      <!-- ══════════════ PIPELINE VELOCITY ═════════════════════════════════ -->
      <div class="acard q-mb-lg">
        <div class="acard-header q-mb-md">
          <div class="acard-title">Pipeline Velocity</div>
          <div class="text-caption text-grey-5">avg days partners spend at each stage · stuck = exceeded healthy threshold</div>
        </div>
        <div class="velocity-grid">
          <div v-for="vs in data.pipeline_velocity" :key="vs.stage" class="velocity-card">
            <div class="velocity-stage-label">{{ vs.label }}</div>
            <div class="velocity-count">{{ vs.count }} <span style="font-size:11px;font-weight:400;color:#9E9E9E">partners</span></div>
            <div class="velocity-age" :style="`color:${vs.avg_age_days > (vs.stuck_threshold || 999) ? '#C62828' : '#2E7D32'}`">
              {{ vs.avg_age_days }}d avg
            </div>
            <div v-if="vs.stuck_threshold" class="velocity-stuck" :class="vs.stuck > 0 ? 'velocity-stuck--bad' : 'velocity-stuck--ok'">
              {{ vs.stuck > 0 ? `⚠ ${vs.stuck} stuck &gt;${vs.stuck_threshold}d` : `✓ None stuck` }}
            </div>
            <div class="velocity-bar-wrap">
              <div class="velocity-bar"
                :style="`width:${Math.min((vs.avg_age_days / ((vs.stuck_threshold||vs.avg_age_days||1)*1.5))*100,100)}%;background:${vs.avg_age_days > (vs.stuck_threshold||999)?'#EF5350':'#66BB6A'}`"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- ══════════════ FINANCIAL KPIs ═══════════════════════════════════ -->
      <div class="fin-section-header q-mb-sm">
        <q-icon name="payments" size="15px" color="green-7" />
        Financial Overview
        <span class="text-caption text-grey-5" style="font-weight:400;margin-left:4px">lifetime · all partners</span>
      </div>
      <div class="kpi-grid q-mb-lg">

        <div class="kpi-card kpi-card--fin">
          <div class="kpi-icon" style="background:#E8F5E9">
            <q-icon name="attach_money" color="green-8" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#1B5E20">{{ fmtMoney(data.financials.total_revenue) }}</div>
            <div class="kpi-label">Total Revenue</div>
          </div>
        </div>

        <div class="kpi-card kpi-card--fin" :class="data.financials.total_unpaid > 0 ? 'kpi-card--warn' : ''">
          <div class="kpi-icon" style="background:#FFF8E1">
            <q-icon name="pending" color="amber-8" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#F57F17">{{ fmtMoney(data.financials.total_unpaid) }}</div>
            <div class="kpi-label">Unpaid Pipeline</div>
          </div>
        </div>

        <div class="kpi-card kpi-card--fin">
          <div class="kpi-icon" style="background:#E3F2FD">
            <q-icon name="shopping_cart" color="blue-7" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#1565C0">{{ data.financials.total_orders }}</div>
            <div class="kpi-label">Orders Total</div>
          </div>
        </div>

        <div class="kpi-card kpi-card--fin">
          <div class="kpi-icon" style="background:#E8F5E9">
            <q-icon name="check_circle" color="green-7" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#2E7D32">{{ data.financials.total_paid_orders }}</div>
            <div class="kpi-label">Paid Orders ({{ data.financials.paid_order_rate }}%)</div>
          </div>
        </div>

        <div class="kpi-card kpi-card--fin">
          <div class="kpi-icon" style="background:#EDE7F6">
            <q-icon name="medical_services" color="deep-purple-6" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#4527A0">{{ data.financials.total_sets }}</div>
            <div class="kpi-label">Medical Sets</div>
          </div>
        </div>

        <div class="kpi-card kpi-card--fin">
          <div class="kpi-icon" style="background:#FCE4EC">
            <q-icon name="share" color="pink-6" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#AD1457">{{ data.financials.total_referrals }}</div>
            <div class="kpi-label">Referrals</div>
          </div>
        </div>

        <div class="kpi-card kpi-card--fin">
          <div class="kpi-icon" style="background:#E0F2F1">
            <q-icon name="person_4" color="teal-7" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#00695C">{{ fmtMoney(data.financials.avg_revenue_per_partner) }}</div>
            <div class="kpi-label">Avg Revenue / partner</div>
          </div>
        </div>

      </div>

      <!-- ══════════════ FUNNEL + CONVERSION + DEAD ════════════════════ -->
      <div class="two-col q-mb-lg">

        <!-- Pipeline Funnel (wider) -->
        <div class="acard" style="grid-column: span 7 / span 7">
          <div class="acard-header">
            <div class="acard-title">Partner Pipeline</div>
            <div class="text-caption text-grey-5">current state of all {{ data.overview.total_partners }} partners</div>
          </div>

          <div class="funnel-section-label q-mb-sm">Active</div>
          <div v-for="item in activeFunnel" :key="item.stage" class="funnel-row q-mb-xs">
            <div class="funnel-label">{{ item.label }}</div>
            <div class="funnel-track">
              <div class="funnel-bar"
                :style="`width:${barWidthPct(item.count)}%;background:${item.color}`" />
            </div>
            <div class="funnel-count">{{ item.count }}</div>
            <div class="funnel-pct">{{ totalPct(item.count) }}%</div>
          </div>

          <q-separator class="q-my-md" />

          <div class="funnel-section-label q-mb-sm" style="color:#C62828">Dead</div>
          <div v-for="item in deadFunnel" :key="item.stage" class="funnel-row q-mb-xs">
            <div class="funnel-label">{{ item.label }}</div>
            <div class="funnel-track">
              <div class="funnel-bar"
                :style="`width:${barWidthPct(item.count)}%;background:${item.color}`" />
            </div>
            <div class="funnel-count">{{ item.count }}</div>
            <div class="funnel-pct">{{ totalPct(item.count) }}%</div>
          </div>
        </div>

        <!-- Right panel -->
        <div style="grid-column: span 5 / span 5; display:flex; flex-direction:column; gap:12px;">

          <!-- Conversion rates -->
          <div class="acard" style="flex:1">
            <div class="acard-header">
              <div class="acard-title">Funnel Conversion</div>
              <div class="text-caption text-grey-5">% of all partners at or past stage</div>
            </div>

            <div class="conv-item q-mb-md">
              <div class="conv-label">Reached Agreed to Create First Set</div>
              <div class="conv-track">
                <div class="conv-fill" :style="`width:${Math.min(data.conversion.to_trained,100)}%;background:#FFB300`" />
              </div>
              <div class="conv-pct" style="color:#F57F17">{{ data.conversion.to_trained }}%</div>
            </div>
            <div class="conv-item q-mb-md">
              <div class="conv-label">Reached Set Created</div>
              <div class="conv-track">
                <div class="conv-fill" :style="`width:${Math.min(data.conversion.to_set_created,100)}%;background:#29B6F6`" />
              </div>
              <div class="conv-pct" style="color:#0277BD">{{ data.conversion.to_set_created }}%</div>
            </div>
            <div class="conv-item">
              <div class="conv-label">Reached Has Sale</div>
              <div class="conv-track">
                <div class="conv-fill" :style="`width:${Math.min(data.conversion.to_sale,100)}%;background:#43A047`" />
              </div>
              <div class="conv-pct" style="color:#2E7D32">{{ data.conversion.to_sale }}%</div>
            </div>
          </div>

          <!-- Dead breakdown -->
          <div class="acard" style="flex:1">
            <div class="acard-header">
              <div class="acard-title">Dead Breakdown</div>
              <div class="text-caption text-grey-5">
                <span v-if="data.overview.dead_partners > 0">
                  {{ data.overview.dead_partners }} partners lost
                </span>
                <span v-else style="color:#4CAF50">No dead partners yet</span>
              </div>
            </div>

            <template v-if="data.overview.dead_partners > 0">
              <div v-for="item in deadFunnel" :key="item.stage" class="q-mb-sm">
                <div class="row items-center justify-between q-mb-xs">
                  <div class="row items-center" style="gap:6px">
                    <div :style="`width:8px;height:8px;border-radius:50%;background:${item.color};flex-shrink:0`" />
                    <span style="font-size:12px;color:#616161">{{ item.label }}</span>
                  </div>
                  <span class="text-caption text-weight-bold text-dark">{{ item.count }}</span>
                </div>
                <q-linear-progress
                  :value="item.count / data.overview.dead_partners"
                  :color="deadQColor(item.stage)"
                  track-color="grey-2"
                  size="5px" rounded
                />
              </div>
            </template>
            <div v-else class="text-center q-py-md">
              <q-icon name="check_circle" color="green-4" size="32px" />
            </div>
          </div>

        </div>
      </div>

      <!-- ══════════════ PARTNER GROWTH CHART ══════════════════════════ -->
      <div class="acard q-mb-lg">
        <div class="acard-header q-mb-md">
          <div class="acard-title">Partner Growth</div>
          <div class="text-caption text-grey-5">new partners added — {{ periodLabel }}</div>
        </div>
        <LineChart
          :data="growthData"
          label-key="label"
          :series="[{ key: 'new', label: 'New Partners', color: '#42A5F5' }]"
          :show-legend="false"
        />
      </div>

      <!-- ══════════════ SALES DEPTH TIME SERIES ══════════════════════════ -->
      <div class="acard q-mb-lg">
        <div class="acard-header q-mb-md">
          <div class="acard-title">Sales Depth — Weekly Growth</div>
          <div class="text-caption text-grey-5">cumulative partners who have reached each sales threshold · last 16 weeks</div>
        </div>
        <LineChart
          :data="salesDepthData"
          label-key="label"
          :series="[
            { key: '1plus',  label: '1+ Sales',  color: '#66BB6A' },
            { key: '3plus',  label: '3+ Sales',  color: '#29B6F6' },
            { key: '5plus',  label: '5+ Sales',  color: '#FFA726' },
            { key: '10plus', label: '10+ Sales', color: '#AB47BC' },
          ]"
        />
      </div>

      <!-- ══════════════ BREAKDOWN GRID: Category / Type / Gender ════════ -->
      <div class="two-col q-mb-lg">

        <!-- By Category (with conversion) -->
        <div class="acard" style="grid-column: span 5 / span 5">
          <div class="acard-title q-mb-md">By Category — Conversion</div>
          <div v-for="cat in data.by_category" :key="cat.key" class="seg-row">
            <div class="seg-label">{{ cat.label }}</div>
            <div class="seg-bars">
              <div class="seg-bar-wrap">
                <div class="seg-bar seg-bar--total" :style="`width:${catMax > 0 ? cat.count/catMax*100 : 0}%`" />
              </div>
              <div class="seg-bar-wrap" style="background:#FFF8E1">
                <div class="seg-bar" :style="`width:${cat.conv_sale}%;background:#43A047`" />
              </div>
            </div>
            <div style="display:flex;gap:6px;flex-shrink:0">
              <span class="seg-chip seg-chip--count">{{ cat.count }}</span>
              <span class="seg-chip seg-chip--sale">{{ cat.conv_sale }}%</span>
              <span class="seg-chip seg-chip--dead" v-if="cat.dead_rate > 0">💀{{ cat.dead_rate }}%</span>
            </div>
          </div>
        </div>

        <!-- By Type + Gender -->
        <div style="grid-column: span 7 / span 7; display:flex; flex-direction:column; gap:14px">
          <div class="acard" style="flex:1">
            <div class="acard-title q-mb-sm">By Type — Conversion</div>
            <div v-for="t in data.by_type" :key="t.key" class="seg-row">
              <div class="seg-label">{{ t.label }}</div>
              <div class="seg-bars">
                <div class="seg-bar-wrap">
                  <div class="seg-bar seg-bar--total" :style="`width:${typeMax > 0 ? t.count/typeMax*100 : 0}%;background:#29B6F6`" />
                </div>
                <div class="seg-bar-wrap" style="background:#FFF8E1">
                  <div class="seg-bar" :style="`width:${t.conv_sale}%;background:#43A047`" />
                </div>
              </div>
              <div style="display:flex;gap:6px;flex-shrink:0">
                <span class="seg-chip seg-chip--count">{{ t.count }}</span>
                <span class="seg-chip seg-chip--sale">{{ t.conv_sale }}%</span>
              </div>
            </div>
          </div>

          <div class="acard" style="flex:1">
            <div class="acard-title q-mb-sm">By Gender</div>
            <div v-for="g in data.by_gender" :key="g.key" class="seg-row">
              <div class="seg-label">{{ g.label }}</div>
              <div class="seg-bars">
                <div class="seg-bar-wrap">
                  <div class="seg-bar" :style="`width:${genderMax > 0 ? g.count/genderMax*100 : 0}%;background:#AB47BC`" />
                </div>
                <div class="seg-bar-wrap" style="background:#FFF8E1">
                  <div class="seg-bar" :style="`width:${g.conv_sale}%;background:#43A047`" />
                </div>
              </div>
              <div style="display:flex;gap:6px;flex-shrink:0">
                <span class="seg-chip seg-chip--count">{{ g.count }}</span>
                <span class="seg-chip seg-chip--sale">{{ g.conv_sale }}%</span>
              </div>
            </div>
            <div v-if="!data.by_gender?.length" class="text-caption text-grey-5 q-mt-sm">No gender data</div>
          </div>
        </div>
      </div>

      <!-- ══════════════ GEOGRAPHY + REFERRALS ════════════════════════════ -->
      <div class="two-col q-mb-lg" v-if="data.by_state?.length || data.by_referral?.length">

        <div v-if="data.by_state?.length" class="acard" style="grid-column: span 6 / span 6">
          <div class="acard-title q-mb-md">Top Regions</div>
          <div v-for="s in data.by_state" :key="s.state" class="seg-row">
            <div class="seg-label" style="max-width:110px">{{ s.state }}</div>
            <div class="seg-bars">
              <div class="seg-bar-wrap">
                <div class="seg-bar seg-bar--total" :style="`width:${stateMax > 0 ? s.count/stateMax*100 : 0}%`" />
              </div>
              <div class="seg-bar-wrap" style="background:#FFF8E1">
                <div class="seg-bar" :style="`width:${s.conv_sale}%;background:#43A047`" />
              </div>
            </div>
            <div style="display:flex;gap:6px;flex-shrink:0">
              <span class="seg-chip seg-chip--count">{{ s.count }}</span>
              <span class="seg-chip seg-chip--sale">{{ s.conv_sale }}%</span>
            </div>
          </div>
        </div>

        <div v-if="data.by_referral?.length" class="acard" style="grid-column: span 6 / span 6">
          <div class="acard-title q-mb-md">Referral Sources</div>
          <div v-for="r in data.by_referral" :key="r.referred_by" class="seg-row">
            <div class="seg-label" style="max-width:110px">{{ r.referred_by }}</div>
            <div class="seg-bars">
              <div class="seg-bar-wrap">
                <div class="seg-bar seg-bar--total" :style="`width:${refMax > 0 ? r.count/refMax*100 : 0}%`" />
              </div>
              <div class="seg-bar-wrap" style="background:#FFF8E1">
                <div class="seg-bar" :style="`width:${r.conv_sale}%;background:#43A047`" />
              </div>
            </div>
            <div style="display:flex;gap:6px;flex-shrink:0">
              <span class="seg-chip seg-chip--count">{{ r.count }}</span>
              <span class="seg-chip seg-chip--sale">{{ r.conv_sale }}%</span>
            </div>
          </div>
        </div>

      </div>

      <!-- ══════════════ WHATSAPP ADOPTION ══════════════════════════════ -->
      <div class="acard q-mb-lg" v-if="data.whatsapp_stats">
        <div class="acard-header q-mb-md">
          <div class="acard-title">WhatsApp Channel Adoption</div>
          <div class="text-caption text-grey-5">active partners added to channel</div>
        </div>
        <div class="row items-center q-mb-lg" style="gap:24px">
          <div style="text-align:center">
            <div style="font-size:40px;font-weight:800;color:#25D366;line-height:1">{{ data.whatsapp_stats.pct }}%</div>
            <div style="font-size:11px;color:#9E9E9E;margin-top:4px">of active partners</div>
          </div>
          <div style="display:flex;gap:16px">
            <div class="kpi-card kpi-card--fin" style="border-color:#25D366">
              <div class="kpi-icon" style="background:#E8F5E9"><q-icon name="check_circle" color="green-7" size="20px" /></div>
              <div><div class="kpi-val" style="color:#1B5E20;font-size:20px">{{ data.whatsapp_stats.added }}</div><div class="kpi-label">Added</div></div>
            </div>
            <div class="kpi-card kpi-card--fin">
              <div class="kpi-icon" style="background:#FFEBEE"><q-icon name="person_off" color="red-5" size="20px" /></div>
              <div><div class="kpi-val" style="color:#C62828;font-size:20px">{{ data.whatsapp_stats.not_added }}</div><div class="kpi-label">Not Added</div></div>
            </div>
          </div>
        </div>
        <div style="font-size:11px;font-weight:700;color:#9E9E9E;text-transform:uppercase;letter-spacing:0.6px;margin-bottom:8px">By Stage</div>
        <div v-for="(ws, stage) in data.whatsapp_stats.by_stage" :key="stage" class="seg-row">
          <div class="seg-label">{{ stageLabel(stage) }}</div>
          <div class="seg-bars">
            <div class="seg-bar-wrap">
              <div class="seg-bar" :style="`width:${ws.pct}%;background:#25D366`" />
            </div>
          </div>
          <div style="display:flex;gap:6px;flex-shrink:0;align-items:center">
            <span class="seg-chip" style="background:#E8F5E9;color:#1B5E20">{{ ws.added }}/{{ ws.total }}</span>
            <span class="seg-chip seg-chip--sale">{{ ws.pct }}%</span>
          </div>
        </div>
      </div>

      <!-- ══════════════ TOP 10 PARTNERS ══════════════════════════════════ -->
      <div class="acard q-mb-lg" v-if="data.top_partners && data.top_partners.length">
        <div class="acard-header q-mb-md">
          <div class="acard-title">Top 10 Partners by Revenue</div>
          <div class="text-caption text-grey-5">lifetime paid orders</div>
        </div>
        <div class="op-table-wrap">
          <table class="op-table">
            <thead>
              <tr>
                <th style="width:40px;text-align:center">#</th>
                <th class="col-operator">Partner</th>
                <th class="cell-center">Revenue</th>
                <th class="cell-center">Paid Orders</th>
                <th class="cell-center">Med. Sets</th>
                <th class="cell-center">Operator</th>
                <th class="cell-center">Stage</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(p, idx) in data.top_partners" :key="p.id" class="op-row">
                <td class="cell-center">
                  <span class="rank-badge" :style="`background:${idx===0?'#FFD700':idx===1?'#C0C0C0':idx===2?'#CD7F32':'#EEEEEE'};color:${idx<3?'#fff':'#9E9E9E'}`">
                    {{ idx + 1 }}
                  </span>
                </td>
                <td><span style="font-weight:600;font-size:12px;color:#212121">{{ p.name }}</span></td>
                <td class="cell-center"><span style="font-weight:700;color:#1B5E20;font-size:12px">{{ fmtMoney(p.paid_orders_sum) }}</span></td>
                <td class="cell-center"><span class="num-chip" style="background:#E8F5E9;color:#2E7D32">{{ p.paid_orders_count }}</span></td>
                <td class="cell-center"><span v-if="p.medical_sets_count" class="num-chip" style="background:#EDE7F6;color:#4527A0">{{ p.medical_sets_count }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center"><span style="font-size:11px;color:#616161">{{ p.operator || '—' }}</span></td>
                <td class="cell-center"><span class="stage-badge" :style="`background:${stageBadgeColor(p.stage)}`">{{ p.stage }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      </template><!-- /partners -->

      <!-- ══════════════════ OPERATOR ANALYTICS ══════════════════════════ -->
      <template v-if="section === 'operators'">

      <!-- Operator KPIs -->
      <div class="kpi-grid q-mb-lg">

        <div class="kpi-card">
          <div class="kpi-icon" style="background:#EDE7F6">
            <q-icon name="phone" color="deep-purple-6" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#4527A0">{{ data.overview.total_calls }}</div>
            <div class="kpi-label">Calls ({{ periodLabel }})</div>
          </div>
        </div>

        <div class="kpi-card" :class="data.overview.miss_rate > 30 ? 'kpi-card--alert' : data.overview.missed_calls > 0 ? 'kpi-card--warn' : ''">
          <div class="kpi-icon" style="background:#FFF3E0">
            <q-icon name="phone_missed" color="orange-8" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#E65100">{{ data.overview.missed_calls }}</div>
            <div class="kpi-label">Missed ({{ data.overview.miss_rate }}%)</div>
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-icon" style="background:#F3E5F5">
            <q-icon name="phone_callback" color="purple-6" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#7B1FA2">{{ teamTotals.callbacks }}</div>
            <div class="kpi-label">Call Back Later</div>
          </div>
        </div>

        <div class="kpi-card" :class="data.overview.overdue_partners > 0 ? 'kpi-card--alert' : ''">
          <div class="kpi-icon" style="background:#FFFDE7">
            <q-icon name="schedule" color="amber-8" size="20px" />
          </div>
          <div>
            <div class="kpi-val" style="color:#F57F17">{{ data.overview.overdue_partners }}</div>
            <div class="kpi-label">
              Overdue
              <span v-if="data.overview.due_today" class="due-badge">
                +{{ data.overview.due_today }} today
              </span>
            </div>
          </div>
        </div>

      </div>

      <!-- ══════════════ CALL ACTIVITY ═══════════════════════════════════ -->
      <div class="acard q-mb-lg">
        <div class="acard-header q-mb-md">
          <div class="acard-title">Call Activity</div>
          <div class="text-caption text-grey-5">calls made · missed · call back later — {{ periodLabel }}</div>
        </div>
        <BarChart
          :data="callData"
          label-key="label"
          :series="[
            { key: 'calls',     label: 'Calls Made',       color: '#5C6BC0' },
            { key: 'missed',    label: 'Missed',            color: '#FF7043' },
            { key: 'callbacks', label: 'Call Back Later',   color: '#AB47BC' },
          ]"
        />
      </div>

      <!-- ══════════════ OPERATOR SCORECARDS ══════════════════════════════ -->
      <div v-if="!data.operators.length" class="acard text-center text-grey-5 q-py-xl q-mb-lg">
        <q-icon name="people_outline" size="40px" class="q-mb-sm" />
        <div>No operators found</div>
      </div>

      <div v-else class="op-cards q-mb-lg">
        <div v-for="(op, rank) in convLeaderboard" :key="op.id" class="op-scorecard">
          <!-- Header -->
          <div class="op-sc-header">
            <div class="op-sc-rank" :style="`background:${rank===0?'#FFD700':rank===1?'#C0C0C0':rank===2?'#CD7F32':'#EEEEEE'}`">
              #{{ rank + 1 }}
            </div>
            <q-avatar size="36px" :color="opAvatarColor(op)" text-color="white" style="font-size:13px;flex-shrink:0">
              {{ initials(op.name) }}
            </q-avatar>
            <div style="flex:1;min-width:0">
              <div class="op-sc-name">{{ op.name }}</div>
              <div class="op-sc-sub">@{{ op.username }} · {{ fromNow(op.last_activity) || 'never' }}</div>
            </div>
            <div class="op-sc-big-conv" :style="`color:${op.conv_sale>=20?'#2E7D32':op.conv_sale>0?'#F57F17':'#BDBDBD'}`">
              {{ op.conv_sale }}%
              <span style="font-size:10px;font-weight:400;color:#9E9E9E;display:block;text-align:right">to sale</span>
            </div>
          </div>

          <!-- Conversion funnel bars -->
          <div class="op-sc-funnel">
            <div class="op-sc-funnel-row">
              <span class="op-sc-fl">Agreed to Create First Set</span>
              <div class="op-sc-ftrack">
                <div class="op-sc-fbar" :style="`width:${op.conv_trained}%;background:#FFB300`" />
              </div>
              <span class="op-sc-fpct">{{ op.conv_trained }}%</span>
            </div>
            <div class="op-sc-funnel-row">
              <span class="op-sc-fl">Set Created</span>
              <div class="op-sc-ftrack">
                <div class="op-sc-fbar" :style="`width:${op.conv_set}%;background:#29B6F6`" />
              </div>
              <span class="op-sc-fpct">{{ op.conv_set }}%</span>
            </div>
            <div class="op-sc-funnel-row">
              <span class="op-sc-fl">Has Sale</span>
              <div class="op-sc-ftrack">
                <div class="op-sc-fbar" :style="`width:${op.conv_sale}%;background:#43A047`" />
              </div>
              <span class="op-sc-fpct" style="color:#2E7D32;font-weight:700">{{ op.conv_sale }}%</span>
            </div>
          </div>

          <!-- Metric grid -->
          <div class="op-sc-metrics">
            <div class="op-sc-metric">
              <div class="op-sc-mval" style="color:#3949AB">{{ op.calls }}</div>
              <div class="op-sc-mlbl">Calls</div>
            </div>
            <div class="op-sc-metric" :class="op.miss_rate > 30 ? 'op-sc-metric--bad' : ''">
              <div class="op-sc-mval" style="color:#D84315">{{ op.miss_rate }}%</div>
              <div class="op-sc-mlbl">Miss rate</div>
            </div>
            <div class="op-sc-metric" :class="op.dead_rate > 30 ? 'op-sc-metric--bad' : ''">
              <div class="op-sc-mval" :style="`color:${op.dead_rate>30?'#C62828':'#616161'}`">{{ op.dead_rate }}%</div>
              <div class="op-sc-mlbl">Dead rate</div>
            </div>
            <div class="op-sc-metric" :class="op.calls_per_sale !== null && op.calls_per_sale < 5 ? 'op-sc-metric--good' : ''">
              <div class="op-sc-mval" style="color:#00695C">{{ op.calls_per_sale !== null ? op.calls_per_sale : '—' }}</div>
              <div class="op-sc-mlbl">Calls/Sale</div>
            </div>
            <div class="op-sc-metric" :class="op.inactive > 0 ? 'op-sc-metric--warn' : ''">
              <div class="op-sc-mval" :style="`color:${op.inactive>0?'#E65100':'#9E9E9E'}`">{{ op.inactive }}</div>
              <div class="op-sc-mlbl">Inactive 14d</div>
            </div>
            <div class="op-sc-metric" :class="op.never_contacted > 0 ? 'op-sc-metric--warn' : ''">
              <div class="op-sc-mval" :style="`color:${op.never_contacted>0?'#AD1457':'#9E9E9E'}`">{{ op.never_contacted }}</div>
              <div class="op-sc-mlbl">Never called</div>
            </div>
            <div class="op-sc-metric">
              <div class="op-sc-mval" style="color:#7B1FA2">{{ op.contact_rate }}%</div>
              <div class="op-sc-mlbl">Contact rate</div>
            </div>
            <div class="op-sc-metric">
              <div class="op-sc-mval" style="color:#2E7D32">{{ op.partners_1sale }}</div>
              <div class="op-sc-mlbl">1+ Sales</div>
            </div>
            <div class="op-sc-metric">
              <div class="op-sc-mval" style="color:#6A1B9A">{{ op.partners_10sale }}</div>
              <div class="op-sc-mlbl">10+ Sales</div>
            </div>
          </div>

          <!-- Portfolio bar -->
          <div class="op-sc-portfolio">
            <div :style="`width:${op.assigned>0?op.active/op.assigned*100:0}%;background:#43A047`" :title="`Active: ${op.active}`" />
            <div :style="`width:${op.assigned>0?op.dead/op.assigned*100:0}%;background:#EF5350`" :title="`Dead: ${op.dead}`" />
          </div>
          <div class="op-sc-portfolio-label">
            <span>{{ op.assigned }} assigned</span>
            <span style="color:#2E7D32">{{ op.active }} active</span>
            <span style="color:#C62828">{{ op.dead }} dead</span>
            <span v-if="op.overdue > 0" style="color:#F57F17">{{ op.overdue }} overdue</span>
            <span v-if="op.revenue > 0" style="color:#00695C">{{ fmtMoney(op.revenue) }} rev</span>
          </div>
        </div>
      </div>

      <!-- ══════════════ OPERATOR FULL TABLE ════════════════════════════════ -->
      <div class="acard q-mb-lg">
        <div class="acard-header q-mb-lg">
          <div class="acard-title">Full Performance Table</div>
          <div class="text-caption text-grey-5">{{ periodLabel }}</div>
        </div>
        <div class="op-table-wrap">
          <table class="op-table">
            <thead>
              <tr>
                <th class="col-operator">Operator</th>
                <th>Calls</th><th>Missed</th><th>Miss%</th><th>CB</th>
                <th class="col-sep">Assigned</th><th>Active</th><th>Dead%</th><th>Overdue</th>
                <th class="col-sep">→Sale%</th><th>Calls/Sale</th>
                <th class="col-sep">Contact%</th><th>Inactive</th><th>Never</th>
                <th class="col-sep">1+</th><th>10+</th><th>Revenue</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="op in data.operators" :key="op.id" class="op-row">
                <td>
                  <div class="row items-center" style="gap:8px">
                    <q-avatar size="28px" :color="opAvatarColor(op)" text-color="white" style="font-size:11px;flex-shrink:0">
                      {{ initials(op.name) }}
                    </q-avatar>
                    <div>
                      <div style="font-weight:600;font-size:12px;color:#212121">{{ op.name }}</div>
                      <div style="font-size:10px;color:#BDBDBD">@{{ op.username }}</div>
                    </div>
                  </div>
                </td>
                <td class="cell-center"><span class="num-chip num--indigo">{{ op.calls }}</span></td>
                <td class="cell-center"><span :class="op.missed>0?'num-chip num--orange':'num-dim'">{{ op.missed }}</span></td>
                <td class="cell-center"><span :class="op.miss_rate>30?'miss-bad':op.miss_rate>0?'miss-ok':'num-dim'">{{ op.miss_rate }}%</span></td>
                <td class="cell-center"><span :class="op.callbacks>0?'num-chip num--purple':'num-dim'">{{ op.callbacks }}</span></td>
                <td class="cell-center col-sep"><b style="font-size:13px">{{ op.assigned }}</b></td>
                <td class="cell-center"><span style="font-size:12px;font-weight:600;color:#2E7D32">{{ op.active }}</span></td>
                <td class="cell-center"><span :class="op.dead_rate>30?'miss-bad':op.dead_rate>0?'miss-ok':'num-dim'">{{ op.dead_rate }}%</span></td>
                <td class="cell-center"><span v-if="op.overdue>0" class="num-chip num--amber">{{ op.overdue }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center col-sep">
                  <div style="display:flex;flex-direction:column;align-items:center;gap:1px">
                    <span :class="op.conv_sale>=20?'conv-good':op.conv_sale>0?'conv-mid':'num-dim'">{{ op.conv_sale }}%</span>
                    <span v-if="op.sale_count>0" style="font-size:9px;color:#9E9E9E">{{ op.sale_count }}p</span>
                  </div>
                </td>
                <td class="cell-center"><span :class="op.calls_per_sale!==null&&op.calls_per_sale<5?'conv-good':op.calls_per_sale!==null?'miss-ok':'num-dim'">{{ op.calls_per_sale !== null ? op.calls_per_sale : '—' }}</span></td>
                <td class="cell-center col-sep"><span :class="op.contact_rate>=80?'conv-good':op.contact_rate>0?'miss-ok':'num-dim'">{{ op.contact_rate }}%</span></td>
                <td class="cell-center"><span v-if="op.inactive>0" class="num-chip num--amber">{{ op.inactive }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center"><span v-if="op.never_contacted>0" class="num-chip num--orange">{{ op.never_contacted }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center col-sep"><span v-if="op.partners_1sale>0" class="num-chip" style="background:#E8F5E9;color:#2E7D32">{{ op.partners_1sale }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center"><span v-if="op.partners_10sale>0" class="num-chip" style="background:#F3E5F5;color:#6A1B9A">{{ op.partners_10sale }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center"><span v-if="op.revenue>0" style="font-size:11px;font-weight:700;color:#2E7D32">{{ fmtMoney(op.revenue) }}</span><span v-else class="num-dim">—</span></td>
              </tr>
            </tbody>
            <tfoot v-if="data.operators.length >= 1">
              <tr class="totals-row">
                <td style="font-size:10px;color:#9E9E9E;font-weight:600;text-transform:uppercase">Team</td>
                <td class="cell-center"><span class="num-chip num--indigo">{{ teamTotals.calls }}</span></td>
                <td class="cell-center"><span class="num-chip num--orange">{{ teamTotals.missed }}</span></td>
                <td class="cell-center"><span :class="teamMissRate>30?'miss-bad':'miss-ok'">{{ teamMissRate }}%</span></td>
                <td class="cell-center"><span class="num-chip num--purple">{{ teamTotals.callbacks }}</span></td>
                <td class="cell-center col-sep"><b style="font-size:13px">{{ teamTotals.assigned }}</b></td>
                <td class="cell-center"><span style="font-size:12px;font-weight:600;color:#2E7D32">{{ teamTotals.active }}</span></td>
                <td class="cell-center"><span :class="teamDeadRate>30?'miss-bad':'miss-ok'">{{ teamDeadRate }}%</span></td>
                <td class="cell-center"><span v-if="teamTotals.overdue>0" class="num-chip num--amber">{{ teamTotals.overdue }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center col-sep"><span :class="teamSaleConv>=20?'conv-good':'conv-mid'">{{ teamSaleConv }}%</span></td>
                <td class="cell-center"><span class="miss-ok">{{ teamCallsPerSale !== null ? teamCallsPerSale : '—' }}</span></td>
                <td class="cell-center col-sep"><span class="miss-ok">{{ teamContactRate }}%</span></td>
                <td class="cell-center"><span v-if="teamTotals.inactive>0" class="num-chip num--amber">{{ teamTotals.inactive }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center"><span v-if="teamTotals.never_contacted>0" class="num-chip num--orange">{{ teamTotals.never_contacted }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center col-sep"><span class="num-chip" style="background:#E8F5E9;color:#2E7D32">{{ teamTotals.partners_1sale }}</span></td>
                <td class="cell-center"><span class="num-chip" style="background:#F3E5F5;color:#6A1B9A">{{ teamTotals.partners_10sale }}</span></td>
                <td class="cell-center"><span v-if="teamTotals.revenue>0" style="font-size:11px;font-weight:700;color:#2E7D32">{{ fmtMoney(teamTotals.revenue) }}</span></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- ══════════════ CALL QUALITY ══════════════════════════════════════ -->
      <div class="acard q-mb-lg" v-if="scoredOperators.length">
        <div class="acard-header q-mb-md">
          <div class="acard-title">AI Call Quality Scores</div>
          <div class="text-caption text-grey-5">operators with at least 1 AI-scored call</div>
        </div>
        <div class="op-table-wrap">
          <table class="op-table">
            <thead>
              <tr>
                <th class="col-operator">Operator</th>
                <th class="cell-center">Scored Calls</th>
                <th class="cell-center">Avg Survey<br><span style="font-weight:400;font-size:9px">(1–10)</span></th>
                <th class="cell-center">Avg Explanation<br><span style="font-weight:400;font-size:9px">(1–10)</span></th>
                <th class="cell-center">Avg Overall<br><span style="font-weight:400;font-size:9px">(1–10)</span></th>
                <th class="cell-center">Avg Duration</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="op in scoredOperators" :key="op.id" class="op-row">
                <td>
                  <div class="row items-center" style="gap:8px">
                    <q-avatar size="28px" :color="opAvatarColor(op)" text-color="white" style="font-size:11px;flex-shrink:0">{{ initials(op.name) }}</q-avatar>
                    <div>
                      <div style="font-weight:600;font-size:12px;color:#212121">{{ op.name }}</div>
                      <div style="font-size:10px;color:#BDBDBD">@{{ op.username }}</div>
                    </div>
                  </div>
                </td>
                <td class="cell-center"><span class="num-chip num--indigo">{{ op.scored_calls }}</span></td>
                <td class="cell-center"><span class="quality-badge" :style="qualityStyle(op.avg_survey)">{{ op.avg_survey ?? '—' }}</span></td>
                <td class="cell-center"><span class="quality-badge" :style="qualityStyle(op.avg_explanation)">{{ op.avg_explanation ?? '—' }}</span></td>
                <td class="cell-center"><span class="quality-badge" :style="qualityStyle(op.avg_overall)">{{ op.avg_overall ?? '—' }}</span></td>
                <td class="cell-center"><span style="font-size:11px;color:#616161">{{ op.avg_duration ? op.avg_duration + 's' : '—' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      </template><!-- /operators -->

      <!-- ══════════════════ OPERATOR UTILIZATION ════════════════════════════ -->
      <template v-if="section === 'operator_utilization'">

      <!-- Loader / empty state -->
      <div v-if="utilizationLoading" class="acard text-center text-grey-5 q-py-xl q-mb-lg">
        <q-spinner size="32px" class="q-mb-sm" /><div>Loading utilization…</div>
      </div>

      <template v-else-if="utilization">

      <!-- Intro / explainer -->
      <div class="acard q-mb-lg" style="background:#FAFCFF;border-color:#E3F2FD">
        <div class="row items-start no-wrap" style="gap:12px">
          <q-icon name="speed" size="28px" color="indigo-6" />
          <div style="flex:1">
            <div class="text-weight-medium" style="font-size:14px;color:#1A237E">
              How operator workloads are scored
            </div>
            <div class="text-caption text-grey-7" style="line-height:1.5;margin-top:4px">
              The ranking is <b>not</b> raw call count. Every operator is judged on
              <b>quantity × duration × AI-graded quality</b>. The composite
              <b>Effective Effort</b> = avg call minutes × (avg quality / 10) × 10 —
              so 100 calls of "hi-how-are-you-bye" lose to 20 deep, well-handled conversations.
            </div>
          </div>
        </div>
      </div>

      <!-- ── Team KPIs ────────────────────────────────────────────────────── -->
      <div class="kpi-grid q-mb-lg">
        <div class="kpi-card">
          <div class="kpi-icon" style="background:#E8EAF6"><q-icon name="support_agent" color="indigo-6" size="20px" /></div>
          <div>
            <div class="kpi-val" style="color:#283593">{{ utilization.team.operators_active }}<span style="font-size:14px;color:#9E9E9E;font-weight:400"> / {{ utilization.team.operators_total }}</span></div>
            <div class="kpi-label">Active operators</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background:#EDE7F6"><q-icon name="phone" color="deep-purple-6" size="20px" /></div>
          <div>
            <div class="kpi-val" style="color:#4527A0">{{ utilization.team.real_calls }}</div>
            <div class="kpi-label">Real calls ({{ utilization.period_label }})</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background:#E0F7FA"><q-icon name="schedule" color="cyan-7" size="20px" /></div>
          <div>
            <div class="kpi-val" style="color:#00838F">{{ utilization.team.talk_min }}<span style="font-size:14px;color:#9E9E9E;font-weight:400"> min</span></div>
            <div class="kpi-label">Total talk-time</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background:#FFF8E1"><q-icon name="timer" color="amber-8" size="20px" /></div>
          <div>
            <div class="kpi-val" :style="`color:${utilDurationColor(utilization.team.avg_call_min)}`">{{ utilFmtNum(utilization.team.avg_call_min) }}<span style="font-size:14px;color:#9E9E9E;font-weight:400"> min</span></div>
            <div class="kpi-label">Avg call duration</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background:#E8F5E9"><q-icon name="star" color="green-7" size="20px" /></div>
          <div>
            <div class="kpi-val" :style="`color:${utilQualityColor(utilization.team.avg_q_overall)}`">{{ utilFmtNum(utilization.team.avg_q_overall) }}<span style="font-size:14px;color:#9E9E9E;font-weight:400"> / 10</span></div>
            <div class="kpi-label">Avg call quality</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background:#FCE4EC"><q-icon name="auto_graph" color="pink-6" size="20px" /></div>
          <div>
            <div class="kpi-val" :style="`color:${utilEffortColor(utilization.team.effective_effort_score)}`">{{ utilFmtNum(utilization.team.effective_effort_score) }}</div>
            <div class="kpi-label">Effective Effort score</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background:#F3E5F5"><q-icon name="hourglass_full" color="purple-6" size="20px" /></div>
          <div>
            <div class="kpi-val" style="color:#6A1B9A">{{ utilFmtNum(utilization.team.quality_minutes, 0) }}</div>
            <div class="kpi-label">Quality-weighted minutes</div>
          </div>
        </div>
        <div class="kpi-card" :class="utilization.team.miss_rate_pct > 30 ? 'kpi-card--alert' : utilization.team.miss_rate_pct > 15 ? 'kpi-card--warn' : ''">
          <div class="kpi-icon" style="background:#FFF3E0"><q-icon name="phone_missed" color="orange-8" size="20px" /></div>
          <div>
            <div class="kpi-val" style="color:#E65100">{{ utilization.team.missed_calls }}<span style="font-size:14px;color:#9E9E9E;font-weight:400"> · {{ utilFmtNum(utilization.team.miss_rate_pct, 0) }}%</span></div>
            <div class="kpi-label">Missed calls</div>
          </div>
        </div>
      </div>

      <!-- ── Empty operators ──────────────────────────────────────────────── -->
      <div v-if="!utilization.operators.length" class="acard text-center text-grey-5 q-py-xl">
        <q-icon name="people_outline" size="40px" class="q-mb-sm" />
        <div>No operators configured</div>
      </div>

      <!-- ── Operator leaderboard table ──────────────────────────────────── -->
      <div v-else class="acard q-mb-lg">
        <div class="acard-header q-mb-md">
          <div class="acard-title">Operator leaderboard — {{ utilization.period_label }}</div>
          <div class="row items-center" style="gap:8px">
            <div class="text-caption text-grey-6">Rank by:</div>
            <q-btn-toggle
              v-model="utilSortBy"
              dense unelevated no-caps
              toggle-color="indigo-6"
              color="grey-2" text-color="grey-9"
              :options="[
                { label: 'Effective Effort', value: 'effective_effort_score' },
                { label: 'Quality',          value: 'avg_q_overall' },
                { label: 'Talk-time',        value: 'talk_min' },
                { label: 'Calls',            value: 'real_calls' },
                { label: 'Partners',         value: 'unique_partners' },
              ]"
            />
          </div>
        </div>

        <div class="util-table-wrap">
          <table class="util-table">
            <thead>
              <tr>
                <th style="width:34px">#</th>
                <th class="text-left">Operator</th>
                <th>Calls</th>
                <th>Missed</th>
                <th>Partners</th>
                <th>Talk min</th>
                <th>Avg call</th>
                <th>Quality</th>
                <th>Effort</th>
                <th>Q·minutes</th>
                <th>Days<br><span class="text-caption text-grey-5">Mon–Fri</span></th>
                <th>Calls<br>/day</th>
                <th>Min<br>/day</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(op, idx) in utilOperatorsSorted" :key="op.id">
                <td class="text-center">
                  <span class="util-rank" :style="`background:${idx===0?'#FFD700':idx===1?'#C0C0C0':idx===2?'#CD7F32':'#EEEEEE'};color:${idx<3?'#fff':'#757575'}`">{{ idx + 1 }}</span>
                </td>
                <td>
                  <div class="row items-center no-wrap" style="gap:8px">
                    <q-avatar size="28px" color="indigo-4" text-color="white" style="font-size:11px">{{ initials(op.name) }}</q-avatar>
                    <div style="min-width:0">
                      <div class="text-weight-medium ellipsis" style="font-size:13px;max-width:180px">{{ op.name }}</div>
                      <div class="text-caption text-grey-6">@{{ op.username }} · {{ fromNow(op.last_activity) || 'never' }}</div>
                    </div>
                  </div>
                </td>
                <td class="text-center">
                  <span style="font-weight:600">{{ op.real_calls }}</span>
                  <span v-if="op.prev != null" class="util-delta" :class="utilDeltaClass(utilDelta(op.real_calls, op.prev.calls))">
                    <q-icon :name="utilDeltaIcon(utilDelta(op.real_calls, op.prev.calls))" size="11px" />
                    {{ utilDelta(op.real_calls, op.prev.calls) != null ? Math.abs(utilDelta(op.real_calls, op.prev.calls)) + '%' : '' }}
                  </span>
                </td>
                <td class="text-center">
                  <span :style="`color:${op.miss_rate_pct > 30 ? '#C62828' : op.miss_rate_pct > 15 ? '#EF6C00' : '#9E9E9E'}`">
                    {{ op.missed_calls }}
                    <span class="text-caption">({{ utilFmtNum(op.miss_rate_pct, 0) }}%)</span>
                  </span>
                </td>
                <td class="text-center">{{ op.unique_partners }}</td>
                <td class="text-center" style="font-weight:600">{{ utilFmtNum(op.talk_min, 0) }}</td>
                <td class="text-center" :style="`font-weight:600;color:${utilDurationColor(op.avg_call_min)}`">
                  {{ utilFmtNum(op.avg_call_min) }}
                  <span v-if="op.prev != null" class="util-delta" :class="utilDeltaClass(utilDelta(op.avg_call_min, op.prev.avg_call_min))">
                    <q-icon :name="utilDeltaIcon(utilDelta(op.avg_call_min, op.prev.avg_call_min))" size="11px" />
                  </span>
                </td>
                <td class="text-center">
                  <span class="util-pill" :style="`background:${utilQualityColor(op.avg_q_overall)}1A;color:${utilQualityColor(op.avg_q_overall)}`">
                    {{ utilFmtNum(op.avg_q_overall) }}
                  </span>
                  <div class="text-caption text-grey-5" style="margin-top:1px">{{ op.quality_calls }} scored</div>
                </td>
                <td class="text-center">
                  <span class="util-pill util-pill--big" :style="`background:${utilEffortColor(op.effective_effort_score)};color:#fff`">
                    {{ utilFmtNum(op.effective_effort_score) }}
                  </span>
                </td>
                <td class="text-center">{{ utilFmtNum(op.quality_minutes, 0) }}</td>
                <td class="text-center">{{ op.days_active }}</td>
                <td class="text-center">{{ utilFmtNum(op.calls_per_active_day) }}</td>
                <td class="text-center">{{ utilFmtNum(op.talk_min_per_active_day, 0) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── Per-operator detailed cards with trend ──────────────────────── -->
      <div v-if="utilization.operators.length" class="util-card-grid">
        <div v-for="op in utilOperatorsSorted" :key="'card-' + op.id" class="util-card">
          <div class="util-card-header">
            <q-avatar size="38px" color="indigo-4" text-color="white" style="font-size:14px">{{ initials(op.name) }}</q-avatar>
            <div style="flex:1;min-width:0">
              <div class="util-card-name">{{ op.name }}</div>
              <div class="util-card-sub">@{{ op.username }}</div>
            </div>
            <div class="util-card-effort" :style="`color:${utilEffortColor(op.effective_effort_score)}`">
              {{ utilFmtNum(op.effective_effort_score) }}
              <span style="font-size:10px;font-weight:400;color:#9E9E9E;display:block;text-align:right">effort</span>
            </div>
          </div>

          <div class="util-card-stats">
            <div class="util-card-stat">
              <div class="util-card-stat-val" style="color:#4527A0">{{ op.real_calls }}</div>
              <div class="util-card-stat-lbl">calls</div>
            </div>
            <div class="util-card-stat">
              <div class="util-card-stat-val" style="color:#00838F">{{ utilFmtNum(op.talk_min, 0) }}<span style="font-size:11px"> m</span></div>
              <div class="util-card-stat-lbl">talk-time</div>
            </div>
            <div class="util-card-stat">
              <div class="util-card-stat-val" :style="`color:${utilDurationColor(op.avg_call_min)}`">{{ utilFmtNum(op.avg_call_min) }}<span style="font-size:11px"> m</span></div>
              <div class="util-card-stat-lbl">avg call</div>
            </div>
            <div class="util-card-stat">
              <div class="util-card-stat-val" :style="`color:${utilQualityColor(op.avg_q_overall)}`">{{ utilFmtNum(op.avg_q_overall) }}</div>
              <div class="util-card-stat-lbl">quality</div>
            </div>
            <div class="util-card-stat">
              <div class="util-card-stat-val" style="color:#5E35B1">{{ op.unique_partners }}</div>
              <div class="util-card-stat-lbl">partners</div>
            </div>
            <div class="util-card-stat">
              <div class="util-card-stat-val" :style="`color:${op.miss_rate_pct > 30 ? '#C62828' : '#757575'}`">{{ op.missed_calls }}<span style="font-size:11px"> · {{ utilFmtNum(op.miss_rate_pct, 0) }}%</span></div>
              <div class="util-card-stat-lbl">missed</div>
            </div>
          </div>

          <!-- Quality breakdown sub-bars -->
          <div v-if="op.quality_calls" class="util-card-quality">
            <div class="util-card-q-row">
              <span class="util-card-q-lbl">Survey</span>
              <div class="util-card-q-track"><div class="util-card-q-bar" :style="`width:${(op.avg_q_survey ?? 0) * 10}%;background:${utilQualityColor(op.avg_q_survey)}`"></div></div>
              <span class="util-card-q-val">{{ utilFmtNum(op.avg_q_survey) }}</span>
            </div>
            <div class="util-card-q-row">
              <span class="util-card-q-lbl">Explain</span>
              <div class="util-card-q-track"><div class="util-card-q-bar" :style="`width:${(op.avg_q_explanation ?? 0) * 10}%;background:${utilQualityColor(op.avg_q_explanation)}`"></div></div>
              <span class="util-card-q-val">{{ utilFmtNum(op.avg_q_explanation) }}</span>
            </div>
            <div class="util-card-q-row">
              <span class="util-card-q-lbl">Overall</span>
              <div class="util-card-q-track"><div class="util-card-q-bar" :style="`width:${(op.avg_q_overall ?? 0) * 10}%;background:${utilQualityColor(op.avg_q_overall)}`"></div></div>
              <span class="util-card-q-val" style="font-weight:700">{{ utilFmtNum(op.avg_q_overall) }}</span>
            </div>
          </div>
          <div v-else class="util-card-quality-empty">
            <q-icon name="info_outline" size="14px" /> No AI-scored calls in this period
          </div>

          <!-- Daily trend (calls bars) -->
          <div class="util-card-trend">
            <div class="util-card-trend-label">Daily activity</div>
            <div class="util-card-trend-bars">
              <div
                v-for="(b, i) in utilTrendBars(op.trend)"
                :key="i"
                class="util-card-trend-bar-wrap"
                :title="`${b.label}: ${b.calls} calls · ${b.minutes} min${b.quality != null ? ' · q=' + b.quality : ''}`"
              >
                <div
                  class="util-card-trend-bar"
                  :style="`height:${b.height}px;background:${b.calls === 0 ? '#EEEEEE' : utilEffortColor((b.minutes / Math.max(b.calls,1)) * ((b.quality ?? 5) / 10) * 10)}`"
                ></div>
              </div>
            </div>
          </div>

          <!-- Active days info -->
          <div class="util-card-footer">
            <span><q-icon name="event" size="13px" /> {{ op.days_active }} active Mon–Fri days</span>
            <span><q-icon name="phone" size="13px" /> {{ utilFmtNum(op.calls_per_active_day) }} calls/day</span>
            <span><q-icon name="schedule" size="13px" /> {{ utilFmtNum(op.talk_min_per_active_day, 0) }} min/day</span>
          </div>
        </div>
      </div>

      </template><!-- /utilization data -->
      </template><!-- /operator_utilization -->

      <!-- ══════════════════ TASK ANALYTICS ══════════════════════════════════ -->
      <template v-if="section === 'tasks'">

      <!-- Task KPIs -->
      <div class="kpi-grid q-mb-lg">
        <div class="kpi-card">
          <div class="kpi-icon" style="background:#FFF3E0"><q-icon name="task_alt" color="deep-orange-6" size="20px" /></div>
          <div><div class="kpi-val">{{ data.task_overview.total }}</div><div class="kpi-label">Total Tasks</div></div>
        </div>
        <div class="kpi-card" :class="data.task_overview.open > 0 ? 'kpi-card--warn' : ''">
          <div class="kpi-icon" style="background:#E3F2FD"><q-icon name="radio_button_unchecked" color="blue-6" size="20px" /></div>
          <div><div class="kpi-val" style="color:#1565C0">{{ data.task_overview.open }}</div><div class="kpi-label">Open</div></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background:#FFF8E1"><q-icon name="pending" color="amber-8" size="20px" /></div>
          <div><div class="kpi-val" style="color:#F57F17">{{ data.task_overview.in_progress }}</div><div class="kpi-label">In Progress</div></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background:#E8F5E9"><q-icon name="check_circle" color="green-7" size="20px" /></div>
          <div><div class="kpi-val" style="color:#2E7D32">{{ data.task_overview.done }}</div><div class="kpi-label">Done</div></div>
        </div>
        <div class="kpi-card" :class="data.task_overview.overdue > 0 ? 'kpi-card--alert' : ''">
          <div class="kpi-icon" style="background:#FFEBEE"><q-icon name="alarm" color="red-6" size="20px" /></div>
          <div><div class="kpi-val" style="color:#C62828">{{ data.task_overview.overdue }}</div><div class="kpi-label">Overdue</div></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background:#E8F5E9"><q-icon name="percent" color="green-7" size="20px" /></div>
          <div><div class="kpi-val" style="color:#2E7D32">{{ data.task_overview.completion_rate }}%</div><div class="kpi-label">Completion Rate</div></div>
        </div>
        <div class="kpi-card" v-if="data.avg_completion_hours !== null">
          <div class="kpi-icon" style="background:#EDE7F6"><q-icon name="timer" color="deep-purple-6" size="20px" /></div>
          <div>
            <div class="kpi-val" style="color:#4527A0">
              {{ data.avg_completion_hours >= 24 ? (data.avg_completion_hours/24).toFixed(1)+'d' : data.avg_completion_hours+'h' }}
            </div>
            <div class="kpi-label">Avg Completion Time</div>
          </div>
        </div>
      </div>

      <!-- Donut charts row -->
      <div class="two-col q-mb-lg" style="grid-template-columns: 1fr 1fr">
        <div class="acard">
          <div class="acard-title q-mb-md">Tasks by Status</div>
          <DonutChart :items="taskStatusPieItems" centerLabel="Tasks" />
        </div>
        <div class="acard">
          <div class="acard-title q-mb-md">Tasks by Priority</div>
          <DonutChart :items="taskPriorityPieItems" centerLabel="Tasks" />
        </div>
      </div>

      <!-- Tasks time series -->
      <div class="acard q-mb-lg">
        <div class="acard-header q-mb-md">
          <div class="acard-title">Tasks Created vs Completed</div>
          <div class="text-caption text-grey-5">{{ periodLabel }}</div>
        </div>
        <BarChart
          :data="taskTimeData"
          label-key="label"
          :series="[
            { key: 'created',   label: 'Created',   color: '#5C6BC0' },
            { key: 'completed', label: 'Completed', color: '#43A047' },
          ]"
        />
      </div>

      <!-- Operator task table -->
      <div class="acard q-mb-lg" v-if="data.task_by_operator && data.task_by_operator.length">
        <div class="acard-header q-mb-md">
          <div class="acard-title">Tasks by Operator</div>
        </div>
        <div class="op-table-wrap">
          <table class="op-table">
            <thead>
              <tr>
                <th class="col-operator">Operator</th>
                <th>Total</th><th>Open</th><th>In Progress</th><th>Done</th><th>Overdue</th><th>Completion %</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="op in data.task_by_operator" :key="op.id" class="op-row">
                <td>
                  <div class="row items-center" style="gap:8px">
                    <q-avatar size="28px" :color="opAvatarColor(op)" text-color="white" style="font-size:11px;flex-shrink:0">{{ initials(op.name) }}</q-avatar>
                    <div style="font-weight:600;font-size:12px;color:#212121">{{ op.name }}</div>
                  </div>
                </td>
                <td class="cell-center"><b>{{ op.total }}</b></td>
                <td class="cell-center"><span v-if="op.open" class="num-chip num--indigo">{{ op.open }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center"><span v-if="op.in_progress" class="num-chip num--amber">{{ op.in_progress }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center"><span v-if="op.done" class="num-chip" style="background:#E8F5E9;color:#2E7D32">{{ op.done }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center"><span v-if="op.overdue" class="num-chip num--orange">{{ op.overdue }}</span><span v-else class="num-dim">—</span></td>
                <td class="cell-center">
                  <div style="display:flex;align-items:center;gap:8px">
                    <div style="flex:1;height:6px;background:#F0F0F0;border-radius:3px;min-width:60px">
                      <div :style="`width:${op.completion_rate}%;height:100%;background:${op.completion_rate>=80?'#43A047':op.completion_rate>=50?'#FFA726':'#EF5350'};border-radius:3px`" />
                    </div>
                    <span :style="`font-size:11px;font-weight:700;color:${op.completion_rate>=80?'#2E7D32':op.completion_rate>=50?'#E65100':'#C62828'}`">{{ op.completion_rate }}%</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div v-else class="acard text-center text-grey-5 q-py-xl q-mb-lg">
        <q-icon name="task_alt" size="40px" class="q-mb-sm" />
        <div>No task data yet</div>
      </div>

      </template><!-- /tasks -->

      <!-- ══════════════════ AI CHAT ══════════════════════════════════════ -->
      <template v-if="section === 'ai_chat'">
      <div class="acard q-mb-lg" style="min-height:500px;display:flex;flex-direction:column">
        <div class="acard-header q-mb-md">
          <div class="row items-center" style="gap:8px">
            <q-icon name="smart_toy" color="deep-purple-5" size="20px" />
            <div class="acard-title">AI Analytics Assistant</div>
          </div>
          <div class="text-caption text-grey-5">Ask questions about your CRM data</div>
        </div>

        <!-- Messages -->
        <div ref="chatBox" class="chat-box" style="flex:1;overflow-y:auto;min-height:300px;max-height:480px;display:flex;flex-direction:column;gap:10px;margin-bottom:12px">
          <div v-if="!chatMessages.length" class="flex flex-center q-py-xl text-grey-4" style="flex-direction:column;gap:8px">
            <q-icon name="chat_bubble_outline" size="40px" />
            <div class="text-caption">Ask me anything about your analytics data</div>
          </div>
          <div v-for="(msg, i) in chatMessages" :key="i"
            :class="msg.role === 'user' ? 'chat-msg chat-msg--user' : 'chat-msg chat-msg--ai'">
            <div class="chat-bubble" :class="msg.role === 'user' ? 'chat-bubble--user' : 'chat-bubble--ai'">
              {{ msg.text }}
            </div>
          </div>
          <div v-if="chatTyping" class="chat-msg chat-msg--ai">
            <div class="chat-bubble chat-bubble--ai" style="padding:8px 14px">
              <q-spinner-dots color="deep-purple-4" size="20px" />
            </div>
          </div>
        </div>

        <!-- Input -->
        <div class="row items-center" style="gap:8px">
          <q-input
            v-model="chatInput"
            outlined dense
            placeholder="Ask a question about the data..."
            style="flex:1"
            bg-color="white"
            @keyup.enter="sendChat"
          />
          <q-btn
            unelevated color="deep-purple-5" icon="send"
            :loading="chatTyping"
            :disable="!chatInput.trim()"
            @click="sendChat"
          />
        </div>
      </div>
      </template><!-- /ai_chat -->

    </template>
  </q-page>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { usePartnersStore } from 'src/stores/partners'
import { api } from 'boot/axios'
import LineChart from 'src/components/LineChart.vue'
import BarChart from 'src/components/BarChart.vue'
import DonutChart from 'src/components/DonutChart.vue'

const store = usePartnersStore()
const period = ref('all')
const section = ref('partners')
const sections = [
  { key: 'partners',             label: 'Partner Analytics',     icon: 'people' },
  { key: 'operators',            label: 'Operator Analytics',     icon: 'support_agent' },
  { key: 'operator_utilization', label: 'Operator Utilization',   icon: 'speed' },
  { key: 'tasks',                label: 'Task Analytics',         icon: 'task_alt' },
  { key: 'ai_chat',              label: 'AI Chat',                icon: 'smart_toy' },
]
const data = ref(null)
const loading = ref(false)

// Custom date range
const todayStr = new Date().toISOString().slice(0, 10)
const customFrom = ref('')
const customTo   = ref(todayStr)

async function load() {
  if (period.value === 'custom') return  // only load via loadCustom
  loading.value = true
  try {
    data.value = await store.fetchAnalytics(period.value)
  } finally {
    loading.value = false
  }
}

async function loadCustom() {
  if (!customFrom.value || !customTo.value) return
  loading.value = true
  try {
    data.value = await store.fetchAnalytics('custom', customFrom.value, customTo.value)
  } finally {
    loading.value = false
  }
}

// Auto-apply when both dates are set and user changes either field
function onCustomDateChange() {
  if (customFrom.value && customTo.value && customFrom.value <= customTo.value) {
    loadCustom()
  }
  if (section.value === 'operator_utilization') {
    loadUtilization()
  }
}

// ── Operator Utilization data ──────────────────────────────────────────────
const utilization = ref(null)
const utilizationLoading = ref(false)
const utilSortBy = ref('effective_effort_score')   // default sort: composite score

async function loadUtilization() {
  utilizationLoading.value = true
  try {
    const params = { period: period.value }
    if (period.value === 'custom') {
      if (!customFrom.value || !customTo.value) { utilizationLoading.value = false; return }
      params.date_from = customFrom.value
      params.date_to   = customTo.value
    }
    const res = await api.get('/analytics/operator-utilization/', { params })
    utilization.value = res.data
  } catch (e) {
    utilization.value = null
  } finally {
    utilizationLoading.value = false
  }
}

watch(period, (val) => {
  if (val !== 'custom') load()
  if (section.value === 'operator_utilization' && val !== 'custom') loadUtilization()
}, { immediate: true })

watch(section, (val) => {
  if (val === 'operator_utilization' && !utilization.value && period.value !== 'custom') {
    loadUtilization()
  }
  if (val === 'operator_utilization' && period.value === 'custom' && customFrom.value && customTo.value) {
    loadUtilization()
  }
})

const utilOperatorsSorted = computed(() => {
  if (!utilization.value) return []
  const list = [...utilization.value.operators]
  const key = utilSortBy.value
  return list.sort((a, b) => {
    const av = a[key] ?? -1
    const bv = b[key] ?? -1
    if (av === bv) return (b.real_calls || 0) - (a.real_calls || 0)
    return bv - av
  })
})

function utilDelta(cur, prev) {
  if (cur == null || prev == null || prev === 0) return null
  return Math.round(((cur - prev) / prev) * 100)
}

function utilDeltaClass(d) {
  if (d == null) return 'text-grey-5'
  if (d > 5)  return 'text-green-7 text-weight-medium'
  if (d < -5) return 'text-red-7   text-weight-medium'
  return 'text-grey-6'
}
function utilDeltaIcon(d) {
  if (d == null) return ''
  if (d > 5)  return 'arrow_upward'
  if (d < -5) return 'arrow_downward'
  return 'remove'
}
function utilFmtNum(v, digits = 1) {
  if (v == null) return '—'
  return Number(v).toFixed(digits)
}
function utilQualityColor(q) {
  if (q == null) return '#BDBDBD'
  if (q >= 8) return '#2E7D32'
  if (q >= 6) return '#558B2F'
  if (q >= 4) return '#F57F17'
  return '#C62828'
}
function utilEffortColor(score) {
  if (score == null) return '#BDBDBD'
  if (score >= 50) return '#2E7D32'
  if (score >= 30) return '#558B2F'
  if (score >= 15) return '#F57F17'
  return '#C62828'
}
function utilDurationColor(min) {
  if (min == null) return '#BDBDBD'
  if (min >= 5) return '#2E7D32'
  if (min >= 3) return '#558B2F'
  if (min >= 1.5) return '#F57F17'
  return '#C62828'
}
function utilTrendBars(trend) {
  if (!trend?.calls?.length) return []
  const max = Math.max(1, ...trend.calls)
  return trend.calls.map((c, i) => ({
    label:   trend.labels?.[i] ?? '',
    height:  Math.max(2, Math.round((c / max) * 28)),
    minutes: trend.minutes?.[i] ?? 0,
    quality: trend.quality?.[i],
    calls:   c,
  }))
}

// ── Period label ────────────────────────────────────────────────────────────
const periodLabel = computed(() => {
  if (period.value === 'custom' && customFrom.value && customTo.value) {
    const fmt = (s) => new Date(s + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    return `${fmt(customFrom.value)} – ${fmt(customTo.value)}`
  }
  return { today: 'Today', week: 'Last 7 Days', month: 'Last 30 Days', all: 'All Time' }[period.value] || ''
})

const customDayCount = computed(() => {
  if (!customFrom.value || !customTo.value) return 0
  const diff = new Date(customTo.value) - new Date(customFrom.value)
  return Math.round(diff / 86400000) + 1
})

// ── Funnel helpers ───────────────────────────────────────────────────────────
const activeFunnel = computed(() =>
  (data.value?.funnel || []).filter(f =>
    ['new', 'trained', 'set_created', 'has_sale'].includes(f.stage)
  )
)
const deadFunnel = computed(() =>
  (data.value?.funnel || []).filter(f =>
    ['no_answer', 'declined', 'no_sales'].includes(f.stage)
  )
)

// Bar width = % of total partners (same denominator as the % label — no mixed bases)
function barWidthPct(count) {
  const t = data.value?.overview.total_partners || 1
  return Math.round((count / t) * 100)
}
function totalPct(count) {
  const t = data.value?.overview.total_partners || 1
  return Math.round((count / t) * 100)
}

function deadQColor(stage) {
  return { no_answer: 'blue-grey', declined: 'red', no_sales: 'deep-orange' }[stage] || 'grey'
}

// ── Donut chart computed items (partner section) ─────────────────────────────
const stagePieItems = computed(() => {
  const f = data.value?.funnel || []
  const colors = { new: '#EF5350', trained: '#FFB300', set_created: '#29B6F6', has_sale: '#43A047', no_answer: '#78909C', declined: '#B71C1C', no_sales: '#E65100' }
  return f.map(s => ({ label: s.label, value: s.count, color: colors[s.stage] || '#9E9E9E' }))
})
const categoryPieItems = computed(() => {
  const colors = { doctor: '#7E57C2', fitness_trainer: '#43A047', blogger: '#F9A825', other: '#FF7043' }
  return (data.value?.by_category || []).filter(c => c.count > 0).map(c => ({ label: c.label, value: c.count, color: colors[c.key] || '#9E9E9E' }))
})
const typePieItems = computed(() => {
  const colors = { partner: '#42A5F5', medic: '#EC407A' }
  return (data.value?.by_type || []).filter(t => t.count > 0).map(t => ({ label: t.label, value: t.count, color: colors[t.key] || '#9E9E9E' }))
})

// ── Task chart computed items ────────────────────────────────────────────────
const taskStatusPieItems = computed(() => {
  const t = data.value?.task_overview
  if (!t) return []
  return [
    { label: 'Open',        value: t.open,        color: '#42A5F5' },
    { label: 'In Progress', value: t.in_progress,  color: '#FFA726' },
    { label: 'Done',        value: t.done,         color: '#66BB6A' },
    { label: 'Cancelled',   value: t.cancelled,    color: '#BDBDBD' },
  ].filter(i => i.value > 0)
})
const taskPriorityPieItems = computed(() => {
  return (data.value?.task_by_priority || []).filter(p => p.count > 0).map(p => ({
    label: p.label,
    value: p.count,
    color: { high: '#EF5350', medium: '#FFA726', low: '#78909C' }[p.key] || '#9E9E9E',
  }))
})
const taskTimeData = computed(() => {
  const ts = data.value?.time_series
  if (!ts) return []
  return ts.labels.map((label, i) => ({
    label,
    created:   ts.tasks_created?.[i] || 0,
    completed: ts.tasks_completed?.[i] || 0,
  }))
})

// ── Category / type / gender / state / referral ──────────────────────────────
const catMax    = computed(() => Math.max(...(data.value?.by_category || []).map(c => c.count), 1))
const typeMax   = computed(() => Math.max(...(data.value?.by_type || []).map(t => t.count), 1))
const genderMax = computed(() => Math.max(...(data.value?.by_gender || []).map(g => g.count), 1))
const stateMax  = computed(() => Math.max(...(data.value?.by_state || []).map(s => s.count), 1))
const refMax    = computed(() => Math.max(...(data.value?.by_referral || []).map(r => r.count), 1))

// ── Chart data ───────────────────────────────────────────────────────────────
const growthData = computed(() => {
  const ts = data.value?.time_series
  if (!ts) return []
  return ts.labels.map((label, i) => ({ label, new: ts.partners_new[i] }))
})

const salesDepthData = computed(() => {
  const sd = data.value?.sales_depth_ts
  if (!sd) return []
  return sd.labels.map((label, i) => ({
    label,
    '1plus':  sd['1plus'][i],
    '3plus':  sd['3plus'][i],
    '5plus':  sd['5plus'][i],
    '10plus': sd['10plus'][i],
  }))
})

const callData = computed(() => {
  const ts = data.value?.time_series
  if (!ts) return []
  return ts.labels.map((label, i) => ({
    label,
    calls:     ts.calls[i],
    missed:    ts.missed[i],
    callbacks: ts.callbacks[i],
  }))
})

// ── Money formatter ──────────────────────────────────────────────────────────
function fmtMoney(val) {
  const n = Number(val) || 0
  if (n === 0) return '₹0'
  if (n >= 1_000_000) return '₹' + (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  if (n >= 1_000) return '₹' + (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K'
  return '₹' + n.toFixed(0)
}

// ── Conversion leaderboard (operators sorted by conv_sale desc) ───────────────
const convLeaderboard = computed(() => {
  return [...(data.value?.operators || [])].sort((a, b) => b.conv_sale - a.conv_sale)
})

// ── Operator table ───────────────────────────────────────────────────────────
function initials(name) {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

// Color-code avatar by activity level
function opAvatarColor(op) {
  const total = op.calls + op.missed
  if (total === 0) return 'grey-5'
  if (total >= 10) return 'green-7'
  if (total >= 5) return 'blue-6'
  return 'orange-7'
}

function fromNow(iso) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const teamTotals = computed(() => {
  const ops = data.value?.operators || []
  return {
    calls:           ops.reduce((s, o) => s + o.calls, 0),
    missed:          ops.reduce((s, o) => s + o.missed, 0),
    callbacks:       ops.reduce((s, o) => s + o.callbacks, 0),
    audio:           ops.reduce((s, o) => s + (o.audio || 0), 0),
    assigned:        ops.reduce((s, o) => s + o.assigned, 0),
    active:          ops.reduce((s, o) => s + o.active, 0),
    dead:            ops.reduce((s, o) => s + o.dead, 0),
    overdue:         ops.reduce((s, o) => s + o.overdue, 0),
    sale_count:      ops.reduce((s, o) => s + (o.sale_count || 0), 0),
    partners_1sale:  ops.reduce((s, o) => s + (o.partners_1sale || 0), 0),
    partners_10sale: ops.reduce((s, o) => s + (o.partners_10sale || 0), 0),
    inactive:        ops.reduce((s, o) => s + (o.inactive || 0), 0),
    never_contacted: ops.reduce((s, o) => s + (o.never_contacted || 0), 0),
    revenue:         ops.reduce((s, o) => s + (o.revenue || 0), 0),
  }
})

const teamMissRate = computed(() => {
  const t = teamTotals.value
  const total = t.calls + t.missed
  return total > 0 ? Math.round(t.missed / total * 100) : 0
})

const teamSaleConv = computed(() => {
  const t = teamTotals.value
  return t.assigned > 0 ? Math.round(t.sale_count / t.assigned * 100) : 0
})

const teamDeadRate = computed(() => {
  const t = teamTotals.value
  const total = t.active + t.dead
  return total > 0 ? Math.round(t.dead / total * 100) : 0
})

const teamCallsPerSale = computed(() => {
  const t = teamTotals.value
  if (!t.sale_count) return null
  return Math.round((t.calls + t.missed) / t.sale_count)
})

const teamContactRate = computed(() => {
  const t = teamTotals.value
  const total = t.active + (t.never_contacted || 0)
  if (!total) return 0
  const contacted = total - (t.never_contacted || 0)
  return Math.round(contacted / total * 100)
})

// ── Stage label helper (for WhatsApp by_stage) ───────────────────────────────
const stageLabelMap = {
  new: 'New', trained: 'Agreed to Create First Set', set_created: 'Set Created', has_sale: 'Has Sale',
}
function stageLabel(key) {
  return stageLabelMap[key] || key
}

function stageBadgeColor(stage) {
  const m = { new: '#EF5350', trained: '#FFB300', set_created: '#29B6F6', has_sale: '#43A047', no_answer: '#78909C', declined: '#B71C1C', no_sales: '#E65100' }
  return m[stage] || '#9E9E9E'
}

// ── Call quality ─────────────────────────────────────────────────────────────
const scoredOperators = computed(() =>
  (data.value?.operators || []).filter(op => op.scored_calls > 0)
)

function qualityStyle(score) {
  if (score === null || score === undefined) return 'background:#F5F5F5;color:#9E9E9E'
  if (score >= 8) return 'background:#E8F5E9;color:#1B5E20'
  if (score >= 6) return 'background:#FFF8E1;color:#E65100'
  return 'background:#FFEBEE;color:#C62828'
}

// ── AI Chat ──────────────────────────────────────────────────────────────────
const chatMessages = ref([])
const chatInput    = ref('')
const chatTyping   = ref(false)
const chatBox      = ref(null)

function buildChatContext() {
  if (!data.value) return {}
  const d = data.value
  const top3ops = [...(d.operators || [])].sort((a, b) => b.conv_sale - a.conv_sale).slice(0, 3)
    .map(o => ({ name: o.name, conv_sale: o.conv_sale, revenue: o.revenue, calls: o.calls }))
  const top3cats = [...(d.by_category || [])].sort((a, b) => b.count - a.count).slice(0, 3)
    .map(c => ({ label: c.label, count: c.count, conv_sale: c.conv_sale }))
  return {
    total_partners:  d.overview.total_partners,
    active_partners: d.overview.active_partners,
    dead_partners:   d.overview.dead_partners,
    dead_rate:       d.overview.dead_rate,
    never_contacted: d.overview.never_contacted,
    stagnant:        d.overview.stagnant_partners,
    total_revenue:   d.financials.total_revenue,
    total_unpaid:    d.financials.total_unpaid,
    total_orders:    d.financials.total_orders,
    conversion_to_sale: d.conversion.to_sale,
    top_operators:   top3ops,
    top_categories:  top3cats,
    whatsapp_pct:    d.whatsapp_stats?.pct,
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
      section:  'partners',
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
.analytics-root { max-width: 1200px; }

/* ── Custom date range bar ────────────────────────────────────────── */
.custom-range-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #F8F9FF;
  border: 1px solid #C5CAE9;
  border-radius: 10px;
  padding: 10px 16px;
  width: fit-content;
}

/* Slide transition */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
  margin-bottom: 0;
}
.slide-down-enter-to,
.slide-down-leave-from {
  opacity: 1;
  max-height: 80px;
}

/* ── Two-column grid (12-unit system) ─────────────────────────────── */
.two-col {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 16px;
}

/* ── KPI grid ─────────────────────────────────────────────────────── */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(155px, 1fr));
  gap: 12px;
}
.kpi-card {
  background: #fff;
  border: 1px solid #E8E8E8;
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: box-shadow 0.2s;
}
.kpi-card:hover      { box-shadow: 0 2px 12px rgba(0,0,0,0.07); }
.kpi-card--warn      { border-color: #FFB300; }
.kpi-card--alert     { border-color: #EF9A9A; background: #FFF8F8; }
.kpi-icon {
  width: 40px; height: 40px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.kpi-val   { font-size: 24px; font-weight: 700; line-height: 1.1; color: #212121; }
.kpi-label { font-size: 11px; color: #9E9E9E; margin-top: 2px; line-height: 1.4; }
.due-badge {
  display: inline-block;
  background: #FFF9C4;
  color: #F9A825;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 6px;
  margin-left: 4px;
}

/* ── Analytics card ───────────────────────────────────────────────── */
.acard {
  background: #fff;
  border: 1px solid #E8E8E8;
  border-radius: 12px;
  padding: 20px;
}
.acard-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 16px;
}
.acard-title {
  font-size: 14px;
  font-weight: 600;
  color: #212121;
  flex-shrink: 0;
}

/* ── Funnel ───────────────────────────────────────────────────────── */
.funnel-section-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: #BDBDBD;
  font-weight: 700;
}
.funnel-row {
  display: grid;
  grid-template-columns: 128px 1fr 36px 38px;
  align-items: center;
  gap: 8px;
}
.funnel-label  { font-size: 12px; color: #424242; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.funnel-track  { height: 7px; background: #F5F5F5; border-radius: 4px; overflow: hidden; }
.funnel-bar    { height: 100%; border-radius: 4px; transition: width 0.5s ease; min-width: 1px; }
.funnel-count  { font-size: 13px; font-weight: 700; color: #212121; text-align: right; }
.funnel-pct    { font-size: 11px; color: #9E9E9E; text-align: right; }

/* ── Conversion ───────────────────────────────────────────────────── */
.conv-item { display: grid; grid-template-columns: 1fr 90px 40px; align-items: center; gap: 8px; }
.conv-label { font-size: 12px; color: #616161; }
.conv-track { height: 6px; background: #F5F5F5; border-radius: 3px; overflow: hidden; }
.conv-fill  { height: 100%; border-radius: 3px; transition: width 0.5s ease; }
.conv-pct   { font-size: 13px; font-weight: 700; text-align: right; }

/* ── Operator table ───────────────────────────────────────────────── */
.op-table-wrap { overflow-x: auto; }
.op-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.op-table thead tr { border-bottom: 2px solid #F0F0F0; }
.op-table thead th {
  padding: 6px 10px;
  color: #9E9E9E;
  font-weight: 700;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  text-align: center;
  white-space: nowrap;
}
.op-table thead .col-operator { text-align: left; }
.op-row { border-bottom: 1px solid #F7F7F7; transition: background 0.12s; }
.op-row:hover { background: #FAFAFA; }
.op-row td { padding: 10px 10px; vertical-align: middle; }
.cell-center { text-align: center; }
.col-sep { border-left: 1px solid #F0F0F0; }

/* Number chips */
.num-chip {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 28px; padding: 2px 7px;
  border-radius: 10px; font-size: 12px; font-weight: 700;
}
.num--indigo { background: #E8EAF6; color: #3949AB; }
.num--orange { background: #FBE9E7; color: #D84315; }
.num--purple { background: #F3E5F5; color: #7B1FA2; }
.num--teal   { background: #E0F2F1; color: #00695C; }
.num--amber  { background: #FFF8E1; color: #E65100; }
.num-dim     { font-size: 12px; color: #BDBDBD; }
.num-dim-red { font-size: 12px; font-weight: 600; color: #EF9A9A; }
.miss-bad    { font-size: 12px; font-weight: 700; color: #C62828; }
.miss-ok     { font-size: 12px; color: #757575; }

/* Totals footer */
.totals-row td { padding-top: 10px; border-top: 2px solid #F0F0F0; }

/* Legend dots in table header */
.legend-dot {
  font-size: 10px; font-weight: 600;
  padding: 2px 8px; border-radius: 8px;
}

/* ── Financial section header ─────────────────────────────────────── */
.fin-section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #388E3C;
  text-transform: uppercase;
  letter-spacing: 0.6px;
}

/* ── Financial KPI cards (slightly smaller) ───────────────────────── */
.kpi-card--fin {
  padding: 11px 14px;
}
.kpi-card--fin .kpi-val {
  font-size: 20px;
}

/* ── Conversion leaderboard ───────────────────────────────────────── */
.conv-leader-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.conv-leader-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.conv-stack-track {
  flex: 1;
  height: 8px;
  background: #F5F5F5;
  border-radius: 4px;
  position: relative;
  overflow: visible;
}
.conv-stack-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
  min-width: 1px;
}
.conv-stack--trained { background: #FFB300; opacity: 0.45; }
.conv-stack--set     { background: #29B6F6; opacity: 0.55; }
.conv-stack--sale    { background: #43A047; opacity: 0.85; }
.conv-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 8px;
  white-space: nowrap;
}
.conv-badge--trained { background: #FFF8E1; color: #F57F17; }
.conv-badge--set     { background: #E3F2FD; color: #0277BD; }
.conv-badge--sale    { background: #E8F5E9; color: #1B5E20; }
.conv-good { font-size: 12px; font-weight: 700; color: #2E7D32; }
.conv-mid  { font-size: 12px; color: #757575; }

/* ── Sales depth chips ────────────────────────────────────────────── */
.sale-chip {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 8px;
  white-space: nowrap;
}
.sale-chip--1  { background: #E8F5E9; color: #2E7D32; }
.sale-chip--10 { background: #F3E5F5; color: #6A1B9A; }

/* ── Section switcher ─────────────────────────────────────────────── */
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
.section-btn:hover {
  border-color: #9FA8DA;
  color: #3949AB;
  background: #F3F4FF;
}
.section-btn--active {
  border-color: #3F51B5;
  background: #3F51B5;
  color: #fff;
}
.section-btn--active:hover {
  background: #3949AB;
  border-color: #3949AB;
  color: #fff;
}

/* ── Pipeline Velocity ────────────────────────────────────────────── */
.velocity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.velocity-card {
  background: #FAFAFA;
  border: 1px solid #EEEEEE;
  border-radius: 10px;
  padding: 14px 16px;
}
.velocity-stage-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: #9E9E9E;
  font-weight: 700;
  margin-bottom: 6px;
}
.velocity-count {
  font-size: 20px;
  font-weight: 700;
  color: #212121;
  line-height: 1.1;
}
.velocity-age {
  font-size: 14px;
  font-weight: 600;
  margin-top: 4px;
}
.velocity-stuck {
  font-size: 11px;
  font-weight: 600;
  margin-top: 4px;
  margin-bottom: 8px;
}
.velocity-stuck--bad { color: #C62828; }
.velocity-stuck--ok  { color: #2E7D32; }
.velocity-bar-wrap {
  height: 4px;
  background: #E0E0E0;
  border-radius: 2px;
  overflow: hidden;
  margin-top: 6px;
}
.velocity-bar {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
  min-width: 1px;
}

/* ── Segmentation rows (category, type, gender, state, referral) ─── */
.seg-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.seg-label {
  font-size: 12px;
  color: #424242;
  width: 90px;
  flex-shrink: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.seg-bars {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.seg-bar-wrap {
  height: 6px;
  background: #F5F5F5;
  border-radius: 3px;
  overflow: hidden;
}
.seg-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
  min-width: 1px;
}
.seg-bar--total { background: #90CAF9; }
.seg-chip {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 8px;
  white-space: nowrap;
}
.seg-chip--count { background: #E3F2FD; color: #1565C0; }
.seg-chip--sale  { background: #E8F5E9; color: #2E7D32; }
.seg-chip--dead  { background: #FFEBEE; color: #C62828; }

/* ── Operator Scorecards ──────────────────────────────────────────── */
.op-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}
.op-scorecard {
  background: #fff;
  border: 1px solid #E8E8E8;
  border-radius: 14px;
  padding: 16px;
  transition: box-shadow 0.2s;
}
.op-scorecard:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
.op-sc-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.op-sc-rank {
  width: 28px; height: 28px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 800;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.op-sc-name {
  font-size: 13px;
  font-weight: 700;
  color: #212121;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.op-sc-sub {
  font-size: 10px;
  color: #BDBDBD;
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.op-sc-big-conv {
  font-size: 22px;
  font-weight: 800;
  flex-shrink: 0;
  text-align: right;
  line-height: 1.1;
}
.op-sc-funnel {
  background: #FAFAFA;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.op-sc-funnel-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.op-sc-fl {
  font-size: 10px;
  color: #9E9E9E;
  width: 68px;
  flex-shrink: 0;
}
.op-sc-ftrack {
  flex: 1;
  height: 5px;
  background: #EEEEEE;
  border-radius: 3px;
  overflow: hidden;
}
.op-sc-fbar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
  min-width: 1px;
}
.op-sc-fpct {
  font-size: 11px;
  font-weight: 700;
  color: #757575;
  width: 34px;
  text-align: right;
}
.op-sc-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}
.op-sc-metric {
  background: #FAFAFA;
  border: 1px solid #F0F0F0;
  border-radius: 8px;
  padding: 7px 8px;
  text-align: center;
}
.op-sc-metric--bad  { background: #FFF5F5; border-color: #FFCDD2; }
.op-sc-metric--warn { background: #FFFDE7; border-color: #FFF176; }
.op-sc-metric--good { background: #F1F8E9; border-color: #DCEDC8; }
.op-sc-mval {
  font-size: 15px;
  font-weight: 800;
  line-height: 1.2;
}
.op-sc-mlbl {
  font-size: 9px;
  color: #9E9E9E;
  margin-top: 2px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.op-sc-portfolio {
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  background: #F5F5F5;
  display: flex;
  margin-bottom: 4px;
}
.op-sc-portfolio-label {
  display: flex;
  gap: 10px;
  font-size: 10px;
  color: #9E9E9E;
}

/* ── Rank badges (top partners) ───────────────────────────────────── */
.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 800;
}
.stage-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
  background: #9E9E9E;
  color: #fff;
}

/* ── Quality badge ────────────────────────────────────────────────── */
.quality-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  padding: 3px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 700;
}

/* ── AI Chat ──────────────────────────────────────────────────────── */
.chat-box { padding: 4px; }
.chat-msg { display: flex; }
.chat-msg--user { justify-content: flex-end; }
.chat-msg--ai   { justify-content: flex-start; }
.chat-bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
}
.chat-bubble--user {
  background: #3F51B5;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.chat-bubble--ai {
  background: #F5F5F5;
  color: #212121;
  border-bottom-left-radius: 4px;
}

/* ───────────────── Operator Utilization ───────────────── */
.util-table-wrap {
  overflow-x: auto;
  margin: 0 -8px;
  padding: 0 8px;
}
.util-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
  min-width: 940px;
}
.util-table thead th {
  background: #FAFAFA;
  color: #616161;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  padding: 10px 8px;
  border-bottom: 2px solid #EEEEEE;
  text-align: center;
  white-space: nowrap;
}
.util-table thead th.text-left { text-align: left; padding-left: 12px; }
.util-table tbody td {
  padding: 10px 8px;
  border-bottom: 1px solid #F5F5F5;
  vertical-align: middle;
}
.util-table tbody tr:hover { background: #FAFCFF; }
.util-rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px; height: 22px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
}
.util-pill {
  display: inline-block;
  padding: 3px 9px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}
.util-pill--big {
  font-size: 13px;
  padding: 4px 11px;
  border-radius: 12px;
}
.util-delta {
  display: inline-flex;
  align-items: center;
  gap: 1px;
  font-size: 10px;
  margin-left: 4px;
}

.util-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}
.util-card {
  background: #FFFFFF;
  border: 1px solid #EEEEEE;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  transition: box-shadow 0.15s;
}
.util-card:hover { box-shadow: 0 4px 18px rgba(0,0,0,0.07); }
.util-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.util-card-name {
  font-size: 14px;
  font-weight: 600;
  color: #212121;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.util-card-sub {
  font-size: 11px;
  color: #9E9E9E;
}
.util-card-effort {
  font-size: 24px;
  font-weight: 700;
  text-align: right;
  line-height: 1;
}
.util-card-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.util-card-stat {
  background: #FAFAFA;
  border-radius: 8px;
  padding: 8px 6px;
  text-align: center;
}
.util-card-stat-val {
  font-size: 16px;
  font-weight: 700;
  line-height: 1.1;
}
.util-card-stat-lbl {
  font-size: 10px;
  color: #757575;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-top: 3px;
}
.util-card-quality { display: flex; flex-direction: column; gap: 5px; }
.util-card-q-row { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.util-card-q-lbl { color: #757575; width: 50px; flex-shrink: 0; }
.util-card-q-track { flex: 1; height: 5px; background: #EEEEEE; border-radius: 3px; overflow: hidden; }
.util-card-q-bar  { height: 100%; border-radius: 3px; transition: width .3s; }
.util-card-q-val  { width: 28px; text-align: right; color: #424242; font-size: 11px; }
.util-card-quality-empty {
  text-align: center;
  font-size: 11px;
  color: #9E9E9E;
  padding: 4px 0;
}
.util-card-trend { display: flex; flex-direction: column; gap: 6px; }
.util-card-trend-label {
  font-size: 11px;
  color: #757575;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.util-card-trend-bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 30px;
  background: #FAFAFA;
  border-radius: 6px;
  padding: 2px 4px;
}
.util-card-trend-bar-wrap {
  flex: 1;
  display: flex;
  align-items: flex-end;
  height: 100%;
  cursor: help;
}
.util-card-trend-bar {
  width: 100%;
  border-radius: 2px 2px 0 0;
  min-height: 2px;
  transition: opacity .15s;
}
.util-card-trend-bar:hover { opacity: 0.8; }
.util-card-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px dashed #EEEEEE;
  font-size: 11px;
  color: #616161;
}
.util-card-footer span { display: inline-flex; align-items: center; gap: 4px; }
</style>
