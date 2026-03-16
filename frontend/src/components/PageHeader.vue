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
    gap: 1rem;
  }

  .page-header.compact {
    align-items: center;
  }

  .page-header-copy {
    display: grid;
    gap: 0.45rem;
    min-width: 0;
  }

  .page-header-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    color: var(--primary);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }

  .page-header-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.45rem, 2.5vw, 2.35rem);
    line-height: 1.02;
    letter-spacing: -0.04em;
  }

  .page-header-description {
    margin: 0;
    max-width: 58ch;
    color: var(--text-muted);
    font-size: 0.94rem;
  }

  .page-header-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  @media (max-width: 720px) {
    .page-header {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
