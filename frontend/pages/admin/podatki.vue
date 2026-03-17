<script setup>
  import DataView from '~/legacy/views/DataView.vue'

  definePageMeta({ middleware: ['admin'] })
</script>

<template>
  <ClientOnly>
    <DataView />
  </ClientOnly>
</template>
