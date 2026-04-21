<script setup lang="ts">
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Skeleton from 'primevue/skeleton'
  import ComparableCard from '../ComparableCard.vue'
  import EmptyState from '../EmptyState.vue'
  import type { TransactionRecord } from '../../types/api'

  defineProps<{
    items: TransactionRecord[]
    countLabel: string
    loading?: boolean
    error?: string
  }>()

  const emit = defineEmits<{ reuse: [item: TransactionRecord]; refresh: [] }>()
  const { t } = useI18n()
</script>

<template>
  <section class="prediction-comparables">
    <div class="prediction-comparables-head">
      <div>
        <p class="eyebrow subtle">{{ t('predict.comparablesTitle') }}</p>
        <h3>{{ t('predict.comparablesTitle') }}</h3>
      </div>
      <div class="comparables-head-actions">
        <small class="comparables-count">{{ countLabel }}</small>
        <Button
          v-if="error && !loading"
          size="small"
          severity="secondary"
          text
          icon="pi pi-refresh"
          :label="t('common.retry')"
          @click="emit('refresh')"
        />
      </div>
    </div>

    <div v-if="loading" class="comparables-list" aria-hidden="true">
      <article v-for="idx in 3" :key="idx" class="comparables-skeleton-item">
        <Skeleton width="36%" height="0.88rem" />
        <Skeleton width="64%" height="1rem" />
        <div class="comparables-skeleton-metrics">
          <Skeleton width="32%" height="0.9rem" />
          <Skeleton width="32%" height="0.9rem" />
          <Skeleton width="32%" height="0.9rem" />
        </div>
      </article>
    </div>
    <div v-else-if="items.length" class="comparables-list">
      <ComparableCard
        v-for="item in items"
        :key="`${item.slug}-${item.price_eur}-${item.size_m2}`"
        :item="item"
      >
        <Button size="small" :label="t('predict.reuseComparable')" @click="emit('reuse', item)" />
      </ComparableCard>
    </div>
    <EmptyState v-else-if="error" icon="pi pi-exclamation-triangle" :message="error" />
    <EmptyState v-else icon="pi pi-chart-bar" :message="t('predict.noComparables')" />
  </section>
</template>

<style scoped>
  .prediction-comparables {
    display: grid;
    gap: 0.9rem;
  }

  .prediction-comparables-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .comparables-head-actions {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .prediction-comparables-head h3 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1rem;
    letter-spacing: -0.03em;
  }

  .comparables-count {
    padding: 0.45rem 0.7rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 92%,
      var(--primary) 8%
    );
    color: var(--text-muted);
    font-weight: 700;
    white-space: nowrap;
  }

  .comparables-list {
    display: grid;
    gap: 0.8rem;
  }

  .comparables-skeleton-item {
    display: grid;
    gap: 0.7rem;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--primary) 22%);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 94%,
      var(--primary) 6%
    );
  }

  .comparables-skeleton-metrics {
    display: flex;
    gap: 0.65rem;
  }

  @media (max-width: 720px) {
    .prediction-comparables-head {
      flex-direction: column;
    }

    .comparables-head-actions,
    .comparables-count {
      width: fit-content;
    }
  }
</style>
