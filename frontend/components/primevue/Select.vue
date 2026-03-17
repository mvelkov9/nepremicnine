<script setup>
  defineOptions({ inheritAttrs: false })

  const attrs = useAttrs()
  const props = defineProps({
    modelValue: { type: [String, Number, Boolean, Object, null], default: null },
    options: { type: Array, default: () => [] },
    optionLabel: { type: String, default: 'label' },
    optionValue: { type: String, default: 'value' },
    placeholder: { type: String, default: '' },
    invalid: { type: Boolean, default: false },
  })

  const emit = defineEmits(['update:modelValue'])

  const inputClass = computed(() => attrs['input-class'] || attrs.inputClass)
  const wrapperClass = computed(() => attrs.class)
  const forwardedAttrs = computed(() => {
    const clone = { ...attrs }
    delete clone.class
    delete clone.inputClass
    delete clone['input-class']
    return clone
  })

  function renderOptionLabel(item) {
    return typeof item === 'object' ? item?.[props.optionLabel] ?? '' : item
  }

  function renderOptionValue(item) {
    return typeof item === 'object' ? item?.[props.optionValue] ?? renderOptionLabel(item) : item
  }
</script>

<template>
  <div class="select-shell" :class="wrapperClass">
    <select
      v-bind="forwardedAttrs"
      class="control-field select-field"
      :class="[props.invalid ? 'control-invalid' : '', inputClass]"
      :value="modelValue ?? ''"
      @change="emit('update:modelValue', $event.target.value)"
    >
      <option v-if="placeholder" value="">{{ placeholder }}</option>
      <option
        v-for="option in options"
        :key="`${renderOptionValue(option)}`"
        :value="renderOptionValue(option)"
      >
        {{ renderOptionLabel(option) }}
      </option>
    </select>

    <span class="select-caret" aria-hidden="true">▾</span>
  </div>
</template>

<style scoped>
  .select-shell {
    position: relative;
    width: 100%;
  }

  .control-field {
    width: 100%;
    min-height: 2.9rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--ui-border) 92%, transparent);
    background: var(--surface-strong);
    color: var(--ui-text);
    padding: 0.8rem 1rem;
    outline: none;
    appearance: none;
    box-shadow: 0 10px 18px rgb(15 23 42 / 5%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease,
      background 160ms ease;
  }

  .select-field {
    padding-right: 2.9rem;
  }

  .control-field:hover {
    border-color: color-mix(in srgb, var(--ui-primary) 24%, var(--ui-border));
    background: color-mix(in srgb, var(--surface-strong) 94%, var(--surface-muted) 6%);
    box-shadow: 0 14px 24px rgb(15 23 42 / 8%);
  }

  .control-field:focus {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--ui-primary) 42%, var(--ui-border));
    box-shadow:
      0 0 0 4px color-mix(in srgb, var(--ui-primary) 14%, transparent),
      0 18px 32px rgb(15 23 42 / 12%);
  }

  .control-field option {
    background: var(--surface-strong);
    color: var(--ui-text);
  }

  .control-field option:checked {
    background: color-mix(in srgb, var(--ui-primary) 18%, var(--surface-strong));
    color: var(--ui-text);
  }

  .control-invalid {
    border-color: color-mix(in srgb, var(--ui-error) 48%, var(--ui-border));
  }

  .select-caret {
    pointer-events: none;
    position: absolute;
    right: 1rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--ui-text-muted);
    font-size: 0.8rem;
    font-weight: 800;
  }
</style>
