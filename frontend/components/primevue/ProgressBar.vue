<script setup>
  const props = defineProps({
    value: { type: Number, default: 0 },
    showValue: { type: Boolean, default: true },
  })
</script>

<template>
  <div class="progress-shell space-y-2">
    <div class="progress-track h-2 overflow-hidden rounded-full">
      <div
        class="progress-fill h-full rounded-full transition-all"
        :style="{ width: `${Math.max(0, Math.min(100, value))}%` }"
      ></div>
    </div>
    <div v-if="showValue" class="text-xs text-[var(--ui-text-muted)]">{{ Math.round(value) }}%</div>
  </div>
</template>

<style scoped>
  .progress-track {
    background:
      linear-gradient(
        145deg,
        color-mix(in srgb, var(--ui-bg-muted) 90%, transparent),
        color-mix(in srgb, var(--ui-bg) 72%, transparent)
      );
    box-shadow: inset 0 1px 2px rgb(15 23 42 / 14%);
  }

  .progress-fill {
    background:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--ui-primary) 86%, white 6%),
        color-mix(in srgb, var(--ui-secondary) 18%, var(--ui-primary) 82%)
      );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 18%),
      0 0 18px color-mix(in srgb, var(--ui-primary) 18%, transparent);
  }
</style>
