<script setup>
  import { onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useAuthStore } from '../stores/auth'
  import { useDataStore } from '../stores/data'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import EmptyState from '../components/EmptyState.vue'

  const { t } = useI18n()
  const auth = useAuthStore()
  const dataStore = useDataStore()

  const fileInput = ref(null)
  const previewData = ref(null)
  const previewName = ref('')
  const previewLoading = ref(false)
  const uploadResult = ref(null)
  const error = ref('')

  onMounted(() => dataStore.fetchDatasets())

  async function handleUpload() {
    const files = fileInput.value?.files
    if (!files?.length) return
    error.value = ''
    uploadResult.value = null
    try {
      const result = await dataStore.uploadFiles(files)
      uploadResult.value = result
      fileInput.value.value = ''
    } catch (e) {
      error.value = e.response?.data?.detail || t('common.error')
    }
  }

  async function showPreview(dataset) {
    previewName.value = dataset.original_name
    previewLoading.value = true
    error.value = ''
    try {
      previewData.value = await dataStore.fetchPreview(dataset.id)
    } catch (e) {
      error.value = e.response?.data?.detail || t('common.error')
    } finally {
      previewLoading.value = false
    }
  }

  async function handleDelete(id) {
    if (!confirm(t('data.confirmDelete'))) return
    try {
      await dataStore.deleteDataset(id)
    } catch (e) {
      error.value = e.response?.data?.detail || t('common.error')
    }
  }

  async function handleDeleteAll() {
    if (!dataStore.datasets.length) return
    if (!confirm(t('data.confirmDeleteAll'))) return
    try {
      await dataStore.deleteAllDatasets()
    } catch (e) {
      error.value = e.response?.data?.detail || t('common.error')
    }
  }

  function formatDate(iso) {
    if (!iso) return '—'
    return new Date(iso).toLocaleDateString('sl-SI', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  }

  function formatSize(rows) {
    if (rows == null) return '—'
    return Number(rows).toLocaleString('sl-SI')
  }
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.data') }}</h1>

    <!-- Upload section - admin only -->
    <div v-if="auth.isAdmin" class="card">
      <div class="card-title">{{ t('data.upload') }}</div>
      <div class="actions">
        <input
          ref="fileInput"
          type="file"
          multiple
          accept=".csv,.zip"
          style="flex: 1"
          :aria-label="t('data.upload')"
        />
        <button :disabled="dataStore.uploading" @click="handleUpload">
          {{ dataStore.uploading ? t('common.loading') : t('data.uploadButton') }}
        </button>
      </div>
      <p v-if="error" class="error" style="margin-top: 8px">{{ error }}</p>
      <div v-if="uploadResult" style="margin-top: 8px">
        <p v-if="uploadResult.uploaded?.length" class="muted">
          ✅ {{ t('data.uploadedCount', { count: uploadResult.uploaded.length }) }}
        </p>
        <p v-if="uploadResult.skipped?.length" class="muted">
          ⏩ {{ t('data.skippedCount', { count: uploadResult.skipped.length }) }}
        </p>
      </div>
    </div>

    <!-- Dataset table -->
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div class="card-title" style="margin-bottom: 0">{{ t('data.datasets') }}</div>
        <button
          v-if="auth.isAdmin && dataStore.datasets.length"
          class="danger"
          style="padding: 4px 10px; font-size: 12px"
          @click="handleDeleteAll"
        >
          {{ t('data.deleteAll') }}
        </button>
      </div>
      <LoadingSpinner v-if="dataStore.loading" :label="t('common.loading')" />
      <EmptyState
        v-else-if="!dataStore.datasets.length"
        icon="📁"
        :message="t('empty.noDatasets')"
      />
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{{ t('data.fileName') }}</th>
              <th>{{ t('data.rows') }}</th>
              <th>{{ t('data.uploaded') }}</th>
              <th>{{ t('data.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ds in dataStore.datasets" :key="ds.id">
              <td>{{ ds.original_name }}</td>
              <td>{{ formatSize(ds.row_count) }}</td>
              <td>{{ formatDate(ds.uploaded_at) }}</td>
              <td>
                <div class="actions" style="margin-top: 0">
                  <button
                    class="secondary"
                    style="padding: 4px 10px; font-size: 12px"
                    @click="showPreview(ds)"
                  >
                    {{ t('data.preview') }}
                  </button>
                  <button
                    v-if="auth.isAdmin"
                    class="danger"
                    style="padding: 4px 10px; font-size: 12px"
                    @click="handleDelete(ds.id)"
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

    <!-- Preview modal -->
    <div v-if="previewData" class="modal-overlay" @click.self="previewData = null">
      <div class="modal-content">
        <div
          style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
          "
        >
          <div class="card-title" style="margin-bottom: 0">{{ previewName }}</div>
          <button
            class="secondary"
            style="padding: 4px 10px; font-size: 12px"
            :aria-label="t('ui.close')"
            @click="previewData = null"
          >
            ✕
          </button>
        </div>
        <p class="muted" style="margin-bottom: 8px">
          {{ t('data.columns') }}: {{ previewData.columns?.join(', ') }}
        </p>
        <div class="table-wrap" style="max-height: 400px; overflow-y: auto">
          <table>
            <thead>
              <tr>
                <th v-for="col in previewData.columns" :key="col">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in previewData.rows" :key="i">
                <td v-for="col in previewData.columns" :key="col">{{ row[col] ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
