let confirmService = null

export function registerConfirmService(service) {
  confirmService = service
}

function confirmAction({
  message,
  header,
  icon = 'pi pi-exclamation-triangle',
  acceptLabel,
  rejectLabel,
  acceptSeverity = 'danger',
  group = 'app-confirm',
}) {
  if (!confirmService) {
    return Promise.resolve(false)
  }

  return new Promise((resolve) => {
    let settled = false

    const finish = (value) => {
      if (!settled) {
        settled = true
        resolve(value)
      }
    }

    confirmService.require({
      group,
      message,
      header,
      icon,
      accept: () => finish(true),
      reject: () => finish(false),
      onHide: () => finish(false),
      rejectProps: {
        label: rejectLabel,
        severity: 'secondary',
        outlined: true,
      },
      acceptProps: {
        label: acceptLabel,
        severity: acceptSeverity,
      },
    })
  })
}

export function useConfirmDialog() {
  return { confirmAction }
}