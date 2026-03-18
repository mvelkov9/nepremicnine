<script setup>
  import { computed } from 'vue'
  import { RouterView, useRoute } from 'vue-router'
  import AppLoader from './components/AppLoader.vue'
  import AppLayout from './components/AppLayout.vue'
  import ConfirmDialogHost from './components/ConfirmDialogHost.vue'
  import ToastContainer from './components/ToastContainer.vue'
  import { useAuthStore } from './stores/auth'
  import { useUiStore } from './stores/ui'

  const auth = useAuthStore()
  const ui = useUiStore()
  const route = useRoute()
  const showBootLoader = computed(() => !auth.initialized || ui.isBootstrapping)
  const showRouteLoader = computed(() => auth.initialized && ui.isNavigating)

  void auth.init()
</script>

<template>
  <div class="app-root">
    <template v-if="auth.initialized">
      <AppLayout v-if="route.meta.requiresAuth && auth.isAuthenticated">
        <RouterView />
      </AppLayout>
      <RouterView v-else />
    </template>

    <AppLoader :visible="showBootLoader" :label="$t('common.loading')" mode="fullscreen" />
    <AppLoader :visible="showRouteLoader" :label="$t('common.loading')" mode="overlay" />
    <ConfirmDialogHost />
    <ToastContainer />
  </div>
</template>
