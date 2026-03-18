import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  const routeTransitioning = ref(false)
  const routeTitle = ref('')

  return { routeTransitioning, routeTitle }
})
