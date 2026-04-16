export interface AdminWorkspaceLink {
  to: string
  label: string
  description: string
  icon: string
}

export const adminWorkspaceLinks: AdminWorkspaceLink[] = [
  {
    to: '/admin',
    label: 'nav.admin',
    description: 'layout.page.adminHome',
    icon: 'admin',
  },
  {
    to: '/admin/podatki',
    label: 'nav.data',
    description: 'layout.page.data',
    icon: 'data',
  },
  {
    to: '/admin/priprava',
    label: 'nav.prepare',
    description: 'layout.page.prepare',
    icon: 'prepare',
  },
  {
    to: '/admin/model',
    label: 'nav.model',
    description: 'layout.page.model',
    icon: 'model',
  },
  {
    to: '/admin/diagnostika',
    label: 'nav.diagnostics',
    description: 'layout.page.diagnostics',
    icon: 'diagnostics',
  },
  {
    to: '/admin/dokaz',
    label: 'nav.benchmark',
    description: 'layout.page.benchmark',
    icon: 'benchmark',
  },
  {
    to: '/admin/uporabniki',
    label: 'admin.userManagement',
    description: 'layout.page.adminUsers',
    icon: 'user',
  },
]
