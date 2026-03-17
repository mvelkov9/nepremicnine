<script setup>
  import PrepareView from '~/legacy/views/PrepareView.vue'

  definePageMeta({ middleware: ['admin'] })
</script>

<template>
  <ClientOnly>
    <PrepareView />
  </ClientOnly>
</template>
