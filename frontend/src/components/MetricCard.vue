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
    display: grid;
    gap: 0.3rem;
    padding: 1rem;
    border-radius: 1.2rem;
    border: 1px solid var(--border);
    background: var(--surface-elevated);
    box-shadow: var(--shadow-sm);
  }

  .metric-card-label {
    color: var(--text-soft);
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.15em;
    text-transform: uppercase;
  }

  .metric-card-value {
    font-size: clamp(1.1rem, 2vw, 1.55rem);
    letter-spacing: -0.04em;
  }

  .metric-card-meta {
    color: var(--text-muted);
    font-size: 0.82rem;
  }

  .metric-card.tone-success {
    border-color: rgb(16 185 129 / 24%);
  }

  .metric-card.tone-warning {
    border-color: rgb(245 158 11 / 26%);
  }
</style>
