<script setup lang="ts">
  defineProps<{
    label: string
    value: string | number
    meta?: string
    icon?: string
    colorClass?: string
  }>()
</script>

<template>
  <article class="kpi-card" :class="colorClass">
    <div v-if="icon" class="kpi-icon-row">
      <span class="kpi-icon">
        <UIcon :name="icon" class="w-4 h-4" />
      </span>
      <span class="kpi-label">{{ label }}</span>
    </div>
    <span v-else class="kpi-label">{{ label }}</span>
    <strong class="kpi-value">{{ value }}</strong>
    <small v-if="meta" class="muted kpi-meta">{{ meta }}</small>
  </article>
</template>

<style scoped>
  .kpi-icon-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.25rem;
  }

  .kpi-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 0.75rem;
    border: 1px solid color-mix(in srgb, var(--border) 88%, transparent);
    background: color-mix(in srgb, var(--surface-muted) 82%, transparent);
    color: var(--primary);
  }

  .kpi-meta {
    font-size: 0.82rem;
  }
</style>
