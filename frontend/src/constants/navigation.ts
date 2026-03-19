export interface NavItem {
  to: string
  icon: string
  label: string
}

export const viewerNavigation: NavItem[] = [
  { to: '/', icon: 'dashboard', label: 'nav.dashboard' },
  { to: '/napoved', icon: 'prediction', label: 'nav.prediction' },
  { to: '/zemljevid', icon: 'map', label: 'nav.map' },
  { to: '/analiza', icon: 'analysis', label: 'nav.analysis' },
]

export const adminNavigation: NavItem[] = [
  { to: '/admin', icon: 'admin', label: 'nav.admin' },
  { to: '/admin/podatki', icon: 'data', label: 'nav.data' },
  { to: '/admin/priprava', icon: 'prepare', label: 'nav.prepare' },
  { to: '/admin/model', icon: 'model', label: 'nav.model' },
  { to: '/admin/diagnostika', icon: 'diagnostics', label: 'nav.diagnostics' },
  { to: '/admin/uporabniki', icon: 'admin', label: 'admin.userManagement' },
]
