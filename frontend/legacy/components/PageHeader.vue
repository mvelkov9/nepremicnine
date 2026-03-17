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
      <div class="page-header-meta">
        <span v-if="eyebrow" class="page-header-eyebrow">{{ eyebrow }}</span>
        <span class="page-header-rule"></span>
      </div>
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
    padding: 0;
  }

  .page-header.compact {
    align-items: center;
  }

  .page-header-copy {
    display: grid;
    gap: 0.65rem;
    min-width: 0;
  }

  .page-header-meta {
    display: flex;
    align-items: center;
    gap: 0.8rem;
  }

  .page-header-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 2rem;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    border: 1px solid var(--ui-border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--ui-bg-elevated) 92%, transparent),
      color-mix(in srgb, var(--ui-primary) 7%, transparent)
    );
    color: var(--ui-text-muted);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 10px 18px rgb(15 23 42 / 6%);
  }

  .page-header-rule {
    width: 4.5rem;
    height: 1px;
    border-radius: 999px;
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--ui-primary) 34%, transparent),
      color-mix(in srgb, var(--ui-secondary) 28%, transparent)
    );
  }

  .page-header-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.7rem, 2.6vw, 2.8rem);
    line-height: 0.97;
    letter-spacing: -0.055em;
    font-weight: 700;
  }

  .page-header-description {
    margin: 0;
    max-width: 58ch;
    color: var(--ui-text-muted);
    font-size: 0.92rem;
    line-height: 1.6;
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

    .page-header-meta {
      gap: 0.55rem;
    }
  }
</style>
