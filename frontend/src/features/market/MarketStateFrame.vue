<script setup lang="ts">
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../../components/EmptyState.vue'
  import LoadingSpinner from '../../components/LoadingSpinner.vue'

  defineProps<{
    loading?: boolean
    loadingLabel?: string
    error?: string
    hasData: boolean
    emptyMessage?: string
  }>()

  const { t } = useI18n()
</script>

<template>
  <LoadingSpinner v-if="loading && !hasData" :label="loadingLabel || t('common.loading')" />

  <div v-else-if="error && !hasData" class="state-card state-card-stack" role="alert">
    <EmptyState :message="error" icon="pi pi-exclamation-triangle" />
    <div v-if="$slots.actions" class="state-card-actions">
      <slot name="actions" />
    </div>
  </div>

  <slot v-else-if="hasData" />

  <EmptyState v-else :message="emptyMessage || t('common.noData')" />
</template>
