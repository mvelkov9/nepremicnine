<script setup lang="ts">
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useConfirm } from 'primevue/useconfirm'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { useAuthStore } from '../stores/auth'
  import { useDataStore } from '../stores/data'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatDate as formatDateValue, formatNumber, formatPercent } from '../utils/format'

  const { t } = useI18n()
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const confirmDialog = useConfirm()

  const fileInput = ref(null)
  const previewData = ref(null)
  const previewName = ref('')
  const previewVisible = ref(false)
  const uploadResult = ref(null)
  const error = ref('')
  const datasetFilter = ref('')

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

  async function handleUpload(event: any) {
    const files = event.files
    if (!files?.length) return
    error.value = ''
    uploadResult.value = null
    try {
      const result = await dataStore.uploadFiles(files)
      uploadResult.value = result
      fileInput.value?.clear()
      await Promise.all([dataStore.fetchTrainingDataset(), dataStore.fetchQualitySummary()])
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

  function handleDelete(id: number) {
    confirmDialog.require({
      message: t('data.confirmDelete'),
      header: t('common.delete'),
      icon: 'pi pi-exclamation-triangle',
      rejectProps: { label: t('common.cancel'), severity: 'secondary', outlined: true },
      acceptProps: { label: t('common.delete'), severity: 'danger' },
      accept: async () => {
        try {
          await dataStore.deleteDataset(id)
          await Promise.all([dataStore.fetchTrainingDataset(), dataStore.fetchQualitySummary()])
        } catch (e) {
          error.value = getApiErrorMessage(e, t)
        }
      },
    })
  }

  function handleDeleteAll() {
    if (!dataStore.datasets.length) return
    confirmDialog.require({
      message: t('data.confirmDeleteAll'),
      header: t('data.deleteAll'),
      icon: 'pi pi-exclamation-triangle',
      rejectProps: { label: t('common.cancel'), severity: 'secondary', outlined: true },
      acceptProps: { label: t('data.deleteAll'), severity: 'danger' },
      accept: async () => {
        try {
          await dataStore.deleteAllDatasets()
          await Promise.all([dataStore.fetchTrainingDataset(), dataStore.fetchQualitySummary()])
        } catch (e) {
          error.value = getApiErrorMessage(e, t)
        }
      },
    })
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
    <section class="card admin-hero data-hero">
      <PageHeader
        :eyebrow="t('nav.data')"
        :title="t('data.workspaceTitle')"
        :description="t('data.workspaceBody')"
      />
    </section>

    <section v-if="auth.isAdmin" class="card admin-upload upload-card">
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
        <div class="upload-copy">
          <strong>{{ t('data.uploadTitle') }}</strong>
          <p class="muted">{{ t('data.uploadHint') }}</p>
        </div>
        <FileUpload
          ref="fileInput"
          mode="basic"
          multiple
          accept=".csv,.zip"
          :auto="false"
          choose-icon="pi pi-upload"
          :choose-label="t('data.uploadButton')"
          :aria-label="t('data.upload')"
          @select="handleUpload"
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
      <article class="card quality-card">
        <PageHeader
          compact
          :eyebrow="t('data.qualitySummary')"
          :title="t('data.unresolvedMunicipalities')"
          :description="t('data.unresolvedHint')"
        />

        <DataTable
          :value="qualitySummary?.unresolved_labels || []"
          paginator
          :rows="6"
          size="small"
          striped-rows
          responsive-layout="scroll"
        >
          <Column field="label" :header="t('dashboard.municipality')" sortable />
          <Column field="count" :header="t('dashboard.transactions')" sortable />
        </DataTable>
      </article>

      <article class="card quality-card">
        <PageHeader
          compact
          :eyebrow="t('data.qualitySummary')"
          :title="t('data.aliasCollisions')"
          :description="t('data.aliasHint')"
        />

        <DataTable
          :value="qualitySummary?.alias_collisions || []"
          paginator
          :rows="6"
          size="small"
          striped-rows
          responsive-layout="scroll"
        >
          <Column field="canonical" :header="t('data.canonicalLabel')" sortable />
          <Column field="variant_count" :header="t('data.variantCount')" sortable />
          <Column :header="t('data.variants')">
            <template #body="{ data }">
              {{ data.variants?.join(', ') || '—' }}
            </template>
          </Column>
        </DataTable>
      </article>
    </section>

    <section class="card dataset-library-card">
      <PageHeader
        compact
        :eyebrow="t('data.datasets')"
        :title="t('data.datasetLibrary')"
        :description="t('data.datasetLibraryHint')"
      >
        <template #actions>
          <div class="table-actions">
            <IconField class="search-field">
              <InputIcon class="pi pi-search" />
              <InputText v-model="datasetFilter" :placeholder="t('common.search')" />
            </IconField>
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
      <DataTable
        v-else
        :value="filteredDatasets"
        paginator
        :rows="10"
        size="small"
        striped-rows
        responsive-layout="scroll"
      >
        <Column field="original_name" :header="t('data.fileName')" sortable />
        <Column field="relative_path" :header="t('data.relativePath')" sortable />
        <Column field="row_count" :header="t('data.rows')" sortable>
          <template #body="{ data }">{{ formatSize(data.row_count) }}</template>
        </Column>
        <Column field="uploaded_at" :header="t('data.uploaded')" sortable>
          <template #body="{ data }">{{ formatDate(data.uploaded_at) }}</template>
        </Column>
        <Column :header="t('data.actions')">
          <template #body="{ data }">
            <div class="row-actions">
              <Button
                size="small"
                severity="secondary"
                outlined
                icon="pi pi-eye"
                :label="t('data.preview')"
                @click="showPreview(data)"
              />
              <Button
                v-if="auth.isAdmin"
                size="small"
                severity="danger"
                outlined
                icon="pi pi-trash"
                :label="t('common.delete')"
                @click="handleDelete(data.id)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
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
        <DataTable
          :value="previewData.rows || []"
          scrollable
          scroll-height="420px"
          size="small"
          striped-rows
          responsive-layout="scroll"
        >
          <Column v-for="col in previewData.columns" :key="col" :field="col" :header="col">
            <template #body="{ data }">{{ data[col] ?? '—' }}</template>
          </Column>
        </DataTable>
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

  .data-hero,
  .upload-card,
  .dataset-library-card,
  .quality-card {
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

  .upload-shell {
    justify-content: space-between;
    padding: 0.3rem 0;
  }

  .upload-copy {
    display: grid;
    gap: 0.3rem;
    max-width: 42rem;
  }

  .upload-copy strong {
    font-size: 1rem;
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

  .search-field {
    width: min(100%, 22rem);
  }

  .row-actions {
    align-items: stretch;
  }

  .row-actions :deep(.p-button) {
    justify-content: center;
  }

  .preview-dialog .muted {
    padding: 0.75rem 0.9rem;
    border-radius: 1rem;
    background: color-mix(in srgb, var(--surface-panel-muted, var(--surface-soft)) 92%, transparent);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
  }

  @media (max-width: 960px) {
    .metrics-grid,
    .quality-grid {
      grid-template-columns: 1fr;
    }

    .upload-shell {
      align-items: stretch;
    }

    .table-actions,
    .row-actions {
      display: grid;
      grid-template-columns: 1fr;
      width: 100%;
    }

    .search-field,
    .row-actions :deep(.p-button),
    .table-actions :deep(.p-button) {
      width: 100%;
    }
  }
</style>
