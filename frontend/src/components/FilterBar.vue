<script setup lang="ts">
  defineProps<{
    /** Number of grid columns (default: 4) */
    columns?: number
  }>()
</script>

<template>
  <div class="filter-bar filter-shell" :data-columns="columns ?? 4">
    <slot />
  </div>
</template>

<style scoped>
  .filter-bar {
    display: grid;
    align-items: end;
    gap: 0.9rem;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    padding: 1.08rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--surface-card-strong) 98%, transparent), transparent 120%),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .filter-bar :deep(.field-inline) {
    min-width: 0;
  }

  @media (max-width: 640px) {
    .filter-bar {
      grid-template-columns: 1fr !important;
    }
  }
</style>
