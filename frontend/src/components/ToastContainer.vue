<script setup>
  import { onBeforeUnmount } from 'vue'
  import Toast from 'primevue/toast'
  import { useToast as usePrimeToast } from 'primevue/usetoast'
  import { registerToastService } from '../composables/useToast'

  const toast = usePrimeToast()
  registerToastService(toast)

  onBeforeUnmount(() => {
    registerToastService(null)
  })
</script>

<template>
  <Toast group="app" position="bottom-right" />
</template>
