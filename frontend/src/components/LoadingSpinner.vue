<script setup>
  defineProps({
    label: { type: String, default: '' },
  })
</script>

<template>
  <div
    class="loading-spinner-container"
    role="status"
    aria-live="polite"
    aria-busy="true"
    :aria-label="label || 'Loading'"
  >
    <div class="loading-spinner" aria-hidden="true">
      <span class="loading-spinner__inner"></span>
    </div>
    <span v-if="label" class="spinner-label">{{ label }}</span>
  </div>
</template>

<style scoped>
  .loading-spinner-container {
    display: grid;
    gap: 0.9rem;
    align-items: center;
    justify-items: center;
    min-height: 9rem;
    padding: 1.8rem 1rem;
    text-align: center;
  }

  .loading-spinner {
    position: relative;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: conic-gradient(
      from 180deg,
      color-mix(in srgb, var(--primary) 88%, transparent),
      color-mix(in srgb, var(--secondary) 76%, transparent),
      transparent 70%
    );
    box-shadow:
      0 0 0 8px color-mix(in srgb, var(--primary) 8%, transparent),
      0 14px 28px color-mix(in srgb, var(--primary) 12%, transparent);
    animation: spin 0.9s linear infinite;
  }

  .loading-spinner__inner {
    position: absolute;
    inset: 6px;
    border-radius: 50%;
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
      var(--surface-card-strong)
    );
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
  }

  .spinner-label {
    color: var(--text-muted, #64748b);
    font-size: var(--text-meta);
    max-width: 28ch;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
