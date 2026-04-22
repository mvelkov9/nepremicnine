<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { useDebounceFn } from '@vueuse/core'
  import { useI18n } from 'vue-i18n'
  import type { DataTableSortEvent } from 'primevue/datatable'
  import Menu from 'primevue/menu'
  import { useConfirm } from 'primevue/useconfirm'
  import AdminWorkspaceHero from '../components/admin/AdminWorkspaceHero.vue'
  import AdminActivityPanel from '../features/admin/AdminActivityPanel.vue'
  import AdminUsersPanel from '../features/admin/AdminUsersPanel.vue'
  import { adminWorkspaceLinks } from '../constants/adminWorkspace'
  import { useExport } from '../composables/useExport'
  import api from '../composables/useApi'
  import { useServerTableState } from '../composables/useServerTableState'
  import { useWorkbenchStore } from '../stores/workbench'
  import type { ServerTableResult, User } from '../types/api'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatDate, formatNumber } from '../utils/format'

  interface AdminUsersResponse extends ServerTableResult<User> {
    per_page?: number
  }

  interface AdminStats {
    total_users: number
    active_users: number
    disabled_users: number
    admin_users: number
  }

  interface AdminPageEvent {
    page?: number
    rows?: number
  }

  const pageSizeOptions = ['10', '25', '50', '100']

  function emptyStats(): AdminStats {
    return {
      total_users: 0,
      active_users: 0,
      disabled_users: 0,
      admin_users: 0,
    }
  }

  const { t } = useI18n()
  const confirm = useConfirm()
  const workbench = useWorkbenchStore()
  const { exportToCSV } = useExport()

  const loading = ref(false)
  const statsLoading = ref(false)
  const activityLoading = ref(false)
  const error = ref('')
  const activityError = ref('')
  const searchInput = ref('')
  const actionMenu = ref()
  const selectedUserForActions = ref<User | null>(null)
  const stats = ref<AdminStats>(emptyStats())
  const users = ref<AdminUsersResponse>({
    items: [],
    total: 0,
    page: 1,
    page_size: 25,
    pages: 0,
    filters: {},
    sort: 'created_at',
    order: 'desc',
  })
  let fetchUsersVersion = 0

  const table = useServerTableState(
    {
      page: '1',
      page_size: '25',
      sort: 'created_at',
      order: 'desc',
      search: '',
      role: '',
      status: '',
    },
    {
      filterKeys: ['role', 'status'],
    },
  )

  const roleOptions = computed(() => [
    { label: t('admin.allRoles'), value: '' },
    { label: t('layout.roleAdmin'), value: 'admin' },
    { label: t('layout.roleViewer'), value: 'viewer' },
  ])

  const statusOptions = computed(() => [
    { label: t('admin.allStatuses'), value: '' },
    { label: t('admin.active'), value: 'active' },
    { label: t('admin.disabled'), value: 'disabled' },
  ])

  const filterBadgeLabel = computed(() =>
    table.activeFilterCount.value > 0
      ? t('dashboard.activeFilterCount', { count: table.activeFilterCount.value })
      : t('dashboard.noActiveFilters'),
  )

  const visibleUsersLabel = computed(() =>
    table.activeFilterCount.value > 0
      ? `${t('admin.totalUsers', { count: users.value.total })} · ${filterBadgeLabel.value}`
      : t('admin.totalUsers', { count: users.value.total }),
  )

  const summaryCards = computed(() => [
    {
      label: t('admin.userManagement'),
      value: formatNumber(stats.value.total_users),
      meta: t('admin.totalUsers', { count: stats.value.total_users }),
    },
    {
      label: t('admin.active'),
      value: formatNumber(stats.value.active_users),
      meta: t('admin.status'),
      tone: 'success' as const,
    },
    {
      label: t('layout.roleAdmin'),
      value: formatNumber(stats.value.admin_users),
      meta: t('admin.adminUsersHint'),
    },
    {
      label: t('admin.disabled'),
      value: formatNumber(stats.value.disabled_users),
      meta: t('admin.activeUsersHint'),
      tone: 'warning' as const,
    },
  ])

  const adminActivity = computed(() => workbench.adminActivity.slice(0, 8))

  const tableWindowLabel = computed(() => {
    const total = users.value.total
    if (!total || !users.value.items.length) return t('empty.noUsers')

    const start = (table.page.value - 1) * table.pageSize.value + 1
    const end = Math.min(start + users.value.items.length - 1, total)

    return `${formatNumber(start)}-${formatNumber(end)} / ${formatNumber(total)}`
  })

  function emptyUsersResponse(): AdminUsersResponse {
    return {
      items: [],
      total: 0,
      page: table.page.value,
      page_size: table.pageSize.value,
      pages: 0,
      filters: {},
      sort: table.sort.value,
      order: table.order.value,
    }
  }

  const actionMenuItems = computed(() => {
    const user = selectedUserForActions.value
    if (!user) return []
    return [
      {
        label: user.role === 'admin' ? t('admin.makeViewer') : t('admin.makeAdmin'),
        icon: user.role === 'admin' ? 'pi pi-user' : 'pi pi-shield',
        command: () => void toggleRole(user),
      },
      {
        label: user.is_active ? t('admin.disable') : t('admin.enable'),
        icon: user.is_active ? 'pi pi-times-circle' : 'pi pi-check-circle',
        command: () => void toggleActive(user),
      },
      {
        label: t('common.delete'),
        icon: 'pi pi-trash',
        command: () => deleteUser(user),
      },
    ]
  })

  const debouncedSearchSync = useDebounceFn((value: string) => {
    table.search.value = value
  }, 260)

  watch(
    () => table.search.value,
    (value) => {
      if (value !== searchInput.value) searchInput.value = value
    },
    { immediate: true },
  )

  watch(searchInput, (value) => {
    debouncedSearchSync(value)
  })

  watch(
    () => [
      table.state.page,
      table.state.page_size,
      table.state.sort,
      table.state.order,
      table.state.search,
      table.state.role,
      table.state.status,
    ],
    () => {
      void fetchUsers()
    },
  )

  async function fetchUsers() {
    const requestVersion = ++fetchUsersVersion
    loading.value = true
    error.value = ''
    try {
      const { data } = await api.get<AdminUsersResponse>('/api/admin/users', {
        params: {
          page: table.page.value,
          per_page: table.pageSize.value,
          search: table.search.value || undefined,
          role: table.state.role || undefined,
          status: table.state.status || undefined,
          sort: table.sort.value,
          order: table.order.value,
        },
      })
      if (requestVersion !== fetchUsersVersion) return
      users.value = data
    } catch (requestError) {
      if (requestVersion !== fetchUsersVersion) return
      users.value = emptyUsersResponse()
      error.value = getApiErrorMessage(requestError, t)
    } finally {
      if (requestVersion === fetchUsersVersion) {
        loading.value = false
      }
    }
  }

  async function fetchStats() {
    statsLoading.value = true
    try {
      const { data } = await api.get<AdminStats>('/api/admin/stats')
      stats.value = data
    } catch (requestError) {
      stats.value = emptyStats()
      if (!error.value) error.value = getApiErrorMessage(requestError, t)
    } finally {
      statsLoading.value = false
    }
  }

  async function fetchActivity() {
    activityLoading.value = true
    activityError.value = ''
    try {
      await workbench.fetchAdminActivity()
    } catch (requestError) {
      activityError.value = getApiErrorMessage(requestError, t)
    } finally {
      activityLoading.value = false
    }
  }

  async function toggleRole(user: User) {
    const newRole = user.role === 'admin' ? 'viewer' : 'admin'
    try {
      await api.patch(`/api/admin/users/${user.id}`, { role: newRole })
      await Promise.all([fetchUsers(), fetchStats()])
    } catch (requestError) {
      error.value = getApiErrorMessage(requestError, t)
    }
  }

  async function toggleActive(user: User) {
    try {
      await api.patch(`/api/admin/users/${user.id}`, {
        is_active: !user.is_active,
      })
      await Promise.all([fetchUsers(), fetchStats()])
    } catch (requestError) {
      error.value = getApiErrorMessage(requestError, t)
    }
  }

  function deleteUser(user: User) {
    confirm.require({
      message: t('admin.confirmDelete', { name: user.full_name || user.email }),
      header: t('common.delete'),
      icon: 'pi pi-exclamation-triangle',
      rejectProps: { label: t('common.cancel'), severity: 'secondary', outlined: true },
      acceptProps: { label: t('common.delete'), severity: 'danger' },
      accept: async () => {
        try {
          await api.delete(`/api/admin/users/${user.id}`)
          const nextPage =
            users.value.items.length === 1 && table.page.value > 1
              ? table.page.value - 1
              : table.page.value

          if (nextPage !== table.page.value) {
            await table.patchState({ page: String(nextPage) })
            await fetchStats()
            return
          }

          await Promise.all([fetchUsers(), fetchStats()])
        } catch (requestError) {
          error.value = getApiErrorMessage(requestError, t)
        }
      },
    })
  }

  function clearFilters() {
    searchInput.value = ''
    table.resetFilters({
      search: '',
      page_size: '25',
      sort: 'created_at',
      order: 'desc',
    })
  }

  function exportCurrentRows() {
    exportToCSV(
      users.value.items.map((user) => ({
        id: user.id,
        name: user.full_name || '',
        email: user.email,
        role: user.role,
        status: user.is_active ? t('admin.active') : t('admin.disabled'),
        created_at: formatDate(user.created_at, { dateStyle: 'medium' }),
        last_login_at: user.last_login_at
          ? formatDate(user.last_login_at, { dateStyle: 'medium', timeStyle: 'short' })
          : '',
      })),
      'admin-users-current-page.csv',
    )
  }

  function onPage(event: AdminPageEvent) {
    void table.patchState({
      page: String((event.page || 0) + 1),
      page_size: String(event.rows || table.pageSize.value),
    })
  }

  function onSort(event: DataTableSortEvent) {
    const sortField = typeof event.sortField === 'string' ? event.sortField : table.sort.value
    const sortOrder = event.sortOrder === 1 ? 'asc' : 'desc'
    void table.patchState({
      page: '1',
      sort: sortField,
      order: sortOrder,
    })
  }

  function onRoleChange(value: string) {
    table.setFilter('role', value)
  }

  function onStatusChange(value: string) {
    table.setFilter('status', value)
  }

  function onPageSizeChange(value: number | string) {
    table.pageSize.value = Number.parseInt(String(value), 10) || 25
  }

  function openActionMenu(event: Event, user: User) {
    selectedUserForActions.value = user
    actionMenu.value?.toggle(event)
  }

  async function initializePage() {
    await Promise.allSettled([fetchUsers(), fetchStats(), fetchActivity()])
  }

  onMounted(async () => {
    await initializePage()
  })
