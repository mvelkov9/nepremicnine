<script setup>
  const props = defineProps({
    value: { type: String, default: '' },
    severity: { type: String, default: 'secondary' },
  })

  const toneClass = computed(() => {
    if (props.severity === 'success') return 'text-[var(--ui-success)]'
    if (props.severity === 'warn') return 'text-[var(--ui-warning)]'
    if (props.severity === 'danger') return 'text-[var(--ui-error)]'
    if (props.severity === 'contrast') return 'bg-[var(--ui-primary)]/10 text-[var(--ui-primary)]'
    return 'border-[var(--ui-border)] bg-[var(--ui-bg)] text-[var(--ui-text-muted)]'
  })

  const toneStyle = computed(() => {
    if (props.severity === 'success') {
      return {
        borderColor: 'color-mix(in srgb, var(--ui-success) 24%, transparent)',
        background: 'color-mix(in srgb, var(--ui-success) 10%, transparent)',
      }
    }

    if (props.severity === 'warn') {
      return {
        borderColor: 'color-mix(in srgb, var(--ui-warning) 24%, transparent)',
        background: 'color-mix(in srgb, var(--ui-warning) 10%, transparent)',
      }
    }

    if (props.severity === 'danger') {
      return {
        borderColor: 'color-mix(in srgb, var(--ui-error) 24%, transparent)',
        background: 'color-mix(in srgb, var(--ui-error) 10%, transparent)',
      }
    }

    return null
  })
</script>

<template>
  <span
    class="p-tag inline-flex rounded-full border px-3 py-1 text-xs font-semibold"
    :class="toneClass"
    :style="toneStyle"
  >
    <slot>{{ value }}</slot>
  </span>
</template>

<style scoped>
  .p-tag {
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 10px 18px rgb(15 23 42 / 6%);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
</style>
