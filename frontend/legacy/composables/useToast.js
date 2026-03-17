import { ref } from 'vue'

const toasts = ref([])
let nextId = 0

function showToast(message, type = 'info', duration = 4000) {
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
