<script setup>
  const props = defineProps({
    modelValue: { type: [Boolean, Number, String], default: false },
    trueValue: { type: [Boolean, Number, String], default: true },
    falseValue: { type: [Boolean, Number, String], default: false },
  })

  const emit = defineEmits(['update:modelValue'])

  const checked = computed(() => props.modelValue === props.trueValue)

  function toggle() {
    emit('update:modelValue', checked.value ? props.falseValue : props.trueValue)
  }
</script>

<template>
  <button
    type="button"
    class="p-toggleswitch relative inline-flex h-7 w-12 items-center rounded-full transition focus:outline-none"
    :class="checked ? 'p-toggleswitch-checked' : ''"
    :aria-pressed="checked ? 'true' : 'false'"
    @click="toggle"
  >
    <span class="p-toggleswitch-slider">
      <span
        class="p-toggleswitch-handle transition"
        :class="checked ? 'translate-x-5' : 'translate-x-0'"
      ></span>
    </span>
  </button>
</template>

<style scoped>
  .p-toggleswitch {
    border: 1px solid color-mix(in srgb, var(--ui-border) 88%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--ui-bg-elevated) 92%, transparent),
      color-mix(in srgb, var(--ui-bg) 76%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 10px 18px rgb(15 23 42 / 8%);
    transition:
      transform 160ms ease,
      box-shadow 160ms ease,
      border-color 160ms ease,
      background 160ms ease;
  }

  .p-toggleswitch:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--ui-primary) 26%, var(--ui-border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 14px 24px rgb(15 23 42 / 12%);
  }

  .p-toggleswitch:active {
    transform: translateY(0) scale(0.97);
  }

  .p-toggleswitch:focus-visible {
    box-shadow:
      0 0 0 4px color-mix(in srgb, var(--ui-primary) 18%, transparent),
      0 14px 24px rgb(15 23 42 / 12%);
  }

  .p-toggleswitch-slider {
    transition:
      background 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease;
  }

  .p-toggleswitch-checked .p-toggleswitch-slider {
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--ui-primary) 68%, var(--ui-bg-elevated) 32%),
      color-mix(in srgb, var(--ui-secondary) 34%, var(--ui-primary) 66%)
    );
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 16%);
  }

  .p-toggleswitch-handle {
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--ui-bg-elevated) 96%, transparent),
      color-mix(in srgb, var(--ui-bg) 80%, transparent)
    );
    box-shadow: 0 8px 18px rgb(15 23 42 / 16%);
  }
</style>
