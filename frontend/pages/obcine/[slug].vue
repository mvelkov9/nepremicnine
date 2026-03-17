<script setup>
  import MunicipalityView from '~/legacy/views/MunicipalityView.vue'

  definePageMeta({ middleware: ['auth'] })
</script>

<template>
  <ClientOnly>
    <MunicipalityView />
  </ClientOnly>
</template>
