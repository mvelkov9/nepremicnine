<script setup>
  import { inject, onBeforeUnmount, onMounted, onUpdated } from 'vue'

  const props = defineProps({
    field: { type: String, default: '' },
    header: { type: String, default: '' },
  })

  const slots = useSlots()
  const register = inject('datatable-register-column', null)
  const update = inject('datatable-update-column', null)
  const unregister = inject('datatable-unregister-column', null)
  const id = Symbol('datatable-column')

  const column = { id, props, slots }

  onMounted(() => {
    register?.(column)
  })

  onUpdated(() => {
    update?.(column)
  })

  onBeforeUnmount(() => {
    unregister?.(id)
  })
</script>

<template>
  <div v-if="false"><slot /></div>
</template>
