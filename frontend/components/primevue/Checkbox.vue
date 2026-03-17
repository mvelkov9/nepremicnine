<script setup>
  const props = defineProps({
    modelValue: { type: [Boolean, Array], default: false },
    binary: { type: Boolean, default: false },
    value: { type: [String, Number, Boolean, Object], default: true },
  })

  const emit = defineEmits(['update:modelValue'])

  const checked = computed(() => {
    if (props.binary) return !!props.modelValue
    return Array.isArray(props.modelValue) && props.modelValue.includes(props.value)
  })

  function updateValue(event) {
    if (props.binary) {
      emit('update:modelValue', event.target.checked)
      return
    }

    const next = Array.isArray(props.modelValue) ? [...props.modelValue] : []
    const index = next.findIndex((item) => item === props.value)
    if (event.target.checked && index === -1) next.push(props.value)
    if (!event.target.checked && index >= 0) next.splice(index, 1)
    emit('update:modelValue', next)
  }
</script>

<template>
  <input
    type="checkbox"
    class="h-4 w-4 rounded border-[var(--ui-border)] text-[var(--ui-primary)] focus:ring-[var(--ui-primary)]"
    :checked="checked"
    @change="updateValue"
  />
</template>
