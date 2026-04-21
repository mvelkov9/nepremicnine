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

  const pillars = computed(() => [
    {
      icon: 'dashboard',
      title: t('auth.viewerTitle'),
      value: t('auth.viewerValue'),
    },
    {
      icon: 'benchmark',
      title: t('auth.proofTitle'),
      value: t('auth.proofValue'),
    },
    {
      icon: 'admin',
      title: t('auth.adminTitle'),
      value: t('auth.adminValue'),
    },
  ])

  const highlights = computed(() => [
    t('auth.highlightPrepared'),
    t('auth.highlightModel'),
    t('auth.highlightInsights'),
  ])
</script>

<template>
  <aside class="auth-showcase" aria-label="Product overview">
    <header class="auth-showcase__intro">
      <p class="auth-showcase__eyebrow">{{ t('auth.showcaseEyebrow') }}</p>
      <div class="auth-showcase__brand-row">
        <span class="auth-showcase__brand-mark">
          <AppIcon name="brand" :size="20" />
        </span>
        <strong>{{ t('app.title') }}</strong>
      </div>
    </header>

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

    <div class="auth-showcase__pillars">
      <article v-for="pillar in pillars" :key="pillar.title" class="auth-pillar">
        <span class="auth-pillar__icon">
          <AppIcon :name="pillar.icon" :size="17" />
        </span>
        <div class="auth-pillar__copy">
          <strong>{{ pillar.title }}</strong>
          <p>{{ pillar.value }}</p>
        </div>
      </article>
    </div>

    <footer class="auth-showcase__footer">
      <p class="auth-showcase__notes-title">{{ t('auth.notesTitle') }}</p>
      <ul class="auth-showcase__highlights">
        <li v-for="point in highlights" :key="point">{{ point }}</li>
      </ul>
      <p class="auth-showcase__notes-footer">{{ t('auth.notesFooter') }}</p>
    </footer>
  </aside>
</template>

