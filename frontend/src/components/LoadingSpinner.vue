<template>
  <div class="loading-spinner-container" role="status" :aria-label="label || 'Loading'">
    <div class="loading-spinner"></div>
    <span v-if="label" class="spinner-label">{{ label }}</span>
  </div>
</template>

<script setup>
  defineProps({
    label: { type: String, default: '' },
  })
</script>

<style scoped>
  .loading-spinner-container {
    display: grid;
    gap: 0.85rem;
    align-items: center;
    justify-content: center;
    min-height: 9rem;
    padding: 1.8rem 1rem;
    text-align: center;
  }

  .loading-spinner {
    width: 42px;
    height: 42px;
    border: 3px solid color-mix(in srgb, var(--border) 82%, white 18%);
    border-top-color: var(--primary, #3b82f6);
    border-right-color: color-mix(in srgb, var(--secondary) 46%, transparent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    box-shadow: 0 0 0 6px color-mix(in srgb, var(--primary) 8%, transparent);
    margin: 0 auto;
  }

  .spinner-label {
    color: var(--text-muted, #64748b);
    font-size: 0.88rem;
    max-width: 28ch;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
