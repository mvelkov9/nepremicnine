<script setup>
  import { computed } from 'vue'

  const props = defineProps({
    eyebrow: { type: String, default: '' },
    title: { type: String, required: true },
    description: { type: String, default: '' },
    compact: { type: Boolean, default: false },
  })

  const titleTag = computed(() => (props.compact ? 'h2' : 'h1'))
</script>

<template>
  <header
    class="page-header"
    :class="{ compact, 'has-meta': !!$slots.meta, 'has-actions': !!$slots.actions }"
  >
    <div class="page-header-main">
      <div class="page-header-copy">
        <span v-if="eyebrow" class="page-header-eyebrow">{{ eyebrow }}</span>
        <component :is="titleTag" class="page-header-title">{{ title }}</component>
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
    display: grid;
    gap: 0.95rem;
    padding: 0.15rem 0 0.7rem;
    animation: page-header-enter 420ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .page-header.compact {
    gap: 0.55rem;
    padding-block: 0 0.05rem;
  }

  .page-header-main {
    display: grid;
    gap: 0.9rem;
    min-width: 0;
  }

  .page-header-copy {
    display: grid;
    gap: 0.48rem;
    min-width: 0;
  }

  .page-header-meta {
    display: grid;
    gap: 0.55rem;
    min-width: 0;
    align-content: end;
  }

  .page-header.has-meta:not(.compact) .page-header-main {
    grid-template-columns: minmax(0, 1fr) minmax(15rem, 23rem);
    align-items: end;
  }

  .page-header::before {
    content: '';
    position: absolute;
    left: 0;
    bottom: 0;
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

  .page-header::after {
    content: '';
    position: absolute;
    inset: auto 0 0;
    height: 1px;
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--border) 86%, transparent),
      color-mix(in srgb, var(--border) 36%, transparent)
    );
    opacity: 0.95;
  }

  .page-header.compact::before {
    width: clamp(3.5rem, 12vw, 7rem);
    opacity: 0.72;
  }

  .page-header.compact::after {
    opacity: 0.58;
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
    max-width: 18ch;
    line-height: 0.99;
    letter-spacing: -0.05em;
    text-wrap: balance;
  }

  .page-header.compact .page-header-title {
    font-size: clamp(1.2rem, 1.75vw, 1.6rem);
    letter-spacing: -0.035em;
  }

  .page-header.compact .page-header-eyebrow {
    padding: 0.28rem 0.62rem;
    font-size: 0.64rem;
    letter-spacing: 0.12em;
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      color-mix(in srgb, var(--surface-card-strong) 94%, var(--primary) 6%);
  }

  .page-header.compact .page-header-description {
    font-size: 0.9rem;
    line-height: 1.5;
  }

  .page-header-description {
    margin: 0;
    max-width: 62ch;
    color: var(--text-soft);
    font-size: 0.95rem;
    line-height: 1.58;
    text-wrap: pretty;
  }

  .page-header-actions {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 0.6rem;
    min-width: 0;
  }

  .page-header.has-actions .page-header-actions {
    padding-top: 0.05rem;
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
      gap: 0.75rem;
      padding-top: 0.05rem;
    }

    .page-header-main {
      gap: 0.65rem;
    }

    .page-header.has-meta .page-header-main {
      grid-template-columns: 1fr;
    }

    .page-header-title {
      max-width: none;
    }

    .page-header-meta {
      justify-items: start;
    }

    .page-header-actions {
      width: 100%;
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
