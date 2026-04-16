<script setup lang="ts">
  export interface MunicipalityHeroMetric {
    label: string
    value: string
    meta?: string
    tone?: 'default' | 'warm' | 'success' | 'accent'
  }

  defineProps<{
    municipality: string
    region?: string
    coverageWindow: string
    regionRank: string | number
    rankLabel: string
    headline: string
    summary: string
    featuredLabel: string
    featuredValue: string
    featuredMeta?: string
    heroMetrics: MunicipalityHeroMetric[]
  }>()
</script>

<template>
  <section class="municipality-hero">
    <div class="hero-copy">
      <div class="hero-story">
        <span class="hero-kicker">{{ municipality }}</span>
        <h2>{{ headline }}</h2>
        <p>{{ summary }}</p>
      </div>

      <div class="hero-chips">
        <span class="hero-chip">{{ region || '-' }}</span>
        <span class="hero-chip">{{ coverageWindow }}</span>
        <span class="hero-chip">{{ rankLabel }} #{{ regionRank }}</span>
      </div>
    </div>

    <div class="hero-rail">
      <article class="hero-feature">
        <span class="eyebrow subtle">{{ featuredLabel }}</span>
        <strong>{{ featuredValue }}</strong>
        <p>{{ featuredMeta }}</p>
      </article>

      <div class="hero-metrics">
        <article
          v-for="metric in heroMetrics"
          :key="metric.label"
          class="hero-metric"
          :class="metric.tone ? `tone-${metric.tone}` : ''"
        >
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <p v-if="metric.meta">{{ metric.meta }}</p>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
  .municipality-hero {
    display: grid;
    grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.95fr);
    gap: 1rem;
    padding: 1.2rem;
    border-radius: calc(var(--radius-lg) + 0.15rem);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--primary) 16%, transparent),
        transparent 34%
      ),
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--secondary) 12%, transparent),
        transparent 30%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 140%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .hero-copy {
    display: grid;
    gap: 1rem;
    align-content: start;
  }

  .hero-story {
    display: grid;
    gap: 0.5rem;
  }

  .hero-kicker {
    width: fit-content;
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--primary) 24%, var(--border) 76%);
    background: color-mix(in srgb, var(--primary) 10%, var(--surface-card-strong));
    color: color-mix(in srgb, var(--primary) 72%, var(--text) 28%);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.15em;
    text-transform: uppercase;
  }

  .hero-story h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.8rem, 3vw, 2.7rem);
    line-height: 0.96;
    letter-spacing: -0.05em;
  }

  .hero-story p,
  .hero-feature p,
  .hero-metric p {
    margin: 0;
    color: var(--text-muted);
    line-height: 1.58;
  }

  .hero-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
  }

  .hero-chip {
    display: inline-flex;
    align-items: center;
    min-height: 2rem;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background: var(--surface-soft);
    color: var(--text-soft);
    font-size: 0.84rem;
    font-weight: 700;
  }

  .hero-rail {
    display: grid;
    gap: 0.85rem;
    align-content: start;
  }

  .hero-feature {
    display: grid;
    gap: 0.35rem;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 70%, var(--primary) 30%);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--secondary) 16%, transparent),
        transparent 40%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-soft);
  }

  .hero-feature strong {
    display: block;
    font-size: clamp(1.8rem, 3vw, 2.6rem);
    line-height: 1;
    letter-spacing: -0.05em;
  }

  .hero-metrics {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .hero-metric {
    display: grid;
    gap: 0.3rem;
    padding: 0.92rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 80%, var(--primary) 20%);
    background: var(--surface-soft);
  }

  .hero-metric span {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .hero-metric strong {
    font-size: 1.08rem;
    line-height: 1.15;
    letter-spacing: -0.03em;
  }

  .hero-metric.tone-warm {
    border-color: color-mix(in srgb, var(--warning) 28%, var(--border));
  }

  .hero-metric.tone-success {
    border-color: color-mix(in srgb, var(--secondary) 28%, var(--border));
  }

  .hero-metric.tone-accent {
    border-color: color-mix(in srgb, var(--primary) 34%, var(--border));
  }

  @media (max-width: 980px) {
    .municipality-hero,
    .hero-metrics {
      grid-template-columns: 1fr;
    }
  }
</style>
