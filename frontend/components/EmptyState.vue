<script setup lang="ts">
  defineProps<{
    icon?: string
    title: string
    description?: string
  }>()
</script>

<template>
  <div class="empty-state">
    <div v-if="icon" class="empty-icon">
      <UIcon :name="icon" class="size-8" />
    </div>
    <p class="empty-title">{{ title }}</p>
    <p v-if="description" class="empty-desc muted">{{ description }}</p>
    <slot />
  </div>
</template>

<style scoped>
  .empty-state {
    display: grid;
    gap: 0.5rem;
    justify-items: center;
    text-align: center;
    padding: 2.5rem 1.5rem;
  }

  .empty-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 3.5rem;
    height: 3.5rem;
    border-radius: 1.25rem;
    border: 1px solid var(--border);
    background: var(--surface-muted);
    color: var(--text-muted);
    margin-bottom: 0.5rem;
  }

  .empty-title {
    margin: 0;
    font-weight: 700;
    font-size: 1rem;
  }

  .empty-desc {
    margin: 0;
    max-width: 40ch;
    font-size: 0.88rem;
    line-height: 1.5;
  }
</style>
