<script setup lang="ts">
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import ComparableCard from '../ComparableCard.vue'
  import EmptyState from '../EmptyState.vue'
  import type { TransactionRecord } from '../../types/api'

  defineProps<{
    items: TransactionRecord[]
    countLabel: string
  }>()

  const emit = defineEmits<{ reuse: [item: TransactionRecord] }>()
  const { t } = useI18n()
</script>

<template>
  <section class="prediction-comparables">
    <div class="prediction-comparables-head">
      <div>
        <p class="eyebrow subtle">{{ t('predict.comparablesTitle') }}</p>
        <h3>{{ t('predict.comparablesTitle') }}</h3>
      </div>
      <small class="comparables-count">{{ countLabel }}</small>
    </div>

    <div v-if="items.length" class="comparables-list">
      <ComparableCard
        v-for="item in items"
        :key="`${item.slug}-${item.price_eur}-${item.size_m2}`"
        :item="item"
      >
        <Button size="small" :label="t('predict.reuseComparable')" @click="emit('reuse', item)" />
      </ComparableCard>
    </div>
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

  @media (max-width: 720px) {
    .prediction-comparables-head {
      flex-direction: column;
    }

    .comparables-count {
      width: fit-content;
    }
  }
</style>
