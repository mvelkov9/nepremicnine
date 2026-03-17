<script setup>
  import ModelView from '~/legacy/views/ModelView.vue'

  definePageMeta({ middleware: ['admin'] })
</script>

<template>
  <ClientOnly>
    <ModelView />
  </ClientOnly>
</template>
