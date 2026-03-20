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
    display: grid;
    gap: 0.85rem;
    align-items: center;
    justify-content: center;
    min-height: 10rem;
    padding: 1.7rem 1.1rem;
    text-align: center;
    border-radius: 1.4rem;
    border: 1px dashed color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(180deg, var(--glass-highlight), transparent 42%),
      color-mix(in srgb, var(--surface-panel-muted, var(--surface-soft)) 92%, var(--primary) 8%);
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }

  .empty-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 4rem;
    height: 4rem;
    margin: 0 auto;
    font-size: 2.35rem;
    line-height: 1;
    border-radius: 1.2rem;
    background: color-mix(in srgb, var(--surface-strong) 84%, white 16%);
    border: 1px solid color-mix(in srgb, var(--border) 74%, var(--primary) 26%);
  }

  .empty-message {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.92rem;
    max-width: 32ch;
  }
</style>
