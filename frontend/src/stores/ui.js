import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', () => {
  const bootstrapPendingCount = ref(0)
  const navigationPendingCount = ref(0)

  const isBootstrapping = computed(() => bootstrapPendingCount.value > 0)
  const isNavigating = computed(() => navigationPendingCount.value > 0)
  const isBusy = computed(() => isBootstrapping.value || isNavigating.value)

  function beginBootstrapping() {
    bootstrapPendingCount.value += 1
  }

  function endBootstrapping() {
    bootstrapPendingCount.value = Math.max(bootstrapPendingCount.value - 1, 0)
  }

  function beginNavigation() {
    navigationPendingCount.value += 1
  }

  function endNavigation() {
    navigationPendingCount.value = Math.max(navigationPendingCount.value - 1, 0)
  }

  return {
    isBootstrapping,
    isNavigating,
    isBusy,
    beginBootstrapping,
    endBootstrapping,
    beginNavigation,
    endNavigation,
  }
})
