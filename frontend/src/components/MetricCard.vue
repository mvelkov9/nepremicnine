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
    <span class="metric-card-label">{{ label }}</span>
    <strong class="metric-card-value">{{ value }}</strong>
    <small v-if="meta" class="metric-card-meta">{{ meta }}</small>
  </article>
</template>

<style scoped>
  .metric-card {
    position: relative;
    display: grid;
    align-content: start;
    gap: 0.35rem;
    min-height: 7rem;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 80%, var(--content-border-strong) 20%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 98%, transparent),
        transparent 120%
      ),
      var(--surface-panel, var(--surface-strong));
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
    overflow: hidden;
  }

  .metric-card::before {
    content: '';
    position: absolute;
    inset: 0 auto 0 0;
    width: 0.22rem;
    background: linear-gradient(180deg, var(--primary), var(--secondary));
    opacity: 0.9;
  }

  .metric-card-label {
    color: var(--text-soft);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.13em;
    text-transform: uppercase;
  }

  .metric-card-value {
    max-width: 14ch;
    font-size: clamp(1.22rem, 1.9vw, 1.85rem);
    line-height: 0.98;
    letter-spacing: -0.05em;
    text-wrap: balance;
  }

  .metric-card-meta {
    color: var(--text-soft);
    font-size: 0.78rem;
    line-height: 1.45;
    max-width: 30ch;
    text-wrap: pretty;
  }

  .metric-card.tone-success {
    border-color: color-mix(in srgb, var(--success) 28%, var(--border) 72%);
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--success) 12%, transparent), transparent 35%),
      color-mix(in srgb, var(--surface-panel, var(--surface-strong)) 90%, var(--success) 10%);
  }

  .metric-card.tone-warning {
    border-color: color-mix(in srgb, var(--warning) 28%, var(--border) 72%);
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--warning) 12%, transparent), transparent 35%),
      color-mix(in srgb, var(--surface-panel, var(--surface-strong)) 90%, var(--warning) 10%);
  }
</style>
