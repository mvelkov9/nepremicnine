<script setup>
  const props = defineProps({
    modelValue: { type: [String, Number, Boolean, null], default: null },
    options: { type: Array, default: () => [] },
    optionLabel: { type: String, default: 'label' },
    optionValue: { type: String, default: 'value' },
    allowEmpty: { type: Boolean, default: true },
  })

  const emit = defineEmits(['update:modelValue'])

  function getLabel(option) {
    return typeof option === 'object' ? (option?.[props.optionLabel] ?? '') : option
  }

  function getValue(option) {
    return typeof option === 'object' ? (option?.[props.optionValue] ?? getLabel(option)) : option
  }

  function selectOption(option) {
    const value = getValue(option)
    if (props.allowEmpty && props.modelValue === value) {
      emit('update:modelValue', null)
      return
    }
    emit('update:modelValue', value)
  }
</script>

<template>
  <div class="p-selectbutton flex flex-wrap gap-2">
    <button
      v-for="option in options"
      :key="`${getValue(option)}`"
      type="button"
      class="p-togglebutton rounded-full border text-sm font-medium transition focus:outline-none"
      :class="
        modelValue === getValue(option)
          ? 'p-togglebutton-checked border-[var(--ui-primary)] text-[var(--ui-text-inverted)]'
          : 'border-[var(--ui-border)] bg-[var(--surface-strong)] text-[var(--ui-text-muted)]'
      "
      :aria-pressed="modelValue === getValue(option) ? 'true' : 'false'"
      @click="selectOption(option)"
    >
      <span class="p-togglebutton-content">
        {{ getLabel(option) }}
      </span>
    </button>
  </div>
</template>

<style scoped>
  .p-togglebutton {
    position: relative;
    overflow: hidden;
    box-shadow: 0 10px 22px rgb(15 23 42 / 5%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease,
      background 160ms ease,
      color 160ms ease;
  }

  .p-togglebutton:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--ui-primary) 26%, var(--ui-border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 16px 30px rgb(15 23 42 / 10%);
  }

  .p-togglebutton:active {
    transform: translateY(0) scale(0.985);
  }

  .p-togglebutton:focus-visible {
    box-shadow:
      0 0 0 4px color-mix(in srgb, var(--ui-primary) 18%, transparent),
      0 16px 30px rgb(15 23 42 / 10%);
  }

  .p-togglebutton-checked {
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--ui-primary) 94%, black 4%),
      color-mix(in srgb, var(--ui-secondary) 14%, var(--ui-primary) 86%)
    );
    box-shadow: 0 18px 34px rgb(15 23 42 / 15%);
  }
</style>
