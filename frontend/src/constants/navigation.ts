export interface NavItem {
  to: string
  icon: string
  label: string
  group?: string
}

export const viewerNavigation: NavItem[] = [
  { to: '/', icon: 'dashboard', label: 'nav.dashboard', group: 'nav.groupOverview' },
  { to: '/trg', icon: 'market', label: 'nav.market', group: 'nav.groupOverview' },
  { to: '/regije', icon: 'regions', label: 'nav.regions', group: 'nav.groupOverview' },
  { to: '/zemljevid', icon: 'map', label: 'nav.map', group: 'nav.groupExplore' },
  { to: '/obcine', icon: 'municipalities', label: 'nav.municipalities', group: 'nav.groupExplore' },
  { to: '/napoved', icon: 'prediction', label: 'nav.prediction', group: 'nav.groupTools' },
  { to: '/analiza', icon: 'analysis', label: 'nav.analysis', group: 'nav.groupTools' },
]

export const adminNavigation: NavItem[] = [
  { to: '/admin', icon: 'admin', label: 'nav.admin', group: 'nav.groupOverview' },
  { to: '/admin/podatki', icon: 'data', label: 'nav.data', group: 'nav.groupPipeline' },
  { to: '/admin/priprava', icon: 'prepare', label: 'nav.prepare', group: 'nav.groupPipeline' },
  { to: '/admin/model', icon: 'model', label: 'nav.model', group: 'nav.groupPipeline' },
  {
    to: '/admin/diagnostika',
    icon: 'diagnostics',
    label: 'nav.diagnostics',
    group: 'nav.groupMonitor',
  },
  {
    to: '/admin/uporabniki',
    icon: 'admin',
    label: 'admin.userManagement',
    group: 'nav.groupMonitor',
  },
]
