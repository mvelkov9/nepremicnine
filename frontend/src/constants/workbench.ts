import type { LocationQueryRaw, LocationQueryValueRaw } from 'vue-router'

export const workspacePagePathMap: Record<string, string> = {
  dashboard: '/',
  market: '/trg',
  regions: '/regije',
  municipalities: '/obcine',
  municipality: '/obcine',
  map: '/zemljevid',
  prediction: '/napoved',
  analysis: '/analiza',
  benchmark: '/dokaz',
  'admin-home': '/admin',
  data: '/admin/podatki',
  prepare: '/admin/priprava',
  model: '/admin/model',
  diagnostics: '/admin/diagnostika',
  'admin-benchmark': '/admin/dokaz',
  users: '/admin/uporabniki',
}

export const workspacePageTitleKeys: Record<string, string> = {
  dashboard: 'nav.dashboard',
  market: 'nav.market',
  regions: 'nav.regions',
  municipalities: 'nav.municipalities',
  municipality: 'municipality.pageTitle',
  map: 'nav.map',
  prediction: 'nav.prediction',
  analysis: 'nav.analysis',
  benchmark: 'nav.benchmark',
  'admin-home': 'nav.admin',
  data: 'nav.data',
  prepare: 'nav.prepare',
  model: 'nav.model',
  diagnostics: 'nav.diagnostics',
  'admin-benchmark': 'nav.benchmark',
  users: 'admin.userManagement',
}

export function toLocationQuery(filters: Record<string, unknown> = {}): LocationQueryRaw {
  const query: LocationQueryRaw = {}
  for (const [key, value] of Object.entries(filters)) {
    if (key === 'slug' || value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      query[key] = value
        .filter((item) => item !== undefined && item !== null && item !== '')
        .map((item) => String(item)) as LocationQueryValueRaw[]
      continue
    }
    query[key] = String(value)
  }
  return query
}

export function toQueryString(filters: Record<string, unknown> = {}) {
  const params = new URLSearchParams()
  const query = toLocationQuery(filters)

  for (const [key, value] of Object.entries(query).sort(([left], [right]) =>
    left.localeCompare(right),
  )) {
    if (Array.isArray(value)) {
      for (const entry of [...value].map(String).sort()) {
        params.append(key, entry)
      }
      continue
    }

    if (value != null) {
      params.append(key, String(value))
    }
  }

  return params.toString()
}

export function describeRoute(path: string, filters: Record<string, unknown> = {}) {
  const queryString = toQueryString(filters)
  return queryString ? `${path}?${queryString}` : path
}

export function buildWorkspaceRoute(page: string, filters: Record<string, unknown> = {}) {
  const query = toLocationQuery(filters)
  const path =
    page === 'municipality' && typeof filters.slug === 'string'
      ? `/obcine/${filters.slug}`
      : workspacePagePathMap[page] || '/'
  return { path, query }
}
