<script setup>
  import AdminHomeView from '~/legacy/views/AdminHomeView.vue'

  definePageMeta({ middleware: ['admin'] })
</script>

<template>
  <ClientOnly>
    <AdminHomeView />
  </ClientOnly>
</template>
