<script setup>
  import MapView from '~/legacy/views/MapView.vue'

  definePageMeta({ middleware: ['auth'] })
</script>

<template>
  <ClientOnly>
    <MapView />
  </ClientOnly>
</template>
