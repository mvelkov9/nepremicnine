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
    <div class="page-header-main">
      <div class="page-header-copy">
        <span v-if="eyebrow" class="page-header-eyebrow">{{ eyebrow }}</span>
        <h1 class="page-header-title">{{ title }}</h1>
        <p v-if="description" class="page-header-description">{{ description }}</p>
      </div>

      <div v-if="$slots.meta" class="page-header-meta">
        <slot name="meta" />
      </div>
    </div>

    <div v-if="$slots.actions" class="page-header-actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
  .page-header {
    position: relative;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.55rem 0.1rem 0.5rem;
    border-bottom: 1px solid color-mix(in srgb, var(--border) 82%, var(--content-border-strong) 18%);
    animation: page-header-enter 420ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .page-header.compact {
    align-items: center;
    padding-block: 0.4rem;
  }

  .page-header-main {
    display: grid;
    gap: 0.72rem;
    min-width: 0;
    flex: 1 1 auto;
  }

  .page-header-copy {
    display: grid;
    gap: 0.42rem;
    min-width: 0;
  }

  .page-header-meta {
    display: grid;
    gap: 0.55rem;
    min-width: 0;
  }

  .page-header::before {
    content: '';
    position: absolute;
    left: 0.1rem;
    bottom: -1px;
    width: clamp(5rem, 16vw, 11rem);
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(
      90deg,
      var(--primary),
      color-mix(in srgb, var(--secondary) 66%, var(--primary) 34%)
    );
    opacity: 0.9;
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
    font-size: clamp(1.62rem, 2.6vw, 2.45rem);
    line-height: 0.98;
    letter-spacing: -0.05em;
    text-wrap: balance;
  }

  .page-header.compact .page-header-title {
    font-size: clamp(1.2rem, 1.75vw, 1.6rem);
  }

  .page-header-description {
    margin: 0;
    max-width: 58ch;
    color: var(--text-muted);
    font-size: 0.93rem;
    line-height: 1.62;
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
    border-radius: 1.1rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  @keyframes page-header-enter {
    from {
      opacity: 0;
      transform: translateY(8px);
    }

    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (max-width: 720px) {
    .page-header {
      flex-direction: column;
      align-items: stretch;
      gap: 0.75rem;
      padding-top: 0.4rem;
    }

    .page-header-main {
      gap: 0.65rem;
    }

    .page-header-actions {
      width: 100%;
      justify-content: stretch;
    }

    .page-header-actions :deep(.p-button),
    .page-header-actions :deep(.p-select),
    .page-header-actions :deep(.p-inputtext),
    .page-header-actions :deep(.p-inputnumber) {
      width: 100%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .page-header {
      animation: none;
    }
  }
</style>
