<script setup>
  import DashboardView from '~/legacy/views/DashboardView.vue'

  definePageMeta({ middleware: ['auth'] })
</script>

<template>
  <ClientOnly>
    <DashboardView />
  </ClientOnly>
</template>
