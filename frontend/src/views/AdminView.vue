<script setup lang="ts">
  import { ref, onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useConfirm } from 'primevue/useconfirm'
  import api from '../composables/useApi'
  import PageHeader from '../components/PageHeader.vue'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatDate } from '../utils/format'

  const { t } = useI18n()
  const confirm = useConfirm()

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

  onMounted(fetchUsers)
</script>

<template>
  <div>
    <PageHeader :title="t('nav.admin')" />

    <div class="card">
      <h2>{{ t('admin.userManagement') }}</h2>
      <p v-if="error" class="error-text mb-3">{{ error }}</p>

      <DataTable
        :value="users"
        :loading="loading"
        striped-rows
        responsive-layout="scroll"
      >
        <template #empty>
          <div class="empty-message">
            {{ t('empty.noUsers') }}
          </div>
        </template>

        <Column field="id" header="ID" />
        <Column field="full_name" :header="t('admin.name')" />
        <Column field="email" :header="t('admin.email')" />

        <Column field="role" :header="t('admin.role')">
          <template #body="{ data }">
            <Tag :value="data.role" :severity="roleSeverity(data.role)" />
          </template>
        </Column>

        <Column field="is_active" :header="t('admin.status')">
          <template #body="{ data }">
            <Tag
              :value="data.is_active ? t('admin.active') : t('admin.disabled')"
              :severity="statusSeverity(data.is_active)"
            />
          </template>
        </Column>

        <Column field="created_at" :header="t('admin.created')">
          <template #body="{ data }">
            {{ formatCreatedAt(data.created_at) }}
          </template>
        </Column>

        <Column :header="t('data.actions')">
          <template #body="{ data }">
            <div class="flex gap-2 flex-wrap">
              <Button
                :label="data.role === 'admin' ? t('admin.makeViewer') : t('admin.makeAdmin')"
                severity="secondary"
                size="small"
                :aria-label="`${data.role === 'admin' ? t('admin.makeViewer') : t('admin.makeAdmin')} - ${data.full_name}`"
                @click="toggleRole(data)"
              />
              <Button
                :label="data.is_active ? t('admin.disable') : t('admin.enable')"
                :severity="data.is_active ? 'danger' : undefined"
                size="small"
                :aria-label="`${data.is_active ? t('admin.disable') : t('admin.enable')} - ${data.full_name}`"
                @click="toggleActive(data)"
              />
              <Button
                :label="t('common.delete')"
                severity="danger"
                size="small"
                :aria-label="`${t('common.delete')} – ${data.full_name}`"
                @click="deleteUser(data)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>
  </div>
</template>

<style scoped>
  .mb-3 {
    margin-bottom: 1rem;
  }

  .empty-message {
    text-align: center;
    color: var(--text-muted, #6b7280);
    padding: 1.5rem;
  }
</style>
