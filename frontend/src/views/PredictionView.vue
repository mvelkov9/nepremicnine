<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.prediction') }}</h1>
    <div class="card">
      <p class="muted">Prediction — Phase 3</p>
    </div>
  </div>
</template>
