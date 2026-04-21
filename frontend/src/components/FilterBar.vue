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
    position: relative;
    isolation: isolate;
    display: grid;
    align-items: end;
    gap: 0.95rem;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    padding: 1.12rem;
    border-radius: calc(var(--radius-md) + 0.1rem);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 98%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
    transition:
      border-color 170ms ease,
      box-shadow 170ms ease;
  }

  .filter-bar::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    pointer-events: none;
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 8%, transparent),
        transparent 36%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--glass-highlight) 64%, transparent),
        transparent 28%
      );
  }

  .filter-bar :deep(.field-inline) {
    min-width: 0;
  }

  .filter-bar :deep(.field-inline span) {
    color: var(--text-soft);
    font-size: 0.71rem;
    letter-spacing: 0.1em;
  }

  .filter-bar :deep(.p-inputtext),
  .filter-bar :deep(.p-select),
  .filter-bar :deep(.p-inputnumber-input),
  .filter-bar :deep(.p-autocomplete-input) {
    min-height: 2.75rem;
  }

  .filter-bar:hover {
    border-color: color-mix(in srgb, var(--border) 62%, var(--primary) 38%);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 16px 30px color-mix(in srgb, var(--shadow-color) 10%, transparent);
  }

  @media (max-width: 640px) {
    .filter-bar {
      grid-template-columns: 1fr !important;
      padding: 0.95rem;
    }
  }
</style>
