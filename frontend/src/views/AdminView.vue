<script setup>
  import { ref, onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import api from '../composables/useApi'

  const { t } = useI18n()

  const users = ref([])
  const loading = ref(false)
  const error = ref(null)

  async function fetchUsers() {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get('/api/admin/users')
      users.value = data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
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
      error.value = e.response?.data?.detail || e.message
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
      error.value = e.response?.data?.detail || e.message
    }
  }

  async function deleteUser(user) {
    if (!confirm(t('admin.confirmDelete', { name: user.full_name }))) return
    try {
      await api.delete(`/api/admin/users/${user.id}`)
      users.value = users.value.filter((u) => u.id !== user.id)
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
    }
  }

  function roleBadge(role) {
    return role === 'admin' ? 'badge-blue' : 'badge-gray'
  }

  function activeBadge(active) {
    return active ? 'badge-green' : 'badge-red'
  }

  onMounted(fetchUsers)
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.admin') }}</h1>

    <div class="card">
      <h2>{{ t('admin.userManagement') }}</h2>
      <p v-if="error" class="error-text" style="margin-bottom: 1rem">{{ error }}</p>

      <div v-if="loading" class="muted">{{ t('common.loading') }}</div>

      <div v-else class="table-wrap">
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
            <tr v-for="user in users" :key="user.id">
              <td>{{ user.id }}</td>
              <td>{{ user.full_name }}</td>
              <td>{{ user.email }}</td>
              <td>
                <span class="badge" :class="roleBadge(user.role)">{{ user.role }}</span>
              </td>
              <td>
                <span class="badge" :class="activeBadge(user.is_active)">
                  {{ user.is_active ? t('admin.active') : t('admin.disabled') }}
                </span>
              </td>
              <td>{{ new Date(user.created_at).toLocaleDateString() }}</td>
              <td>
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap">
                  <button
                    class="secondary"
                    style="padding: 4px 10px; font-size: 12px"
                    @click="toggleRole(user)"
                  >
                    {{ user.role === 'admin' ? '→ viewer' : '→ admin' }}
                  </button>
                  <button
                    :class="user.is_active ? 'danger' : ''"
                    style="padding: 4px 10px; font-size: 12px"
                    @click="toggleActive(user)"
                  >
                    {{ user.is_active ? t('admin.disable') : t('admin.enable') }}
                  </button>
                  <button
                    class="danger"
                    style="padding: 4px 10px; font-size: 12px"
                    @click="deleteUser(user)"
                  >
                    {{ t('common.delete') }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
