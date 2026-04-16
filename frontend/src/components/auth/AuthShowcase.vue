<script setup lang="ts">
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import AppIcon from '../AppIcon.vue'

  const { t } = useI18n()

  const bands = computed(() => [
    t('auth.marketBandMap'),
    t('auth.marketBandTrend'),
    t('auth.marketBandEstimate'),
  ])

  const cards = computed(() => [
    {
      icon: 'map',
      label: t('auth.marketMap'),
      value: t('auth.marketMapValue'),
    },
    {
      icon: 'trend',
      label: t('auth.marketTrend'),
      value: t('auth.marketTrendValue'),
    },
    {
      icon: 'prediction',
      label: t('auth.marketEstimate'),
      value: t('auth.marketEstimateValue'),
    },
  ])
</script>

<template>
  <aside class="auth-showcase" aria-label="Product overview">
    <p class="auth-showcase__eyebrow">{{ t('auth.showcaseEyebrow') }}</p>

    <div class="auth-showcase__hero">
      <h1>{{ t('auth.welcomeTitle') }}</h1>
      <p>{{ t('auth.welcomeBody') }}</p>
    </div>

    <div class="auth-showcase__band">
      <span v-for="item in bands" :key="item" class="auth-showcase__band-item">
        {{ item }}
      </span>
    </div>

    <div class="auth-showcase__feature-grid">
      <article v-for="card in cards" :key="card.label" class="auth-feature-card">
        <span class="auth-feature-card__icon">
          <AppIcon :name="card.icon" :size="18" />
        </span>
        <div class="auth-feature-card__copy">
          <strong>{{ card.label }}</strong>
          <p>{{ card.value }}</p>
        </div>
      </article>
    </div>
  </aside>
</template>

<style scoped>
  .auth-showcase {
    position: relative;
    display: grid;
    align-content: start;
    gap: 1.15rem;
    padding: clamp(1.35rem, 2.5vw, 2rem);
    border-radius: clamp(1.2rem, 2vw, 1.65rem);
    border: 1px solid color-mix(in srgb, var(--primary) 24%, var(--border) 76%);
    background:
      radial-gradient(circle at top right, color-mix(in srgb, var(--warning) 14%, transparent), transparent 24%),
      radial-gradient(circle at left, color-mix(in srgb, var(--primary) 16%, transparent), transparent 32%),
      var(--surface-panel-dark);
    color: var(--shell-text);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 8%),
      0 24px 48px color-mix(in srgb, rgb(2 6 23) 20%, transparent);
    overflow: clip;
  }

  .auth-showcase::before {
    content: '';
    position: absolute;
    inset: 0;
    pointer-events: none;
    background:
      linear-gradient(180deg, rgb(255 255 255 / 6%), transparent 24%),
      radial-gradient(circle at 84% 16%, rgb(255 255 255 / 8%), transparent 24%);
  }

  .auth-showcase > * {
    position: relative;
    z-index: 1;
  }

  .auth-showcase__eyebrow {
    margin: 0;
    color: var(--shell-text-muted);
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .auth-showcase__hero {
    display: grid;
    gap: 0.6rem;
    max-width: 30rem;
  }

  .auth-showcase__hero h1 {
    margin: 0;
    max-width: 12ch;
    color: var(--shell-text);
    font-family: var(--font-display);
    font-size: clamp(1.9rem, 3vw, 2.65rem);
    line-height: 0.97;
    letter-spacing: -0.05em;
    text-wrap: balance;
  }

  .auth-showcase__hero p {
    margin: 0;
    max-width: 37ch;
    color: var(--shell-text-soft);
    font-size: 0.94rem;
    line-height: 1.66;
  }

  .auth-showcase__band {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .auth-showcase__band-item {
    display: inline-flex;
    align-items: center;
    min-height: 1.9rem;
    padding: 0.32rem 0.72rem;
    border-radius: 999px;
    border: 1px solid rgb(255 255 255 / 14%);
    background:
      linear-gradient(180deg, rgb(255 255 255 / 16%), rgb(255 255 255 / 8%)),
      rgb(255 255 255 / 8%);
    color: var(--shell-text-soft);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 10%);
  }

  .auth-showcase__feature-grid {
    display: grid;
    gap: 0.72rem;
  }

  .auth-feature-card {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.82rem;
    align-items: start;
    padding: 0.9rem 0.95rem;
    border-radius: 1rem;
    border: 1px solid rgb(255 255 255 / 10%);
    background:
      linear-gradient(180deg, rgb(255 255 255 / 12%), rgb(255 255 255 / 6%)),
      rgb(255 255 255 / 7%);
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 10%);
  }

  .auth-feature-card__icon {
    display: inline-grid;
    place-items: center;
    width: 2rem;
    height: 2rem;
    border-radius: 0.85rem;
    background: color-mix(in srgb, var(--primary) 22%, transparent);
    color: var(--primary-contrast);
  }

  .auth-feature-card__copy {
    display: grid;
    gap: 0.22rem;
  }

  .auth-feature-card__copy strong {
    color: var(--shell-text);
    font-size: 0.95rem;
    line-height: 1.2;
  }

  .auth-feature-card__copy p {
    margin: 0;
    color: var(--shell-text-soft);
    font-size: 0.85rem;
    line-height: 1.56;
  }
</style>
