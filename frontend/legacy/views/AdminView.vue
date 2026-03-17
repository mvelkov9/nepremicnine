<script setup>
  import { ref, onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import api from '../composables/useApi'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatDate } from '../utils/format'

  const { t } = useI18n()

  const users = ref([])
  const loading = ref(false)
  const error = ref(null)

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
    try {
      const { data } = await api.patch(`/api/admin/users/${user.id}`, { role: newRole })
      const idx = users.value.findIndex((u) => u.id === user.id)
      if (idx !== -1) users.value[idx] = data
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function toggleActive(user) {
    try {
      const { data } = await api.patch(`/api/admin/users/${user.id}`, {
        is_active: !user.is_active,
      })
      const idx = users.value.findIndex((u) => u.id === user.id)
      if (idx !== -1) users.value[idx] = data
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function deleteUser(user) {
    if (!confirm(t('admin.confirmDelete', { name: user.full_name }))) return
    try {
      await api.delete(`/api/admin/users/${user.id}`)
      users.value = users.value.filter((u) => u.id !== user.id)
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  function roleBadge(role) {
    return role === 'admin' ? 'badge-blue' : 'badge-gray'
  }

  function activeBadge(active) {
    return active ? 'badge-green' : 'badge-red'
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
  <div class="admin-page">
    <section class="card admin-shell">
      <PageHeader
        :eyebrow="t('nav.admin')"
        :title="t('admin.userManagement')"
        :description="t('layout.page.adminUsers')"
      />

      <p v-if="error" class="error-text admin-error">{{ error }}</p>

      <LoadingSpinner v-if="loading" :label="t('common.loading')" />

      <div v-else class="table-wrap admin-table">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>{{ t('admin.name') }}</th>
              <th>{{ t('admin.email') }}</th>
              <th>{{ t('admin.role') }}</th>
              <th>{{ t('admin.status') }}</th>
              <th>{{ t('admin.created') }}</th>
              <th>{{ t('data.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="users.length === 0">
              <td colspan="7" class="admin-empty">
                {{ t('empty.noUsers') }}
              </td>
            </tr>
            <tr v-for="user in users" :key="user.id">
              <td>{{ user.id }}</td>
              <td>
                <div class="user-identity">
                  <strong>{{ user.full_name }}</strong>
                  <small>{{ user.avatar_url || user.email }}</small>
                </div>
              </td>
              <td>{{ user.email }}</td>
              <td>
                <span class="badge" :class="roleBadge(user.role)">{{ user.role }}</span>
              </td>
              <td>
                <span class="badge" :class="activeBadge(user.is_active)">
                  {{ user.is_active ? t('admin.active') : t('admin.disabled') }}
                </span>
              </td>
              <td>{{ formatCreatedAt(user.created_at) }}</td>
              <td>
                <div class="user-actions">
                  <Button
                    severity="secondary"
                    outlined
                    class="mini-action"
                    :aria-label="roleActionLabel(user)"
                    @click="toggleRole(user)"
                    :label="user.role === 'admin' ? t('admin.makeViewer') : t('admin.makeAdmin')"
                  />
                  <Button
                    :severity="user.is_active ? 'danger' : 'success'"
                    :outlined="user.is_active"
                    class="mini-action"
                    :aria-label="activeActionLabel(user)"
                    @click="toggleActive(user)"
                    :label="user.is_active ? t('admin.disable') : t('admin.enable')"
                  />
                  <Button
                    severity="danger"
                    outlined
                    class="mini-action"
                    :aria-label="t('common.delete') + ' – ' + user.full_name"
                    @click="deleteUser(user)"
                    :label="t('common.delete')"
                  />
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
  .admin-page {
    display: grid;
  }

  .admin-shell {
    display: grid;
    gap: 1rem;
  }

  .admin-error {
    margin: 0;
  }

  .admin-table {
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 18px 30px rgb(15 23 42 / 6%);
  }

  .admin-empty {
    text-align: center;
    color: var(--text-muted);
    padding: 1.5rem;
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

  .user-actions :deep(.mini-action) {
    min-height: 2.1rem;
    padding-inline: 0.85rem;
    font-size: 0.76rem;
  }
</style>
