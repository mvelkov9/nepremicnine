<script setup>
  import DiagnosticsView from '~/legacy/views/DiagnosticsView.vue'

  definePageMeta({ middleware: ['admin'] })
</script>

<template>
  <ClientOnly>
    <DiagnosticsView />
  </ClientOnly>
</template>
