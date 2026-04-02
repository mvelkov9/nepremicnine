<script setup lang="ts">
  import { ref, computed, onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useConfirm } from 'primevue/useconfirm'
  import api from '../composables/useApi'
  import AdminWorkspaceHero from '../components/admin/AdminWorkspaceHero.vue'
  import { adminWorkspaceLinks } from '../constants/adminWorkspace'
  import { useWorkbenchStore } from '../stores/workbench'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatDate } from '../utils/format'

  const { t } = useI18n()
  const confirm = useConfirm()
  const workbench = useWorkbenchStore()

  const users = ref([])
  const loading = ref(false)
  const error = ref(null)
  const userFilter = ref('')
  const roleFilter = ref('all')
  const statusFilter = ref('all')

  const roleOptions = computed(() => [
    { label: t('admin.allRoles'), value: 'all' },
    { label: t('layout.roleAdmin'), value: 'admin' },
    { label: t('layout.roleViewer'), value: 'viewer' },
  ])

  const statusOptions = computed(() => [
    { label: t('admin.allStatuses'), value: 'all' },
    { label: t('admin.active'), value: 'active' },
    { label: t('admin.disabled'), value: 'disabled' },
  ])

  const filteredUsers = computed(() => {
    const query = userFilter.value.trim().toLowerCase()
    return users.value.filter((user: any) => {
      const matchesQuery =
        !query ||
        [user.full_name, user.email].some((value) =>
          String(value || '')
            .toLowerCase()
            .includes(query),
        )
      const matchesRole = roleFilter.value === 'all' || user.role === roleFilter.value
      const matchesStatus =
        statusFilter.value === 'all' ||
        (statusFilter.value === 'active' ? user.is_active : !user.is_active)
      return matchesQuery && matchesRole && matchesStatus
    })
  })

  const summaryCards = computed(() => [
    {
      label: t('admin.userManagement'),
      value: String(users.value.length),
      meta: t('admin.totalUsers', { count: users.value.length }),
    },
    {
      label: t('admin.active'),
      value: String(users.value.filter((user: any) => user.is_active).length),
      meta: t('admin.status'),
      tone: 'success' as const,
    },
    {
      label: t('layout.roleAdmin'),
      value: String(users.value.filter((user: any) => user.role === 'admin').length),
      meta: t('admin.adminUsersHint'),
    },
    {
      label: t('admin.disabled'),
      value: String(users.value.filter((user: any) => !user.is_active).length),
      meta: t('admin.activeUsersHint'),
      tone: 'warning' as const,
    },
  ])

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

  async function toggleRole(user: any) {
    const newRole = user.role === 'admin' ? 'viewer' : 'admin'
    try {
      const { data } = await api.patch(`/api/admin/users/${user.id}`, { role: newRole })
      const idx = users.value.findIndex((u: any) => u.id === user.id)
      if (idx !== -1) users.value[idx] = data
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function toggleActive(user: any) {
    try {
      const { data } = await api.patch(`/api/admin/users/${user.id}`, {
        is_active: !user.is_active,
      })
      const idx = users.value.findIndex((u: any) => u.id === user.id)
      if (idx !== -1) users.value[idx] = data
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  function deleteUser(user: any) {
    confirm.require({
      message: t('admin.confirmDelete', { name: user.full_name }),
      header: t('common.delete'),
      icon: 'pi pi-exclamation-triangle',
      rejectProps: { label: t('common.cancel'), severity: 'secondary', outlined: true },
      acceptProps: { label: t('common.delete'), severity: 'danger' },
      accept: async () => {
        try {
          await api.delete(`/api/admin/users/${user.id}`)
          users.value = users.value.filter((u: any) => u.id !== user.id)
        } catch (e) {
          error.value = getApiErrorMessage(e, t)
        }
      },
    })
  }

  function roleSeverity(role: string) {
    return role === 'admin' ? 'info' : 'secondary'
  }

  function statusSeverity(active: boolean) {
    return active ? 'success' : 'danger'
  }

  function formatCreatedAt(value: string) {
    return formatDate(value, { dateStyle: 'medium' })
  }

  onMounted(async () => {
    await Promise.allSettled([fetchUsers(), workbench.fetchAdminActivity()])
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
      :status="t('admin.totalUsers', { count: users.length })"
      status-severity="secondary"
    />

    <section class="card admin-users-panel">
      <div class="panel-toolbar">
        <div>
          <p class="eyebrow subtle">{{ t('layout.adminWorkbench') }}</p>
          <h2>{{ t('admin.userManagement') }}</h2>
        </div>

        <div class="toolbar-controls">
          <IconField class="search-field">
            <InputIcon class="pi pi-search" />
            <InputText v-model="userFilter" :placeholder="t('common.search')" />
          </IconField>

          <Select
            v-model="roleFilter"
            :options="roleOptions"
            option-label="label"
            option-value="value"
            class="toolbar-select"
          />

          <Select
            v-model="statusFilter"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            class="toolbar-select"
          />
        </div>
      </div>

      <p v-if="error" class="error-text">{{ error }}</p>

      <DataTable
        :value="filteredUsers"
        :loading="loading"
        paginator
        :rows="10"
        striped-rows
        responsive-layout="scroll"
      >
        <template #empty>
          <div class="empty-message">
            {{ t('empty.noUsers') }}
          </div>
        </template>

        <Column field="id" :header="t('common.id')" sortable />
        <Column field="full_name" :header="t('admin.name')" sortable />
        <Column field="email" :header="t('admin.email')" sortable />

        <Column field="role" :header="t('admin.role')" sortable>
          <template #body="{ data }">
            <Tag :value="data.role" :severity="roleSeverity(data.role)" />
          </template>
        </Column>

        <Column field="is_active" :header="t('admin.status')" sortable>
          <template #body="{ data }">
            <Tag
              :value="data.is_active ? t('admin.active') : t('admin.disabled')"
              :severity="statusSeverity(data.is_active)"
            />
          </template>
        </Column>

        <Column field="created_at" :header="t('admin.created')" sortable>
          <template #body="{ data }">
            {{ formatCreatedAt(data.created_at) }}
          </template>
        </Column>

        <Column :header="t('data.actions')">
          <template #body="{ data }">
            <div class="row-actions">
              <Button
                :icon="data.role === 'admin' ? 'pi pi-user' : 'pi pi-shield'"
                :label="data.role === 'admin' ? t('admin.makeViewer') : t('admin.makeAdmin')"
                severity="secondary"
                size="small"
                outlined
                :aria-label="`${data.role === 'admin' ? t('admin.makeViewer') : t('admin.makeAdmin')} - ${data.full_name}`"
                @click="toggleRole(data)"
              />
              <Button
                :icon="data.is_active ? 'pi pi-times-circle' : 'pi pi-check-circle'"
                :label="data.is_active ? t('admin.disable') : t('admin.enable')"
                :severity="data.is_active ? 'danger' : undefined"
                size="small"
                outlined
                :aria-label="`${data.is_active ? t('admin.disable') : t('admin.enable')} - ${data.full_name}`"
                @click="toggleActive(data)"
              />
              <Button
                icon="pi pi-trash"
                :label="t('common.delete')"
                severity="danger"
                size="small"
                outlined
                :aria-label="`${t('common.delete')} – ${data.full_name}`"
                @click="deleteUser(data)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </section>

    <section class="card admin-activity-panel">
      <div class="panel-toolbar">
        <div>
          <p class="eyebrow subtle">{{ t('workbench.activityCenter') }}</p>
          <h2>{{ t('workbench.adminTimeline') }}</h2>
        </div>
      </div>

      <div v-if="workbench.adminActivity.length" class="activity-list">
        <article
          v-for="item in workbench.adminActivity.slice(0, 8)"
          :key="item.id"
          class="activity-row"
        >
          <strong>{{ item.title }}</strong>
          <p class="muted">{{ item.body || item.category }}</p>
        </article>
      </div>
      <div v-else class="empty-message">
        {{ t('workbench.noActivity') }}
      </div>
    </section>
  </div>
</template>

<style scoped>
  .admin-view {
    display: grid;
    gap: 1rem;
  }

  .admin-overview,
  .admin-users-panel {
    display: grid;
    gap: 1rem;
  }

  .admin-metric-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .panel-toolbar {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .panel-toolbar h2 {
    margin: 0.2rem 0 0;
    font-family: var(--font-display);
    font-size: 1.45rem;
    line-height: 1.05;
  }

  .search-field {
    width: min(100%, 22rem);
  }

  .toolbar-controls,
  .activity-list {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .toolbar-select {
    min-width: 11rem;
  }

  .row-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .empty-message {
    text-align: center;
    color: var(--text-muted, #6b7280);
    padding: 1.5rem;
  }

  .eyebrow.subtle {
    color: var(--text-soft);
  }

  .admin-activity-panel {
    display: grid;
    gap: 1rem;
  }

  .activity-list {
    display: grid;
  }

  .activity-row {
    padding: 0.9rem 1rem;
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--surface-soft-subtle) 84%, white 16%);
  }

  .activity-row p {
    margin: 0.25rem 0 0;
  }

  @media (max-width: 980px) {
    .admin-metric-grid {
      grid-template-columns: 1fr;
    }

    .toolbar-controls {
      width: 100%;
      display: grid;
      grid-template-columns: 1fr;
    }
  }
</style>
