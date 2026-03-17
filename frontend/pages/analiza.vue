<script setup>
  import AnalysisView from '~/legacy/views/AnalysisView.vue'

  definePageMeta({ middleware: ['auth'] })
</script>

<template>
  <ClientOnly>
    <AnalysisView />
  </ClientOnly>
</template>
