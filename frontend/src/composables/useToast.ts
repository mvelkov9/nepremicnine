import { ref } from 'vue'

export type ToastType = 'info' | 'success' | 'warning' | 'error'

interface Toast {
  id: number
  message: string
  type: ToastType
}

const toasts = ref<Toast[]>([])
let nextId = 0

function showToast(message: string, type: ToastType = 'info', duration = 4000): void {
  const id = nextId++
  toasts.value.push({ id, message, type })
  if (duration > 0) {
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, duration)
  }
}

export function useToast() {
  return { toasts, showToast }
}
