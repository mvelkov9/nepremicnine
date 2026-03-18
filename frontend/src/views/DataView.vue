<script setup>
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Dialog from 'primevue/dialog'
  import InputText from 'primevue/inputtext'
  import Tag from 'primevue/tag'
  import AppDataTable from '../components/AppDataTable.vue'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { useConfirmDialog } from '../composables/useConfirmDialog'
  import { useToast } from '../composables/useToast'
  import { useAuthStore } from '../stores/auth'
  import { useDataStore } from '../stores/data'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatDate as formatDateValue, formatNumber, formatPercent } from '../utils/format'

  const { t } = useI18n()
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const { confirmAction } = useConfirmDialog()
  const { showToast } = useToast()

  const fileInput = ref(null)
  const previewData = ref(null)
  const previewName = ref('')
  const previewVisible = ref(false)
  const uploadResult = ref(null)
  const error = ref('')
  const datasetFilter = ref('')

  const unresolvedColumns = computed(() => [
    { key: 'label', label: t('dashboard.municipality'), sortable: true },
    { key: 'count', label: t('dashboard.transactions'), sortable: true },
  ])

  const aliasColumns = computed(() => [
    { key: 'canonical', label: t('data.canonicalLabel'), sortable: true },
    { key: 'variant_count', label: t('data.variantCount'), sortable: true },
    { key: 'variants', label: t('data.variants') },
  ])

  const datasetColumns = computed(() => [
    { key: 'original_name', label: t('data.fileName'), sortable: true },
    { key: 'relative_path', label: t('data.relativePath'), sortable: true },
    { key: 'row_count', label: t('data.rows'), sortable: true },
    { key: 'uploaded_at', label: t('data.uploaded'), sortable: true },
    { key: 'actions', label: t('data.actions') },
  ])

  const previewColumns = computed(() =>
    (previewData.value?.columns || []).map((column) => ({ key: column, label: column })),
  )

  const qualitySummary = computed(() => dataStore.qualitySummary)
  const filteredDatasets = computed(() => {
    const query = datasetFilter.value.trim().toLowerCase()
    if (!query) return dataStore.datasets
    return dataStore.datasets.filter((item) =>
      [item.original_name, item.relative_path, item.source_type].some((value) =>
        String(value || '')
          .toLowerCase()
          .includes(query),
      ),
    )
  })

  const summaryCards = computed(() => [
    {
      label: t('data.preparedDataset'),
      value: dataStore.trainingDataset?.exists
        ? formatNumber(dataStore.trainingDataset.rows || 0)
        : t('common.noData'),
      meta: dataStore.trainingDataset?.exists
        ? dataStore.trainingDataset.relative_path
        : t('data.noPreparedDataset'),
    },
    {
      label: t('data.coveredMunicipalities'),
      value: formatNumber(qualitySummary.value?.covered_municipalities || 0),
      meta:
        qualitySummary.value?.canonical_reference_total != null
          ? `${formatNumber(qualitySummary.value.covered_municipalities || 0)} / ${formatNumber(qualitySummary.value.canonical_reference_total || 0)}`
          : t('common.noData'),
    },
    {
      label: t('data.coverageRatio'),
      value:
        qualitySummary.value?.coverage_ratio != null
          ? formatPercent(qualitySummary.value.coverage_ratio)
          : '—',
      meta: t('data.referenceCoverageHint'),
    },
    {
      label: t('data.unresolvedRows'),
      value: formatNumber(qualitySummary.value?.unresolved_rows || 0),
      meta: t('data.qualityHint'),
    },
  ])

  async function loadDataView() {
    await Promise.all([
      dataStore.fetchDatasets(),
      dataStore.fetchTrainingDataset(),
      auth.isAdmin ? dataStore.fetchQualitySummary() : Promise.resolve(),
    ])
  }

  onMounted(async () => {
    try {
      await loadDataView()
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  })

  async function handleUpload() {
    const files = fileInput.value?.files
    if (!files?.length) return
    error.value = ''
    uploadResult.value = null
    try {
      const result = await dataStore.uploadFiles(files)
      uploadResult.value = result
      fileInput.value.value = ''
      await Promise.all([dataStore.fetchTrainingDataset(), dataStore.fetchQualitySummary()])
      showToast(
        t('data.uploadSuccess', {
          uploaded: result.uploaded?.length || 0,
          skipped: result.skipped?.length || 0,
        }),
        'success',
      )
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function showPreview(dataset) {
    previewName.value = dataset.original_name
    error.value = ''
    try {
      previewData.value = await dataStore.fetchPreview(dataset.id)
      previewVisible.value = true
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function handleDelete(id) {
    error.value = ''
    const confirmed = await confirmAction({
      header: t('common.confirm'),
      message: t('data.confirmDelete'),
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
    })
    if (!confirmed) return
    try {
      await dataStore.deleteDataset(id)
      await Promise.all([dataStore.fetchTrainingDataset(), dataStore.fetchQualitySummary()])
      showToast(t('data.deleteSuccess'), 'success')
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function handleDeleteAll() {
    if (!dataStore.datasets.length) return
    error.value = ''
    const datasetCount = dataStore.datasets.length
    const confirmed = await confirmAction({
      header: t('common.confirm'),
      message: t('data.confirmDeleteAll'),
      acceptLabel: t('data.deleteAll'),
      rejectLabel: t('common.cancel'),
    })
    if (!confirmed) return
    try {
      await dataStore.deleteAllDatasets()
      await Promise.all([dataStore.fetchTrainingDataset(), dataStore.fetchQualitySummary()])
      showToast(t('data.deleteAllSuccess', { count: datasetCount }), 'success')
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  function formatDate(iso) {
    return formatDateValue(iso, { dateStyle: 'medium' })
  }

  function formatSize(rows) {
    return formatNumber(rows)
  }
</script>

<template>
  <div class="data-page">
    <section class="card">
      <PageHeader
        :eyebrow="t('nav.data')"
        :title="t('data.workspaceTitle')"
        :description="t('data.workspaceBody')"
      />
    </section>

    <section v-if="auth.isAdmin" class="card admin-upload">
      <PageHeader
        compact
        :eyebrow="t('data.upload')"
        :title="t('data.uploadTitle')"
        :description="t('data.uploadHint')"
      >
        <template #actions>
          <Tag severity="secondary" :value="t('data.maxUpload')" />
        </template>
      </PageHeader>

      <div class="upload-shell">
        <input
          ref="fileInput"
          type="file"
          multiple
          accept=".csv,.zip"
          :aria-label="t('data.upload')"
        />
        <Button
          icon="pi pi-upload"
          :loading="dataStore.uploading"
          :label="dataStore.uploading ? t('common.loading') : t('data.uploadButton')"
          @click="handleUpload"
        />
      </div>

      <div v-if="uploadResult" class="upload-result">
        <Tag
          v-if="uploadResult.uploaded?.length"
          severity="success"
          :value="t('data.uploadedCount', { count: uploadResult.uploaded.length })"
        />
        <Tag
          v-if="uploadResult.skipped?.length"
          severity="warn"
          :value="t('data.skippedCount', { count: uploadResult.skipped.length })"
        />
      </div>
    </section>

    <section v-if="auth.isAdmin" class="metrics-grid">
      <MetricCard
        v-for="card in summaryCards"
        :key="card.label"
        :label="card.label"
        :value="card.value"
        :meta="card.meta"
      />
    </section>

    <section v-if="auth.isAdmin" class="quality-grid">
      <article class="card">
        <PageHeader
          compact
          :eyebrow="t('data.qualitySummary')"
          :title="t('data.unresolvedMunicipalities')"
          :description="t('data.unresolvedHint')"
        />

        <AppDataTable
          :rows="qualitySummary?.unresolved_labels || []"
          :columns="unresolvedColumns"
          row-key="label"
          :page-size="6"
          :empty-message="t('empty.noResults')"
        />
      </article>

      <article class="card">
        <PageHeader
          compact
          :eyebrow="t('data.qualitySummary')"
          :title="t('data.aliasCollisions')"
          :description="t('data.aliasHint')"
        />

        <AppDataTable
          :rows="qualitySummary?.alias_collisions || []"
          :columns="aliasColumns"
          row-key="canonical"
          :page-size="6"
          :empty-message="t('empty.noResults')"
        >
          <template #cell-variants="{ row }">
            {{ row.variants?.join(', ') || '—' }}
          </template>
        </AppDataTable>
      </article>
    </section>

    <section class="card">
      <PageHeader
        compact
        :eyebrow="t('data.datasets')"
        :title="t('data.datasetLibrary')"
        :description="t('data.datasetLibraryHint')"
      >
        <template #actions>
          <div class="table-actions">
            <span class="p-input-icon-left">
              <i class="pi pi-search"></i>
              <InputText v-model="datasetFilter" :placeholder="t('common.search')" />
            </span>
            <Button
              v-if="auth.isAdmin && dataStore.datasets.length"
              severity="danger"
              outlined
              icon="pi pi-trash"
              :label="t('data.deleteAll')"
              @click="handleDeleteAll"
            />
          </div>
        </template>
      </PageHeader>

      <LoadingSpinner v-if="dataStore.loading" :label="t('common.loading')" />
      <EmptyState
        v-else-if="!dataStore.datasets.length"
        icon="📁"
        :message="t('empty.noDatasets')"
      />
      <AppDataTable
        v-else
        :rows="filteredDatasets"
        :columns="datasetColumns"
        row-key="id"
        :page-size="10"
        :empty-message="t('empty.noDatasets')"
      >
        <template #cell-row_count="{ row }">{{ formatSize(row.row_count) }}</template>
        <template #cell-uploaded_at="{ row }">{{ formatDate(row.uploaded_at) }}</template>
        <template #cell-actions="{ row }">
          <div class="row-actions">
            <Button
              size="small"
              severity="secondary"
              outlined
              icon="pi pi-eye"
              :label="t('data.preview')"
              @click="showPreview(row)"
            />
            <Button
              v-if="auth.isAdmin"
              size="small"
              severity="danger"
              outlined
              icon="pi pi-trash"
              :label="t('common.delete')"
              @click="handleDelete(row.id)"
            />
          </div>
        </template>
      </AppDataTable>
    </section>

    <p v-if="error" class="error-text">{{ error }}</p>

    <Dialog
      v-model:visible="previewVisible"
      modal
      maximizable
      :header="previewName || t('data.preview')"
      class="dataset-preview-dialog"
      :style="{ width: 'min(96vw, 1200px)' }"
    >
      <div v-if="previewData" class="preview-dialog">
        <p class="muted">{{ t('data.columns') }}: {{ previewData.columns?.join(', ') }}</p>
        <AppDataTable
          :rows="previewData.rows || []"
          :columns="previewColumns"
          row-key="__previewIndex"
          :page-size="12"
          :empty-message="t('empty.noResults')"
        />
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
  .data-page,
  .metrics-grid,
  .quality-grid {
    display: grid;
    gap: 1rem;
  }

  .metrics-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .quality-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .admin-upload {
    display: grid;
    gap: 1rem;
  }

  .upload-shell,
  .table-actions,
  .row-actions,
  .upload-result {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .upload-shell input[type='file'] {
    min-width: min(100%, 28rem);
  }

  .preview-dialog {
    display: grid;
    gap: 0.75rem;
  }

  @media (max-width: 960px) {
    .metrics-grid,
    .quality-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
