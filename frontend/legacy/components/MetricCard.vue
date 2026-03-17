<script setup>
  defineProps({
    label: { type: String, required: true },
    value: { type: String, required: true },
    meta: { type: String, default: '' },
    tone: { type: String, default: 'default' },
  })
</script>

<template>
  <article class="metric-card" :class="`tone-${tone}`">
    <span class="metric-card-glow"></span>
    <span class="metric-card-label">{{ label }}</span>
    <strong class="metric-card-value">{{ value }}</strong>
    <small v-if="meta" class="metric-card-meta">{{ meta }}</small>
  </article>
</template>

<style scoped>
  .metric-card {
    position: relative;
    overflow: hidden;
    display: grid;
    gap: 0.55rem;
    padding: 1.2rem 1.25rem;
    border-radius: 1.6rem;
    border: 1px solid var(--ui-border);
    background: var(--surface-panel-strong);
    box-shadow: 0 18px 34px rgb(15 23 42 / 6%);
    transition:
      transform 180ms ease,
      border-color 180ms ease,
      box-shadow 180ms ease,
      background 180ms ease;
  }

  .metric-card::after {
    content: '';
    position: absolute;
    inset: auto 1.2rem 0.95rem 1.2rem;
    height: 1px;
    border-radius: 999px;
    background:
      linear-gradient(
        90deg,
        color-mix(in srgb, var(--ui-primary) 22%, transparent),
        transparent
      );
    pointer-events: none;
  }

  .metric-card:hover {
    transform: translateY(-3px);
    border-color: color-mix(in srgb, var(--ui-primary) 24%, var(--ui-border));
    background: var(--surface-brand-soft);
    box-shadow: 0 24px 42px rgb(15 23 42 / 11%);
  }

  .metric-card-glow {
    position: absolute;
    inset: auto auto calc(100% - 4rem) -1.4rem;
    width: 6rem;
    height: 6rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--ui-primary) 14%, transparent);
    filter: blur(16px);
    opacity: 0.55;
    pointer-events: none;
  }

  .metric-card-label {
    color: var(--ui-text-muted);
    font-size: 0.69rem;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-transform: uppercase;
  }

  .metric-card-value {
    font-family: var(--font-display);
    font-size: clamp(1.55rem, 2.5vw, 2.3rem);
    letter-spacing: -0.06em;
    line-height: 1;
  }

  .metric-card-meta {
    color: var(--ui-text-muted);
    font-size: 0.84rem;
    line-height: 1.5;
  }

  .metric-card.tone-success {
    border-color: color-mix(in srgb, var(--ui-success) 26%, var(--ui-border));
  }

  .metric-card.tone-success .metric-card-glow {
    background: color-mix(in srgb, var(--ui-success) 18%, transparent);
  }

  .metric-card.tone-warning {
    border-color: color-mix(in srgb, var(--ui-warning) 28%, var(--ui-border));
  }

  .metric-card.tone-warning .metric-card-glow {
    background: color-mix(in srgb, var(--ui-warning) 18%, transparent);
  }
</style>
