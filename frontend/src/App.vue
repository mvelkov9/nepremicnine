<script setup>
  import { onMounted, ref } from 'vue'
  import { RouterView, useRoute } from 'vue-router'
  import AppLayout from './components/AppLayout.vue'
  import ToastContainer from './components/ToastContainer.vue'
  import { useAuthStore } from './stores/auth'

  const auth = useAuthStore()
  const route = useRoute()
  const ready = ref(false)

  onMounted(async () => {
    await auth.init()
    ready.value = true
  })
</script>

<template>
  <div v-if="!ready" class="login-page">
    <p>{{ $t('common.loading') }}</p>
  </div>
  <template v-else>
    <AppLayout v-if="route.meta.requiresAuth && auth.isAuthenticated">
      <RouterView />
    </AppLayout>
    <RouterView v-else />
  </template>
  <ToastContainer />
</template>
