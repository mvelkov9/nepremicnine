<script setup>
  defineOptions({ inheritAttrs: false })

  const attrs = useAttrs()
  const props = defineProps({
    modelValue: { type: [Number, String, null], default: null },
    min: { type: Number, default: undefined },
    max: { type: Number, default: undefined },
    step: { type: Number, default: undefined },
    suffix: { type: String, default: '' },
    prefix: { type: String, default: '' },
    invalid: { type: Boolean, default: false },
  })

  const emit = defineEmits(['update:modelValue'])

  const displayValue = computed(() => (props.modelValue ?? '') === '' ? '' : props.modelValue)
  const inputClass = computed(() => attrs['input-class'] || attrs.inputClass)
  const wrapperClass = computed(() => attrs.class)
  const forwardedAttrs = computed(() => {
    const clone = { ...attrs }
    delete clone.class
    delete clone.inputClass
    delete clone['input-class']
    return clone
  })

  function updateValue(event) {
    const raw = event.target.value
    if (raw === '') {
      emit('update:modelValue', null)
      return
    }
    emit('update:modelValue', Number(raw))
  }
</script>

<template>
  <div class="relative w-full" :class="wrapperClass">
    <span v-if="prefix" class="number-affix pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-sm">
      {{ prefix }}
    </span>
    <input
      v-bind="forwardedAttrs"
      :value="displayValue"
      type="number"
      class="control-field"
      :class="[
        invalid ? 'control-invalid' : '',
        prefix ? 'pl-8' : '',
        suffix ? 'pr-12' : '',
        inputClass,
      ]"
      :min="min"
      :max="max"
      :step="step"
      @input="updateValue"
    />
    <span v-if="suffix" class="number-affix pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-sm">
      {{ suffix }}
    </span>
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

  .control-invalid:hover,
  .control-invalid:focus {
    border-color: color-mix(in srgb, var(--ui-error) 54%, var(--ui-border));
    box-shadow:
      0 0 0 4px color-mix(in srgb, var(--ui-error) 12%, transparent),
      0 18px 32px rgb(15 23 42 / 12%);
  }

  .number-affix {
    color: var(--ui-text-muted);
    font-weight: 700;
  }
</style>
