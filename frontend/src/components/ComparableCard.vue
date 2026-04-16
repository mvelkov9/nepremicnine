<script setup lang="ts">
  import { useI18n } from 'vue-i18n'
  import { useFormat } from '../composables/useFormat'

  defineProps<{
    item: {
      municipality?: string
      year?: number | string | null
      property_type?: string
      size_m2?: number | null
      price_per_m2?: number | null
      price_eur?: number | null
      similarity_score?: number | string | null
      slug?: string
    }
  }>()

  const { t } = useI18n()
  const { fmt, fmtCurrency, formatType } = useFormat()
</script>

<template>
  <article class="comparable-card">
    <div class="comparable-row">
      <strong>{{ item.municipality }}</strong>
      <span>{{ item.year || '-' }}</span>
    </div>
    <p>
      {{ formatType(item.property_type ?? '') || '-' }} - {{ fmt(item.size_m2, 1) }} m² -
      {{ fmtCurrency(item.price_per_m2) }}/m²
    </p>
    <div class="comparable-row">
      <strong class="comparable-price">{{ fmtCurrency(item.price_eur) }}</strong>
      <small>{{ t('predict.similarityLabel') }} {{ item.similarity_score }}</small>
    </div>
    <slot />
  </article>
</template>

<style scoped>
  .comparable-card {
    display: grid;
    gap: 0.55rem;
    padding: 1.02rem 1.08rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 94%, var(--primary) 6%),
        var(--surface-subtle)
      );
    box-shadow: var(--shadow-sm);
  }

  .comparable-card p,
  .comparable-card small {
    margin: 0;
    color: var(--text-muted);
  }

  .comparable-card p {
    font-size: 0.92rem;
  }

  .comparable-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .comparable-price {
    display: block;
    font-size: 1.05rem;
    letter-spacing: -0.02em;
  }
</style>
