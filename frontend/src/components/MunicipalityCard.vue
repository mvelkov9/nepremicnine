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
    <span class="card-accent" aria-hidden="true" />
    <div class="card-top">
      <div class="card-heading">
        <span class="card-kicker">{{ t('dashboard.municipality') }}</span>
        <strong class="card-name">{{ municipality }}</strong>
      </div>
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
    position: relative;
    isolation: isolate;
    display: grid;
    gap: 1rem;
    align-content: start;
    min-height: 100%;
    padding: 1.15rem 1.15rem 1.05rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--content-border-strong) 32%);
    border-radius: calc(var(--radius-lg) - 0.1rem);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 12%, transparent),
        transparent 28%
      ),
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--secondary) 10%, transparent),
        transparent 32%
      ),
      color-mix(in srgb, var(--surface-card-strong) 96%, transparent);
    text-decoration: none;
    color: inherit;
    overflow: hidden;
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 14px 28px color-mix(in srgb, rgb(2 6 23) 9%, transparent);
    transition:
      transform 0.18s ease,
      border-color 0.18s ease,
      box-shadow 0.18s ease,
      background-position 0.18s ease;
  }

  .municipality-card:hover,
  .municipality-card:focus-visible {
    transform: translateY(-4px);
    border-color: color-mix(in srgb, var(--primary) 42%, var(--border) 58%);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 22px 40px color-mix(in srgb, rgb(2 6 23) 12%, transparent),
      0 0 0 1px color-mix(in srgb, var(--primary) 10%, transparent);
    outline: none;
  }

  .municipality-card:active {
    transform: translateY(-1px) scale(0.995);
  }

  .municipality-card:hover .card-name,
  .municipality-card:focus-visible .card-name {
    color: var(--primary-strong);
  }

  .municipality-card:hover .card-kicker,
  .municipality-card:focus-visible .card-kicker {
    color: var(--primary-strong);
  }

  .municipality-card:hover .card-accent,
  .municipality-card:focus-visible .card-accent {
    opacity: 1;
  }

  .card-accent {
    position: absolute;
    inset: 0 auto auto 0;
    width: 100%;
    height: 0.24rem;
    background: linear-gradient(90deg, var(--primary), var(--secondary));
    opacity: 0.8;
    transition: opacity 0.16s ease;
    pointer-events: none;
  }

  .card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
  }

  .card-heading {
    display: grid;
    gap: 0.3rem;
    min-width: 0;
  }

  .card-kicker {
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .card-name {
    font-size: 1.08rem;
    font-family: var(--font-display);
    line-height: 1.08;
    text-wrap: balance;
    letter-spacing: -0.02em;
  }

  .card-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }

  .card-stats div {
    display: grid;
    gap: 0.2rem;
    padding: 0.82rem 0.88rem;
    border-radius: calc(var(--radius-sm) + 0.2rem);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 90%, transparent),
        transparent 140%
      ),
      var(--surface-subtle);
    border: 1px solid color-mix(in srgb, var(--border) 70%, var(--content-border-strong) 30%);
  }

  .card-stats span {
    font-size: var(--text-xs);
    font-weight: 850;
    color: var(--text);
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .card-stats strong {
    font-size: 0.98rem;
    letter-spacing: -0.03em;
  }

  :deep(.p-tag) {
    background: color-mix(in srgb, var(--surface-card-strong) 84%, var(--primary) 16%);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    color: var(--text-soft);
    box-shadow: inset 0 1px 0 var(--content-glow);
  }

  :deep(.p-tag .p-tag-label) {
    font-weight: 700;
    letter-spacing: 0.01em;
  }

  @media (max-width: 540px) {
    .municipality-card {
      padding: 1rem;
    }

    .card-top {
      align-items: flex-start;
    }

    .card-stats {
      grid-template-columns: 1fr;
    }
  }
</style>
