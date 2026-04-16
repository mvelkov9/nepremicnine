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
    display: grid;
    gap: 1.1rem;
    padding: 1.35rem;
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
  }

  .section-panel :deep(.panel-head) {
    margin-bottom: 0.1rem;
  }
</style>
