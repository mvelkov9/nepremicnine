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
    gap: 0.9rem;
    padding: 3rem 1.4rem;
    text-align: center;
    border: 1px dashed color-mix(in srgb, var(--ui-border) 88%, transparent);
    border-radius: 1.75rem;
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--ui-bg-elevated) 90%, transparent),
      color-mix(in srgb, var(--ui-bg) 72%, transparent)
    );
  }

  .empty-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 3.2rem;
    height: 3.2rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--ui-primary) 12%, transparent);
    color: var(--ui-primary);
    font-size: 1.45rem;
  }

  .empty-message {
    margin: 0;
    color: var(--ui-text-muted);
    font-size: 0.92rem;
    line-height: 1.7;
    max-width: 36ch;
  }
</style>
