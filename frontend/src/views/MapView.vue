<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.map') }}</h1>
    <div class="card">
      <p class="muted">Map — Phase 4</p>
    </div>
  </div>
</template>