<style scoped>
  .auth-showcase {
    position: relative;
    display: grid;
    align-content: start;
    gap: 1.05rem;
    min-height: 100%;
    padding: clamp(1.25rem, 2vw, 1.8rem);
    border-radius: clamp(1.15rem, 2vw, 1.7rem);
    border: 1px solid color-mix(in srgb, var(--primary) 34%, transparent);
    background:
      radial-gradient(
        circle at 8% 0%,
        color-mix(in srgb, var(--secondary) 26%, transparent),
        transparent 36%
      ),
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--warning) 16%, transparent),
        transparent 32%
      ),
      radial-gradient(
        circle at left,
        color-mix(in srgb, var(--primary) 22%, transparent),
        transparent 40%
      ),
      var(--surface-panel-dark);
    color: var(--shell-text);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 8%),
      0 28px 56px color-mix(in srgb, rgb(2 6 23) 24%, transparent);
    overflow: clip;
    animation: showcase-enter 720ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .auth-showcase::before {
    content: '';
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: linear-gradient(180deg, rgb(255 255 255 / 8%), transparent 32%);
  }

  .auth-showcase::after {
    content: '';
    position: absolute;
    inset: 1rem;
    pointer-events: none;
    border-radius: calc(clamp(1.15rem, 2vw, 1.7rem) - 0.55rem);
    border: 1px solid rgb(255 255 255 / 9%);
    opacity: 0.65;
  }

  .auth-showcase > * {
    position: relative;
    z-index: 1;
  }

  .auth-showcase__intro {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.7rem;
  }

  .auth-showcase__eyebrow {
    margin: 0;
    color: var(--shell-text-muted);
    font-size: 0.71rem;
    font-weight: 800;
    letter-spacing: 0.13em;
    text-transform: uppercase;
  }

  .auth-showcase__brand-row {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.24rem 0.58rem;
    border-radius: 999px;
    border: 1px solid rgb(255 255 255 / 15%);
    background: rgb(255 255 255 / 8%);
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 12%);
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .auth-showcase__brand-mark {
    display: inline-grid;
    place-items: center;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 0.6rem;
    color: var(--primary-contrast);
    background: linear-gradient(
      160deg,
      color-mix(in srgb, var(--primary) 86%, white 14%),
      color-mix(in srgb, var(--secondary) 70%, var(--primary) 30%)
    );
  }

  .auth-showcase__hero {
    display: grid;
    gap: 0.56rem;
    max-width: 33rem;
  }

  .auth-showcase__hero h1 {
    margin: 0;
    max-width: 13ch;
    color: var(--shell-text);
    font-family: var(--font-display);
    font-size: clamp(2rem, 3vw, 2.8rem);
    line-height: 0.92;
    letter-spacing: -0.04em;
    text-wrap: balance;
    text-shadow: 0 8px 24px rgb(2 8 22 / 34%);
  }

  .auth-showcase__hero p {
    margin: 0;
    max-width: 39ch;
    color: var(--shell-text-soft);
    font-size: 0.92rem;
    line-height: 1.63;
  }

  .auth-showcase__band {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .auth-showcase__band-item {
    display: inline-flex;
    align-items: center;
    min-height: 1.9rem;
    padding: 0.29rem 0.68rem;
    border-radius: 999px;
    border: 1px solid rgb(255 255 255 / 14%);
    background:
      linear-gradient(180deg, rgb(255 255 255 / 16%), rgb(255 255 255 / 8%)), rgb(255 255 255 / 8%);
    color: var(--shell-text-soft);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 10%);
  }

  .auth-showcase__feature-grid {
    display: grid;
    gap: 0.66rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .auth-feature-card {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.64rem;
    align-items: start;
    padding: 0.85rem 0.9rem;
    border-radius: 0.95rem;
    border: 1px solid rgb(255 255 255 / 10%);
    background:
      linear-gradient(180deg, rgb(255 255 255 / 12%), rgb(255 255 255 / 6%)), rgb(255 255 255 / 7%);
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 10%);
    animation: showcase-rise 560ms cubic-bezier(0.22, 1, 0.36, 1) both;
  }

  .auth-feature-card:nth-child(2) {
    animation-delay: 80ms;
  }

  .auth-feature-card:nth-child(3) {
    animation-delay: 160ms;
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
    gap: 0.2rem;
  }

  .auth-feature-card__copy strong {
    color: var(--shell-text);
    font-size: 0.86rem;
    line-height: 1.2;
  }

  .auth-feature-card__copy p {
    margin: 0;
    color: var(--shell-text-soft);
    font-size: 0.79rem;
    line-height: 1.46;
  }

  .auth-showcase__pillars {
    display: grid;
    gap: 0.62rem;
  }

  .auth-pillar {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.7rem;
    align-items: start;
    padding: 0.7rem 0.82rem;
    border-radius: 0.9rem;
    border: 1px solid rgb(255 255 255 / 11%);
    background: color-mix(in srgb, var(--surface-dark) 84%, transparent);
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 8%);
  }

  .auth-pillar__icon {
    display: inline-grid;
    place-items: center;
    width: 1.9rem;
    height: 1.9rem;
    border-radius: 0.72rem;
    color: var(--primary-contrast);
    background: color-mix(in srgb, var(--primary) 28%, transparent);
  }

  .auth-pillar__copy {
    display: grid;
    gap: 0.16rem;
  }

  .auth-pillar__copy strong {
    color: var(--shell-text);
    font-size: 0.86rem;
    line-height: 1.2;
  }

  .auth-pillar__copy p {
    margin: 0;
    color: var(--shell-text-soft);
    font-size: 0.76rem;
    line-height: 1.48;
  }

  .auth-showcase__footer {
    margin-top: 0.22rem;
    padding-top: 0.82rem;
    border-top: 1px solid rgb(255 255 255 / 12%);
    display: grid;
    gap: 0.5rem;
  }

  .auth-showcase__notes-title {
    margin: 0;
    color: var(--shell-text);
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.03em;
  }

  .auth-showcase__highlights {
    margin: 0;
    padding-left: 1rem;
    display: grid;
    gap: 0.26rem;
    color: var(--shell-text-soft);
    font-size: 0.76rem;
    line-height: 1.45;
  }

  .auth-showcase__notes-footer {
    margin: 0;
    color: var(--shell-text-muted);
    font-size: 0.72rem;
    line-height: 1.48;
  }

  @keyframes showcase-enter {
    from {
      opacity: 0;
      transform: translateY(14px);
    }

    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes showcase-rise {
    from {
      opacity: 0;
      transform: translateY(12px);
    }

    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (max-width: 1280px) {
    .auth-showcase__feature-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 1024px) {
    .auth-showcase {
      padding: 1rem;
      gap: 0.9rem;
    }

    .auth-showcase__hero h1 {
      font-size: clamp(1.8rem, 5.5vw, 2.2rem);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .auth-showcase,
    .auth-feature-card {
      animation: none;
    }
  }
</style>
