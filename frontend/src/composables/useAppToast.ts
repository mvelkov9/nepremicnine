import { useToast as usePrimeToast } from 'primevue/usetoast'

export type ToastSeverity = 'info' | 'success' | 'warn' | 'error'

const severityMap: Record<string, ToastSeverity> = {
  info: 'info',
  success: 'success',
  warning: 'warn',
  error: 'error',
}

export function useAppToast() {
  const toast = usePrimeToast()

  function showToast(message: string, type: string = 'info', life = 4000): void {
    toast.add({
      severity: severityMap[type] ?? 'info',
      summary: type.charAt(0).toUpperCase() + type.slice(1),
      detail: message,
      life,
    })
  }

  return { showToast }
}
