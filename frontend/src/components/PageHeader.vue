<script setup>
  defineProps({
    eyebrow: { type: String, default: '' },
    title: { type: String, required: true },
    description: { type: String, default: '' },
    compact: { type: Boolean, default: false },
  })
</script>

<template>
  <header class="page-header" :class="{ compact }">
    <div class="page-header-copy">
      <span v-if="eyebrow" class="page-header-eyebrow">{{ eyebrow }}</span>
      <h1 class="page-header-title">{{ title }}</h1>
      <p v-if="description" class="page-header-description">{{ description }}</p>
    </div>

    <div v-if="$slots.actions" class="page-header-actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.9rem;
    padding: 0.15rem 0 0.1rem;
  }

  .page-header.compact {
    align-items: center;
  }

  .page-header-copy {
    display: grid;
    gap: 0.38rem;
    min-width: 0;
  }

  .page-header-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    width: fit-content;
    padding: 0.38rem 0.78rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--primary) 20%, var(--border) 80%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 94%, transparent),
        transparent 120%
      ),
      color-mix(in srgb, var(--surface-card-strong) 90%, var(--primary) 10%);
    color: color-mix(in srgb, var(--primary) 78%, var(--text) 22%);
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }

  .page-header-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.58rem, 2.4vw, 2.3rem);
    line-height: 0.98;
    letter-spacing: -0.055em;
    text-wrap: balance;
  }

  .page-header.compact .page-header-title {
    font-size: clamp(1.18rem, 1.7vw, 1.55rem);
  }

  .page-header-description {
    margin: 0;
    max-width: 54ch;
    color: var(--text-muted);
    font-size: 0.95rem;
    line-height: 1.58;
    text-wrap: pretty;
  }

  .page-header-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 0.55rem;
    align-self: flex-start;
    padding: 0.45rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow: var(--shadow-sm);
  }

  @media (max-width: 720px) {
    .page-header {
      flex-direction: column;
      align-items: stretch;
      gap: 0.8rem;
    }

    .page-header-actions {
      width: 100%;
    }
  }
</style>
