<script setup lang="ts">
  defineProps<{
    /** Field label text */
    label: string
    /** Span multiple grid columns */
    span?: number
  }>()
</script>

<template>
  <label class="field-inline filter-field" :style="span ? { gridColumn: `span ${span}` } : undefined">
    <span>{{ label }}</span>
    <slot />
  </label>
</template>

<style scoped>
  .filter-field {
    min-width: 0;
  }

  .filter-field :deep(.p-inputtext),
  .filter-field :deep(.p-select),
  .filter-field :deep(.p-autocomplete),
  .filter-field :deep(.p-inputnumber),
  .filter-field :deep(.p-textarea) {
    width: 100%;
  }
</style>
