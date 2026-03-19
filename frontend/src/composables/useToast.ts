import { ref } from 'vue'

export type ToastType = 'info' | 'success' | 'warning' | 'error'

interface ToastEvent {
  id: number
  message: string
  type: ToastType
  life: number
}

const pending = ref<ToastEvent[]>([])
let nextId = 0

/**
 * Queue a toast message. Works from any context (component setup, interceptors, etc.).
 * App.vue bridges these to PrimeVue Toast for rendering.
 */
function showToast(message: string, type: ToastType = 'info', life = 4000): void {
  pending.value.push({ id: nextId++, message, type, life })
}

/** Used by App.vue to drain queued toasts into PrimeVue Toast. */
export function usePendingToasts() {
  return { pending }
}

/** Backward-compatible composable for use anywhere. */
export function useToast() {
  return { showToast }
}
