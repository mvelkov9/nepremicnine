<script setup lang="ts">
  import { computed, onMounted, watch } from 'vue'
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
  const primeToast = usePrimeToast()
  const { pending } = usePendingToasts()

  const ready = computed(() => auth.isReady)
  const shouldBlockForBoot = computed(
    () => !ready.value && (auth.hasToken || Boolean(route.meta.requiresAuth)),
  )
  const skipTarget = computed(() =>
    route.meta.requiresAuth && auth.isAuthenticated ? '#main-content' : '#guest-main-content',
  )

  const severityMap: Record<ToastType, string> = {
    info: 'info',
    success: 'success',
    warning: 'warn',
    error: 'error',
  }

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

  onMounted(() => {
    void auth.init()
  })
</script>

<template>
  <a :href="skipTarget" class="skip-link">{{ $t('a11y.skipToContent') }}</a>
  <div aria-live="polite" aria-atomic="true" class="sr-only">{{ ui.routeTitle }}</div>
  <FullPageSpinner :show="shouldBlockForBoot || ui.routeTransitioning" />
  <div v-if="shouldBlockForBoot" class="app-boot-overlay">
    <LoadingSpinner />
  </div>
  <template v-else-if="ready || !route.meta.requiresAuth">
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
