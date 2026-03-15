<template>
  <div class="empty-state" role="status">
    <span class="empty-icon">{{ icon }}</span>
    <p class="empty-message">{{ message }}</p>
  </div>
</template>

<script setup>
  defineProps({
    icon: { type: String, default: '📭' },
    message: { type: String, required: true },
  })
</script>

<style scoped>
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem 1rem;
    text-align: center;
  }

  .empty-icon {
    font-size: 2.5rem;
    margin-bottom: 0.75rem;
  }

  .empty-message {
    color: var(--text-muted);
    font-size: 0.9rem;
  }
</style>
