<script setup lang="ts">
  import { onMounted, ref } from 'vue'
  import { RouterView, useRoute } from 'vue-router'
  import AppLayout from './components/AppLayout.vue'
  import ToastContainer from './components/ToastContainer.vue'
  import LoadingSpinner from './components/LoadingSpinner.vue'
  import FullPageSpinner from './components/FullPageSpinner.vue'
  import { useAuthStore } from './stores/auth'
  import { useUiStore } from './stores/ui'

  const auth = useAuthStore()
  const route = useRoute()
  const ui = useUiStore()
  const ready = ref(false)

  onMounted(async () => {
    await auth.init()
    ready.value = true
  })
</script>

<template>
  <a href="#main-content" class="skip-link">{{ $t('a11y.skipToContent') }}</a>
  <div aria-live="polite" aria-atomic="true" class="sr-only">{{ ui.routeTitle }}</div>
  <FullPageSpinner :show="!ready || ui.routeTransitioning" />
  <div v-if="!ready" class="app-boot-overlay">
    <LoadingSpinner />
  </div>
  <template v-else>
    <AppLayout v-if="route.meta.requiresAuth && auth.isAuthenticated">
      <RouterView v-slot="{ Component }">
        <Transition name="page-fade" mode="out-in">
          <component :is="Component" :key="route.path" />
        </Transition>
      </RouterView>
    </AppLayout>
    <RouterView v-else v-slot="{ Component }">
      <Transition name="page-fade" mode="out-in">
        <component :is="Component" :key="route.path" />
      </Transition>
    </RouterView>
  </template>
  <ToastContainer />
</template>
