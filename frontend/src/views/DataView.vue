<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.data') }}</h1>
    <div class="card">
      <p class="muted">Data management — Phase 2</p>
    </div>
  </div>
</template>
