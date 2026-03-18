<script setup lang="ts">
  definePageMeta({ middleware: ['admin'] })

  interface User {
    id: number
    full_name: string
    email: string
    avatar_url: string | null
    role: 'admin' | 'viewer'
    is_active: boolean
    created_at: string
  }

  interface UsersResponse {
    items: User[]
  }

  const { t } = useI18n()
  const api = useApi()

  const users = ref<User[]>([])
  const loading = ref(false)
  const error = ref('')

  const columns = [
    { accessorKey: 'id', header: 'ID' },
    { accessorKey: 'full_name', header: t('admin.name') },
    { accessorKey: 'email', header: t('admin.email') },
    { accessorKey: 'role', header: t('admin.role') },
    { accessorKey: 'is_active', header: t('admin.status') },
    { accessorKey: 'created_at', header: t('admin.created') },
    { accessorKey: 'actions', header: t('data.actions'), enableSorting: false },
  ]

  async function fetchUsers() {
    loading.value = true
    error.value = ''
    try {
      const { data } = await api.get<UsersResponse>('/api/admin/users')
      users.value = data.items || []
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  async function toggleRole(user: User) {
    const newRole = user.role === 'admin' ? 'viewer' : 'admin'
    try {
      const { data } = await api.patch<User>(`/api/admin/users/${user.id}`, { role: newRole })
      const idx = users.value.findIndex((u) => u.id === user.id)
      if (idx !== -1) users.value[idx] = data
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function toggleActive(user: User) {
    try {
      const { data } = await api.patch<User>(`/api/admin/users/${user.id}`, {
        is_active: !user.is_active,
      })
      const idx = users.value.findIndex((u) => u.id === user.id)
      if (idx !== -1) users.value[idx] = data
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function deleteUser(user: User) {
    if (!confirm(t('admin.confirmDelete', { name: user.full_name }))) return
    try {
      await api.delete(`/api/admin/users/${user.id}`)
      users.value = users.value.filter((u) => u.id !== user.id)
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  function roleBadgeColor(role: string): 'info' | 'neutral' {
    return role === 'admin' ? 'info' : 'neutral'
  }

  function activeBadgeColor(active: boolean): 'success' | 'error' {
    return active ? 'success' : 'error'
  }

  useLazyAsyncData('admin-users', fetchUsers)
</script>

<template>
  <div class="admin-page">
    <section class="card admin-shell">
      <!-- Page header -->
      <div class="section-head">
        <div>
          <p class="eyebrow">{{ t('nav.admin') }}</p>
          <h1>{{ t('admin.userManagement') }}</h1>
          <p class="muted">{{ t('layout.page.adminUsers') }}</p>
        </div>
        <UButton
          icon="i-lucide-refresh-cw"
          variant="outline"
          color="neutral"
          :loading="loading"
          :label="loading ? t('common.loading') : t('common.refresh', 'Refresh')"
          @click="fetchUsers"
        />
      </div>

      <!-- Error alert -->
      <UAlert
        v-if="error"
        :description="error"
        color="error"
        variant="soft"
        icon="i-lucide-alert-circle"
      />

      <!-- Loading skeleton -->
      <div v-if="loading" class="grid gap-2">
        <USkeleton v-for="i in 6" :key="i" class="h-10" />
      </div>

      <!-- Empty state -->
      <p v-else-if="!users.length" class="admin-empty muted">
        {{ t('empty.noUsers') }}
      </p>

      <!-- Users table -->
      <div v-else class="table-wrap admin-table">
        <UTable :columns="columns" :data="users">
          <template #full_name-cell="{ row }">
            <div class="user-identity">
              <strong>{{ row.original.full_name }}</strong>
              <small>{{ row.original.avatar_url || row.original.email }}</small>
            </div>
          </template>

          <template #role-cell="{ row }">
            <UBadge
              :label="row.original.role"
              :color="roleBadgeColor(row.original.role)"
              variant="soft"
            />
          </template>

          <template #is_active-cell="{ row }">
            <UBadge
              :label="row.original.is_active ? t('admin.active') : t('admin.disabled')"
              :color="activeBadgeColor(row.original.is_active)"
              variant="soft"
            />
          </template>

          <template #created_at-cell="{ row }">
            {{ formatDate(row.original.created_at, { dateStyle: 'medium' }) }}
          </template>

          <template #actions-cell="{ row }">
            <div class="user-actions">
              <UButton
                size="xs"
                variant="outline"
                color="neutral"
                :aria-label="`${row.original.role === 'admin' ? t('admin.makeViewer') : t('admin.makeAdmin')} - ${row.original.full_name}`"
                :label="
                  row.original.role === 'admin' ? t('admin.makeViewer') : t('admin.makeAdmin')
                "
                @click="toggleRole(row.original)"
              />
              <UButton
                size="xs"
                :variant="row.original.is_active ? 'outline' : 'solid'"
                :color="row.original.is_active ? 'error' : 'success'"
                :aria-label="`${row.original.is_active ? t('admin.disable') : t('admin.enable')} - ${row.original.full_name}`"
                :label="row.original.is_active ? t('admin.disable') : t('admin.enable')"
                @click="toggleActive(row.original)"
              />
              <UButton
                size="xs"
                variant="outline"
                color="error"
                icon="i-lucide-trash-2"
                :aria-label="`${t('common.delete')} – ${row.original.full_name}`"
                :label="t('common.delete')"
                @click="deleteUser(row.original)"
              />
            </div>
          </template>
        </UTable>
      </div>
    </section>
  </div>
</template>

<style scoped>
  .admin-page {
    display: grid;
  }

  .card {
    padding: 1.25rem;
    border-radius: 1.5rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
  }

  .admin-shell {
    display: grid;
    gap: 1rem;
  }

  .section-head h1 {
    font-size: clamp(1.5rem, 2vw, 2rem);
  }

  .admin-table {
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 18px 30px rgb(15 23 42 / 6%);
  }

  .admin-empty {
    text-align: center;
    padding: 1.5rem;
    margin: 0;
  }

  .user-identity {
    display: grid;
    gap: 0.14rem;
  }

  .user-identity small {
    color: var(--text-muted);
  }

  .user-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  @media (max-width: 720px) {
    .section-head {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
