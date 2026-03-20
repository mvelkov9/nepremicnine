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
    gap: 1.15rem;
  }

  .page-header.compact {
    align-items: center;
  }

  .page-header-copy {
    display: grid;
    gap: 0.6rem;
    min-width: 0;
  }

  .page-header-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    width: fit-content;
    padding: 0.42rem 0.78rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--primary) 22%, var(--border));
    background:
      linear-gradient(135deg, color-mix(in srgb, var(--primary) 10%, transparent), transparent),
      var(--surface-panel-muted, color-mix(in srgb, var(--surface-soft) 88%, white 12%));
    color: var(--primary-strong);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }

  .page-header-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.55rem, 2.9vw, 2.7rem);
    line-height: 0.98;
    letter-spacing: -0.05em;
  }

  .page-header.compact .page-header-title {
    font-size: clamp(1.28rem, 2.1vw, 1.92rem);
  }

  .page-header-description {
    margin: 0;
    max-width: 60ch;
    color: var(--text-muted);
    font-size: 0.95rem;
    line-height: 1.65;
  }

  .page-header-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 0.7rem;
    align-self: flex-start;
  }

  @media (max-width: 720px) {
    .page-header {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
