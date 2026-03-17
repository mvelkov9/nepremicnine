<script setup>
  import AdminView from '~/legacy/views/AdminView.vue'

  definePageMeta({ middleware: ['admin'] })
</script>

<template>
  <ClientOnly>
    <AdminView />
  </ClientOnly>
</template>
