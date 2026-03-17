<script setup>
  import PredictionView from '~/legacy/views/PredictionView.vue'

  definePageMeta({ middleware: ['auth'] })
</script>

<template>
  <ClientOnly>
    <PredictionView />
  </ClientOnly>
</template>
