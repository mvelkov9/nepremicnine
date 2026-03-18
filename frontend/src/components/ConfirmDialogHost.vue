<script setup>
  import { onBeforeUnmount } from 'vue'
  import ConfirmDialog from 'primevue/confirmdialog'
  import { useConfirm } from 'primevue/useconfirm'
  import { registerConfirmService } from '../composables/useConfirmDialog'

  const confirm = useConfirm()
  registerConfirmService(confirm)

  onBeforeUnmount(() => {
    registerConfirmService(null)
  })
</script>

<template>
  <ConfirmDialog group="app-confirm" />
</template>