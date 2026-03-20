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
    overflow: hidden;
    display: grid;
    gap: 0.42rem;
    padding: 1.05rem 1.1rem;
    border-radius: 1.4rem;
    border: 1px solid color-mix(in srgb, var(--border) 84%, white 16%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--overlay-soft) 84%, transparent),
        transparent 34%
      ),
      linear-gradient(
        145deg,
        color-mix(in srgb, var(--surface-strong) 90%, var(--primary) 10%),
        color-mix(in srgb, var(--surface-soft) 93%, var(--secondary) 7%)
      );
    box-shadow: var(--shadow-sm);
  }

  .metric-card::before {
    content: '';
    position: absolute;
    inset: 0 auto auto 0;
    width: 5.25rem;
    height: 5.25rem;
    background: radial-gradient(circle, var(--accent-glow-start), transparent 70%);
    pointer-events: none;
  }

  .metric-card-label {
    position: relative;
    color: var(--text-soft);
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.15em;
    text-transform: uppercase;
  }

  .metric-card-value {
    position: relative;
    font-size: clamp(1.18rem, 2.2vw, 1.82rem);
    line-height: 1.02;
    letter-spacing: -0.05em;
  }

  .metric-card-meta {
    position: relative;
    color: var(--text-muted);
    font-size: 0.84rem;
    line-height: 1.5;
  }

  .metric-card.tone-success {
    border-color: color-mix(in srgb, var(--success) 28%, transparent);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--overlay-soft) 84%, transparent),
        transparent 34%
      ),
      linear-gradient(
        145deg,
        color-mix(in srgb, var(--surface-strong) 86%, var(--success) 14%),
        color-mix(in srgb, var(--surface-soft) 92%, var(--success) 8%)
      );
  }

  .metric-card.tone-warning {
    border-color: color-mix(in srgb, var(--warning) 28%, transparent);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--overlay-soft) 84%, transparent),
        transparent 34%
      ),
      linear-gradient(
        145deg,
        color-mix(in srgb, var(--surface-strong) 88%, var(--warning) 12%),
        color-mix(in srgb, var(--surface-soft) 93%, var(--warning) 7%)
      );
  }
</style>
