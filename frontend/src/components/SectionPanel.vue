<script setup lang="ts">
  defineProps<{
    /** Eyebrow text above the title */
    eyebrow?: string
    /** Panel title */
    title?: string
    /** HTML element tag */
    tag?: 'section' | 'article' | 'aside' | 'div'
    /** Compact variant — centers actions vertically with header */
    compact?: boolean
  }>()
</script>

<template>
  <component :is="tag || 'section'" class="section-panel">
    <div
      v-if="eyebrow || title || $slots.title || $slots.actions"
      class="panel-head"
      :class="{ compact }"
    >
      <div>
        <p v-if="eyebrow" class="eyebrow subtle">{{ eyebrow }}</p>
        <h2 v-if="title">{{ title }}</h2>
        <slot v-else name="title" />
      </div>
      <slot name="actions" />
    </div>
    <slot />
  </component>
</template>

<style scoped>
  .section-panel {
    position: relative;
    isolation: isolate;
    display: grid;
    gap: 1.15rem;
    padding: 1.4rem;
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
    overflow: clip;
    transition:
      border-color 180ms ease,
      box-shadow 180ms ease,
      transform 180ms ease;
  }

  .section-panel::before {
    content: '';
    position: absolute;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 10%, transparent),
        transparent 30%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--glass-highlight) 72%, transparent),
        transparent 28%
      );
    opacity: 0.8;
  }

  .section-panel:hover {
    border-color: color-mix(in srgb, var(--border) 66%, var(--primary) 34%);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 18px 38px color-mix(in srgb, var(--shadow-color) 12%, transparent);
  }

  .section-panel:focus-within {
    border-color: color-mix(in srgb, var(--primary) 44%, var(--border) 56%);
  }

  .section-panel :deep(.panel-head) {
    margin-bottom: 0.1rem;
  }

  @media (prefers-reduced-motion: reduce) {
    .section-panel {
      transition: none;
    }

    .section-panel:hover {
      transform: none;
    }
  }
</style>
