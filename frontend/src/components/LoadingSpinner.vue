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
    padding: 2rem 1rem;
    gap: 0.75rem;
  }

  .loading-spinner {
    width: 36px;
    height: 36px;
    border: 3px solid var(--border, #e2e8f0);
    border-top-color: var(--primary, #3b82f6);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  .spinner-label {
    color: var(--text-muted, #64748b);
    font-size: 0.875rem;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
