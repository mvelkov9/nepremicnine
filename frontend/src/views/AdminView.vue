<script setup>
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Tag from 'primevue/tag'
  import api from '../composables/useApi'
  import AppDataTable from '../components/AppDataTable.vue'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import { useConfirmDialog } from '../composables/useConfirmDialog'
  import { useToast } from '../composables/useToast'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatDate } from '../utils/format'

  const { t } = useI18n()
  const { confirmAction } = useConfirmDialog()
  const { showToast } = useToast()

  const users = ref([])
  const loading = ref(false)
  const error = ref(null)

  const tableColumns = computed(() => [
    { key: 'id', label: 'ID', sortable: true },
    { key: 'full_name', label: t('admin.name'), sortable: true },
    { key: 'email', label: t('admin.email'), sortable: true },
    { key: 'role', label: t('admin.role'), sortable: true },
    { key: 'is_active', label: t('admin.status'), sortable: true },
    {
      key: 'created_at',
      label: t('admin.created'),
      sortable: true,
      value: (row) => row.created_at,
    },
    { key: 'actions', label: t('data.actions') },
  ])

  const summaryCards = computed(() => {
    const totalUsers = users.value.length
    const adminUsers = users.value.filter((user) => user.role === 'admin').length
    const viewerUsers = users.value.filter((user) => user.role !== 'admin').length
    const activeUsers = users.value.filter((user) => user.is_active).length

    return [
      {
        label: t('admin.totalUsers'),
        value: String(totalUsers),
        meta: t('admin.userManagement'),
      },
      {
        label: t('admin.adminUsers'),
        value: String(adminUsers),
        meta: `${adminUsers}/${Math.max(totalUsers, 1)}`,
      },
      {
        label: t('admin.viewerUsers'),
        value: String(viewerUsers),
        meta: `${viewerUsers}/${Math.max(totalUsers, 1)}`,
      },
      {
        label: t('admin.activeUsers'),
        value: String(activeUsers),
        meta: `${activeUsers}/${Math.max(totalUsers, 1)}`,
        tone: activeUsers === totalUsers ? 'success' : 'warning',
      },
    ]
  })

  async function fetchUsers() {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get('/api/admin/users')
      users.value = data.items || []
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  async function toggleRole(user) {
    const newRole = user.role === 'admin' ? 'viewer' : 'admin'
    error.value = null
    try {
      const { data } = await api.patch(`/api/admin/users/${user.id}`, { role: newRole })
      const idx = users.value.findIndex((u) => u.id === user.id)
      if (idx !== -1) users.value[idx] = data
      showToast(t('admin.roleUpdated'), 'success')
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function toggleActive(user) {
    error.value = null
    try {
      const { data } = await api.patch(`/api/admin/users/${user.id}`, {
        is_active: !user.is_active,
      })
      const idx = users.value.findIndex((u) => u.id === user.id)
      if (idx !== -1) users.value[idx] = data
      showToast(t('admin.statusUpdated'), 'success')
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function deleteUser(user) {
    const confirmed = await confirmAction({
      header: t('common.confirm'),
      message: t('admin.confirmDelete', { name: user.full_name }),
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
    })
    if (!confirmed) return

    error.value = null
    try {
      await api.delete(`/api/admin/users/${user.id}`)
      users.value = users.value.filter((u) => u.id !== user.id)
      showToast(t('admin.userDeleted'), 'success')
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  function roleSeverity(role) {
    return role === 'admin' ? 'info' : 'secondary'
  }

  function activeSeverity(active) {
    return active ? 'success' : 'danger'
  }

  function roleActionLabel(user) {
    return `${user.role === 'admin' ? t('admin.makeViewer') : t('admin.makeAdmin')} - ${user.full_name}`
  }

  function activeActionLabel(user) {
    return `${user.is_active ? t('admin.disable') : t('admin.enable')} - ${user.full_name}`
  }

  function formatCreatedAt(value) {
    return formatDate(value, { dateStyle: 'medium' })
  }

  onMounted(fetchUsers)
</script>

<template>
  <div class="admin-users-page">
    <section class="card">
      <PageHeader
        :eyebrow="t('nav.admin')"
        :title="t('admin.userManagement')"
        :description="t('layout.page.adminUsers')"
      >
        <template #actions>
          <Tag severity="secondary" :value="String(users.length)" />
        </template>
      </PageHeader>
    </section>

    <section class="metrics-grid">
      <MetricCard
        v-for="card in summaryCards"
        :key="card.label"
        :label="card.label"
        :value="card.value"
        :meta="card.meta"
        :tone="card.tone || 'default'"
      />
    </section>

    <section class="card">
      <PageHeader
        compact
        :eyebrow="t('admin.userManagement')"
        :title="t('admin.userManagement')"
        :description="t('layout.page.adminUsers')"
      />

      <p v-if="error" class="error-text admin-error">{{ error }}</p>

      <LoadingSpinner v-if="loading" :label="t('common.loading')" />

      <EmptyState v-else-if="users.length === 0" icon="👥" :message="t('empty.noUsers')" />

      <AppDataTable
        v-else
        :rows="users"
        :columns="tableColumns"
        row-key="id"
        :page-size="10"
        :empty-message="t('empty.noUsers')"
      >
        <template #cell-role="{ row }">
          <Tag :severity="roleSeverity(row.role)" :value="row.role" />
        </template>
        <template #cell-is_active="{ row }">
          <Tag
            :severity="activeSeverity(row.is_active)"
            :value="row.is_active ? t('admin.active') : t('admin.disabled')"
          />
        </template>
        <template #cell-created_at="{ row }">
          {{ formatCreatedAt(row.created_at) }}
        </template>
        <template #cell-actions="{ row }">
          <div class="admin-actions">
            <Button
              size="small"
              severity="secondary"
              :label="row.role === 'admin' ? t('admin.makeViewer') : t('admin.makeAdmin')"
              :aria-label="roleActionLabel(row)"
              @click="toggleRole(row)"
            />
            <Button
              size="small"
              :severity="row.is_active ? 'warn' : 'success'"
              :label="row.is_active ? t('admin.disable') : t('admin.enable')"
              :aria-label="activeActionLabel(row)"
              @click="toggleActive(row)"
            />
            <Button
              size="small"
              severity="danger"
              :label="t('common.delete')"
              :aria-label="`${t('common.delete')} – ${row.full_name}`"
              @click="deleteUser(row)"
            />
          </div>
        </template>
      </AppDataTable>
    </section>
  </div>
</template>

<style scoped>
  .admin-users-page {
    display: grid;
    gap: 1.25rem;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    gap: 1rem;
  }

  .admin-error {
    margin: 0 0 1rem;
  }

  .admin-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  @media (max-width: 720px) {
    .admin-actions {
      min-width: 14rem;
    }
  }
</style>
