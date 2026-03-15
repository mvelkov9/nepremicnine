<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('dashboard.title') }}</h1>

    <div class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-label">{{ t('dashboard.totalRecords') }}</span>
        <span class="kpi-value">—</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">{{ t('dashboard.medianPrice') }}</span>
        <span class="kpi-value">—</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">{{ t('dashboard.pricePerM2') }}</span>
        <span class="kpi-value">—</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">{{ t('dashboard.modelR2') }}</span>
        <span class="kpi-value">—</span>
      </div>
    </div>

    <div class="charts-grid">
      <div class="card">
        <div class="card-title">Cene po regijah</div>
        <p class="muted">Chart placeholder — Phase 2</p>
      </div>
      <div class="card">
        <div class="card-title">Porazdelitev cen</div>
        <p class="muted">Chart placeholder — Phase 2</p>
      </div>
    </div>
  </div>
</template>