</script>

<template>
  <div class="admin-view">
    <AdminWorkspaceHero
      :eyebrow="t('layout.adminWorkbench')"
      :title="t('admin.userManagement')"
      :description="t('admin.description')"
      :metrics="summaryCards"
      :links="adminWorkspaceLinks"
      :status="statsLoading ? t('common.loading') : filterBadgeLabel"
      :status-severity="table.activeFilterCount.value > 0 ? 'contrast' : 'secondary'"
    />

    <Menu ref="actionMenu" :model="actionMenuItems" popup />

    <div class="admin-workspace-grid">
      <AdminUsersPanel
        :eyebrow="t('layout.adminWorkbench')"
        :title="t('admin.userManagement')"
        :description="t('admin.description')"
        :status-label="statsLoading ? t('common.loading') : filterBadgeLabel"
        :status-severity="table.activeFilterCount.value > 0 ? 'contrast' : 'secondary'"
        :visible-users-label="visibleUsersLabel"
        :table-window-label="tableWindowLabel"
        :loading="loading"
        :error="error"
        :users="users.items"
        :total-records="users.total"
        :page="table.page.value"
        :page-size="table.pageSize.value"
        :sort-field="table.sort.value"
        :sort-order="table.order.value"
        :search-value="searchInput"
        :role-value="table.state.role"
        :status-value="table.state.status"
        :role-options="roleOptions"
        :status-options="statusOptions"
        :page-size-options="pageSizeOptions"
        @update:search-value="searchInput = $event"
        @update:role-value="onRoleChange"
        @update:status-value="onStatusChange"
        @update:page-size-value="onPageSizeChange"
        @clear="clearFilters"
        @export="exportCurrentRows"
        @page="onPage"
        @sort="onSort"
        @retry="initializePage"
        @open-actions="openActionMenu"
      />

      <AdminActivityPanel
        :eyebrow="t('workbench.activityCenter')"
        :title="t('workbench.adminTimeline')"
        :items="adminActivity"
        :loading="activityLoading"
        :error="activityError"
        @retry="fetchActivity"
      />
    </div>
  </div>
</template>

<style scoped>
  .admin-view {
    display: grid;
    gap: 1.35rem;
    --page-accent: var(--primary);
    --page-accent-2: var(--accent);
  }

  .admin-workspace-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1.35rem;
    align-items: start;
  }

  .admin-workspace-grid :deep(.admin-users-panel) {
    border-color: color-mix(in srgb, var(--border) 56%, var(--page-accent) 44%);
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--page-accent) 14%, transparent),
        transparent 42%
      ),
      var(--surface-panel);
  }

  .admin-workspace-grid :deep(.admin-activity-panel) {
    border-color: color-mix(in srgb, var(--border) 56%, var(--page-accent-2) 44%);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--page-accent-2) 14%, transparent),
        transparent 44%
      ),
      var(--surface-panel);
  }

  .admin-workspace-grid :deep(.admin-activity-panel) {
    min-width: 0;
  }
</style>
