const SEVERITY_MAP = {
  info: 'info',
  success: 'success',
  warning: 'warn',
  error: 'error',
}

let toastService = null

export function registerToastService(service) {
  toastService = service
}

function showToast(message, type = 'info', duration = 4000, options = {}) {
  if (!toastService || !message) {
    return
  }

  toastService.add({
    group: options.group || 'app',
    severity: SEVERITY_MAP[type] || 'info',
    summary: options.summary,
    detail: message,
    life: duration,
  })
}

export function useToast() {
  return { showToast }
}
