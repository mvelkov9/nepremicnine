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
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2.4rem 1rem;
    gap: 0.9rem;
  }

  .loading-spinner {
    width: 42px;
    height: 42px;
    border: 3px solid color-mix(in srgb, var(--ui-border, rgb(148 163 184 / 30%)) 72%, transparent);
    border-top-color: var(--ui-primary, currentColor);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    box-shadow: 0 0 0 8px color-mix(in srgb, var(--ui-primary, currentColor) 8%, transparent);
  }

  .spinner-label {
    color: var(--ui-text-muted, currentColor);
    font-size: 0.9rem;
    font-weight: 600;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
