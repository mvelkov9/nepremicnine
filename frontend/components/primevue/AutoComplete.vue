<script setup>
  defineOptions({ inheritAttrs: false })

  const attrs = useAttrs()
  const props = defineProps({
    modelValue: { type: [String, Number], default: '' },
    suggestions: { type: Array, default: () => [] },
    placeholder: { type: String, default: '' },
    dropdown: { type: Boolean, default: false },
    invalid: { type: Boolean, default: false },
  })

  const emit = defineEmits(['update:modelValue', 'complete'])
  const datalistId = `autocomplete-${useId()}`
  const inputClass = computed(() => attrs['input-class'] || attrs.inputClass)
  const wrapperClass = computed(() => attrs.class)
  const forwardedAttrs = computed(() => {
    const clone = { ...attrs }
    delete clone.class
    delete clone.inputClass
    delete clone['input-class']
    return clone
  })

  function itemLabel(item) {
    if (typeof item === 'object') return item?.label ?? item?.value ?? ''
    return item
  }

  function handleInput(event) {
    const value = event.target.value
    emit('update:modelValue', value)
    emit('complete', { query: value })
  }
</script>

<template>
  <div class="autocomplete-shell relative w-full" :class="wrapperClass">
    <input
      v-bind="forwardedAttrs"
      :value="modelValue"
      :placeholder="placeholder"
      :list="datalistId"
      class="control-field"
      :class="[invalid ? 'control-invalid' : '', inputClass]"
      @input="handleInput"
      @focus="emit('complete', { query: modelValue || '' })"
    />
    <button
      v-if="dropdown"
      type="button"
      class="autocomplete-trigger absolute right-3 top-1/2 -translate-y-1/2 rounded-full px-2 py-1 text-xs"
      @click="emit('complete', { query: modelValue || '' })"
    >
      ▼
    </button>
    <datalist :id="datalistId">
      <option v-for="item in suggestions" :key="itemLabel(item)" :value="itemLabel(item)" />
    </datalist>
  </div>
</template>

<style scoped>
  .control-field {
    width: 100%;
    min-height: 2.9rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--ui-border) 92%, transparent);
    background: var(--surface-strong);
    color: var(--ui-text);
    padding: 0.8rem 1rem;
    outline: none;
    box-shadow: 0 10px 18px rgb(15 23 42 / 5%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease,
      background 160ms ease;
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

  .control-invalid {
    border-color: color-mix(in srgb, var(--ui-error) 48%, var(--ui-border));
  }

  .autocomplete-trigger {
    border: 1px solid transparent;
    background: color-mix(in srgb, var(--ui-primary) 8%, transparent);
    color: var(--ui-text-muted);
    font-weight: 800;
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      background 160ms ease,
      color 160ms ease;
  }

  .autocomplete-trigger:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--ui-primary) 24%, transparent);
    background: color-mix(in srgb, var(--ui-primary) 14%, transparent);
    color: var(--ui-primary);
  }
</style>
