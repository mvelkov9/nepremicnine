<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.model') }}</h1>
    <div class="card">
      <p class="muted">Model training — Phase 3</p>
    </div>
  </div>
</template>
