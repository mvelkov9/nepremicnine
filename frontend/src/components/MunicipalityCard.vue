<script setup lang="ts">
  import { useI18n } from 'vue-i18n'
  import Tag from 'primevue/tag'
  import { formatCurrency, formatNumber } from '../utils/format'

  defineProps<{
    municipality: string
    slug: string
    region?: string
    count?: number
    medianPricePerM2?: number
  }>()

  const { t } = useI18n()
</script>

<template>
  <RouterLink :to="`/obcine/${slug}`" class="municipality-card">
    <div class="card-top">
      <strong class="card-name">{{ municipality }}</strong>
      <Tag v-if="region" severity="secondary" :value="region" />
    </div>
    <div class="card-stats">
      <div v-if="count != null">
        <span>{{ t('dashboard.transactions') }}</span>
        <strong>{{ formatNumber(count) }}</strong>
      </div>
      <div v-if="medianPricePerM2 != null">
        <span>{{ t('dashboard.pricePerM2') }}</span>
        <strong>{{ formatCurrency(medianPricePerM2) }}</strong>
      </div>
    </div>
  </RouterLink>
</template>

<style scoped>
  .municipality-card {
    display: grid;
    gap: 0.7rem;
    padding: 1rem 1.1rem;
    border: 1px solid var(--border);
    border-radius: 1.25rem;
    background: color-mix(in srgb, var(--surface-strong) 90%, var(--overlay-soft) 10%);
    text-decoration: none;
    color: inherit;
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease;
  }

  .municipality-card:hover,
  .municipality-card:focus-visible {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 30%, transparent);
    box-shadow: 0 16px 28px color-mix(in srgb, var(--shadow-color) 12%, transparent);
    outline: none;
  }

  .card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
  }

  .card-name {
    font-size: 1.05rem;
    font-family: var(--font-display);
    line-height: 1.15;
  }

  .card-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
  }

  .card-stats div {
    display: grid;
    gap: 0.2rem;
  }

  .card-stats span {
    font-size: 0.72rem;
    font-weight: 800;
    color: var(--text-soft);
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .card-stats strong {
    font-size: 0.95rem;
    letter-spacing: -0.02em;
  }
</style>
