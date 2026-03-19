<script setup lang="ts">
  import { onMounted, ref, watch } from 'vue'
  import { RouterView, useRoute } from 'vue-router'
  import { useToast as usePrimeToast } from 'primevue/usetoast'
  import AppLayout from './components/AppLayout.vue'
  import LoadingSpinner from './components/LoadingSpinner.vue'
  import FullPageSpinner from './components/FullPageSpinner.vue'
  import { useAuthStore } from './stores/auth'
  import { useUiStore } from './stores/ui'
  import { usePendingToasts, type ToastType } from './composables/useToast'

  const auth = useAuthStore()
  const route = useRoute()
  const ui = useUiStore()
  const ready = ref(false)
  const primeToast = usePrimeToast()
  const { pending } = usePendingToasts()

  const severityMap: Record<ToastType, string> = {
    info: 'info',
    success: 'success',
    warning: 'warn',
    error: 'error',
  }

  // Bridge module-level toast queue → PrimeVue Toast
  watch(
    pending,
    (items) => {
      while (items.length) {
        const item = items.shift()!
        primeToast.add({
          severity: severityMap[item.type] ?? 'info',
          detail: item.message,
          life: item.life,
        })
      }
    },
    { deep: true },
  )

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
  <Toast />
  <ConfirmDialog />
</template>
