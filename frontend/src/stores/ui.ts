import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  const routeTransitioning = ref(false)
  const routeTitle = ref('')
  const commandPaletteOpen = ref(false)
  const activityCenterOpen = ref(false)
  const workspaceTrayOpen = ref(false)

  function toggleCommandPalette(force?: boolean) {
    commandPaletteOpen.value = typeof force === 'boolean' ? force : !commandPaletteOpen.value
  }

  function toggleActivityCenter(force?: boolean) {
    activityCenterOpen.value = typeof force === 'boolean' ? force : !activityCenterOpen.value
  }

  function toggleWorkspaceTray(force?: boolean) {
    workspaceTrayOpen.value = typeof force === 'boolean' ? force : !workspaceTrayOpen.value
  }

  return {
    routeTransitioning,
    routeTitle,
    commandPaletteOpen,
    activityCenterOpen,
    workspaceTrayOpen,
    toggleCommandPalette,
    toggleActivityCenter,
    toggleWorkspaceTray,
  }
})
