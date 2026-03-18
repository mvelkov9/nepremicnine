export function portalSearchUrl(
  municipality: string | null | undefined,
  propertyType: string | null | undefined,
): string {
  const base = 'https://www.nepremicnine.net'
  if (!municipality && !propertyType) return base

  const parts: string[] = []
  if (propertyType === 'stanovanje') parts.push('stanovanja')
  else if (propertyType === 'hisa') parts.push('hise')
  else parts.push('nepremicnine')

  if (municipality) {
    const slug = municipality
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '')
    parts.push(slug)
  }

  return `${base}/${parts.join('/')}/`
}
