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

  <div
    v-else-if="hasData"
    class="market-state-frame"
    :class="{ 'market-state-frame--refreshing': loading }"
    :aria-busy="loading ? 'true' : undefined"
  >
    <slot />
    <div v-if="loading" class="market-state-frame__overlay" aria-hidden="true">
      <span class="market-state-frame__chip">
        <i class="pi pi-spin pi-spinner"></i>
        {{ loadingLabel || t('common.loading') }}
      </span>
    </div>
  </div>

  <EmptyState v-else :message="emptyMessage || t('common.noData')" />
</template>

<style scoped>
  .market-state-frame {
    position: relative;
  }

  .market-state-frame--refreshing {
    min-height: 8rem;
  }

  .market-state-frame__overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: flex-start;
    justify-content: flex-end;
    padding: 0.35rem 0 0;
    pointer-events: none;
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--surface-panel) 42%, transparent),
      transparent 32%
    );
  }

  .market-state-frame__chip {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.35rem 0.6rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--border) 70%, var(--primary) 30%);
    background: color-mix(in srgb, var(--surface-card-strong) 92%, var(--primary-overlay) 8%);
    color: var(--text-muted);
    font-size: 0.78rem;
    font-weight: 700;
    box-shadow: 0 8px 18px color-mix(in srgb, var(--shadow-color) 8%, transparent);
  }
</style>
