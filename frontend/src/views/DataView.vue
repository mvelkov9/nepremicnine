<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { useDebounceFn } from '@vueuse/core'
  import { useI18n } from 'vue-i18n'
  import { useConfirm } from 'primevue/useconfirm'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import Dialog from 'primevue/dialog'
  import Tab from 'primevue/tab'
  import TabList from 'primevue/tablist'
  import TabPanel from 'primevue/tabpanel'
  import TabPanels from 'primevue/tabpanels'
  import Tabs from 'primevue/tabs'
  import EmptyState from '../components/EmptyState.vue'
  import PageHeader from '../components/PageHeader.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import AdminRunDetailPanel from '../components/admin/AdminRunDetailPanel.vue'
  import AdminWorkspaceHero from '../components/admin/AdminWorkspaceHero.vue'
  import DataDatasetLibrary from '../components/data/DataDatasetLibrary.vue'
  import DataUploadWorkspace from '../components/data/DataUploadWorkspace.vue'
  import { adminWorkspaceLinks } from '../constants/adminWorkspace'
  import { useExport } from '../composables/useExport'
  import { useServerTableState } from '../composables/useServerTableState'
  import { useToast } from '../composables/useToast'
  import { useAuthStore } from '../stores/auth'
  import { useDataStore } from '../stores/data'
  import type { UploadProgressContext } from '../stores/data'
  import { useWorkbenchStore } from '../stores/workbench'
  import type {
    DatasetPreviewData,
    DatasetRow,
    DatasetTablePageEvent,
    DatasetTableSortEvent,
    QualitySummary,
    TrainingDatasetSummary,
    UploadBatchResult,
    UploadCapacitySummary,
    UploadItem,
  } from '../features/data/types'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatDate as formatDateValue, formatNumber, formatPercent } from '../utils/format'

  const { t } = useI18n()
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const workbench = useWorkbenchStore()
  const confirmDialog = useConfirm()
  const { showToast } = useToast()
  const { exportToCSV } = useExport()

  const datasetSearchInput = ref('')
  const datasetTable = useServerTableState({
    page: '1',
    page_size: '10',
    sort: 'uploaded_at',
    order: 'desc',
    search: '',
  })

  const selectedFiles = ref<File[]>([])
  const uploadItems = ref<UploadItem[]>([])
  const uploadResult = ref<UploadBatchResult | null>(null)
  const uploadResetToken = ref(0)
  const previewData = ref<DatasetPreviewData | null>(null)
  const previewName = ref('')
  const previewVisible = ref(false)
  const error = ref('')
  const rescanning = ref(false)
  const selectedPrepareRunId = ref('')
  const dataTab = ref(auth.isAdmin ? 'upload' : 'library')

  const qualitySummary = computed(() => dataStore.qualitySummary as QualitySummary | null)
  const uploadCapacity = computed(() => dataStore.uploadCapacity as UploadCapacitySummary | null)
  const trainingDataset = computed(() => dataStore.trainingDataset as TrainingDatasetSummary | null)
  const datasets = computed(() => dataStore.datasets as DatasetRow[])
  const selectedPrepareRun = computed(() => workbench.selectedPrepareRun)

  const datasetFilterLabels = computed(() =>
    datasetTable.search.value ? [datasetTable.search.value] : [],
  )
  const datasetRows = computed(() => Number(dataStore.datasetsPerPage || 10))
  const datasetFirst = computed(() =>
    Math.max(0, (Number(dataStore.datasetsPage || 1) - 1) * datasetRows.value),
  )
  const datasetTotalRecords = computed(() => Number(dataStore.datasetsTotal || 0))

  const debouncedDatasetSearchSync = useDebounceFn((value: string) => {
    datasetTable.search.value = value
  }, 260)

  const summaryCards = computed(() => [
    {
      label: t('data.preparedDataset'),
      value: trainingDataset.value?.exists
        ? formatNumber(trainingDataset.value.rows || 0)
        : t('common.noData'),
      meta: trainingDataset.value?.exists
        ? trainingDataset.value.relative_path || t('common.noData')
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
          : '-',
      meta: t('data.referenceCoverageHint'),
    },
    {
      label: t('data.unresolvedRows'),
      value: formatNumber(qualitySummary.value?.unresolved_rows || 0),
      meta: t('data.qualityHint'),
    },
  ])

  const totalSelectedBytes = computed(() =>
    selectedFiles.value.reduce((total, file) => total + (file.size || 0), 0),
  )

  const maxUploadLabel = computed(() => {
    const limitBytes = uploadCapacity.value?.max_upload_size_bytes
    return limitBytes
      ? t('data.maxUploadValue', { size: formatFileSize(limitBytes) })
      : t('data.maxUploadUnknown')
  })

  const serverFreeLabel = computed(() => formatFileSize(uploadCapacity.value?.free_disk_bytes || 0))
  const recommendedUploadLabel = computed(() =>
    formatFileSize(uploadCapacity.value?.recommended_max_upload_bytes || 0),
  )
  const reserveLabel = computed(() => formatFileSize(uploadCapacity.value?.reserve_disk_bytes || 0))

  const capacityTone = computed(() => {
    const available = uploadCapacity.value?.recommended_max_upload_bytes || 0
    if (!available) return 'danger'
    if (totalSelectedBytes.value > available) return 'danger'
    if (available < 5 * 1024 ** 3) return 'warn'
    return 'success'
  })

  const capacityMessage = computed(() => {
    const available = uploadCapacity.value?.recommended_max_upload_bytes || 0
    if (!uploadCapacity.value) return t('data.capacityUnknown')
    if (!available) return t('data.capacityUnavailable')
    if (selectedFiles.value.length && totalSelectedBytes.value > available) {
      return t('data.capacityTooLow')
    }
    return t('data.capacityHealthy')
  })

  const uploadProgressLabel = computed(() =>
    t('data.uploadProgressValue', {
      progress: formatNumber(dataStore.uploadProgress || 0, { maximumFractionDigits: 0 }),
    }),
  )
  const heroStatusMessage = computed(() => {
    if (dataStore.uploading) return t('common.loading')
    if (selectedFiles.value.length) {
      return t('data.readyToUpload', { count: selectedFiles.value.length })
    }
    if (uploadResult.value?.uploaded?.length) {
      return t('data.uploadedCount', { count: uploadResult.value.uploaded.length })
    }
    if (uploadResult.value?.skipped?.length) {
      return t('data.skippedCount', { count: uploadResult.value.skipped.length })
    }
    return t('data.uploadEmptyState')
  })
  const heroStatusSeverity = computed(() => {
    if (dataStore.uploading) return 'warn'
    if (selectedFiles.value.length) return 'secondary'
    if (uploadResult.value?.uploaded?.length) return 'success'
    if (uploadResult.value?.skipped?.length) return 'warn'
    return 'secondary'
  })

  watch(
    () => datasetTable.search.value,
    (value) => {
      if (value !== datasetSearchInput.value) datasetSearchInput.value = value
    },
    { immediate: true },
  )

  watch(datasetSearchInput, (value) => {
    debouncedDatasetSearchSync(value)
  })

  watch(
    () => [
      datasetTable.state.page,
      datasetTable.state.page_size,
      datasetTable.state.sort,
      datasetTable.state.order,
      datasetTable.state.search,
    ],
    async () => {
      error.value = ''
      try {
        await fetchDatasetPage(
          datasetTable.page.value,
          datasetTable.pageSize.value,
          false,
          datasetTable.search.value,
          datasetTable.sort.value,
          datasetTable.order.value,
        )
      } catch (e) {
        error.value = getApiErrorMessage(e, t)
      }
    },
  )

  async function fetchDatasetPage(
    page = 1,
    perPage = 10,
    withSync = false,
    search = datasetTable.search.value,
    sort = datasetTable.sort.value,
    order: 'asc' | 'desc' = datasetTable.order.value,
  ) {
    await dataStore.fetchDatasets(withSync, false, { page, perPage, search, sort, order })
  }

  function refreshAdminDiagnosticsBackground() {
    if (!auth.isAdmin) return

    void dataStore.fetchQualitySummary().catch((e) => {
      if (!error.value) error.value = getApiErrorMessage(e, t)
    })

    void dataStore.fetchUploadCapacity().catch((e) => {
      if (!error.value) error.value = getApiErrorMessage(e, t)
    })
  }

  async function loadDataView() {
    const results = await Promise.allSettled([
      fetchDatasetPage(
        datasetTable.page.value,
        datasetTable.pageSize.value,
        false,
        datasetTable.search.value,
        datasetTable.sort.value,
        datasetTable.order.value,
      ),
      dataStore.fetchTrainingDataset(),
    ])

    const firstFailure = results.find((result) => result.status === 'rejected')
    if (firstFailure && firstFailure.status === 'rejected') {
      throw firstFailure.reason
    }

    refreshAdminDiagnosticsBackground()
  }

  async function initializePage() {
    error.value = ''
    const results = await Promise.allSettled([loadDataView(), workbench.fetchPrepareRuns()])

    const dataViewResult = results[0]
    if (dataViewResult.status === 'rejected') {
      throw dataViewResult.reason
    }
  }

  onMounted(async () => {
    try {
      await initializePage()
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  })

  async function loadPrepareRunDetail(jobId: string) {
    selectedPrepareRunId.value = jobId
    await workbench.fetchPrepareRunDetail(jobId)
  }

  watch(
    () => workbench.prepareRuns,
    (runs) => {
      if (!runs.length) return

      const resolvedRunId = runs.some((item) => item.id === selectedPrepareRunId.value)
        ? selectedPrepareRunId.value
        : runs[0].id

      if (!resolvedRunId) return

      if (selectedPrepareRunId.value !== resolvedRunId) {
        selectedPrepareRunId.value = resolvedRunId
      }

      if (selectedPrepareRun.value?.id !== resolvedRunId) {
        void loadPrepareRunDetail(resolvedRunId)
      }
    },
    { immediate: true },
  )

  function formatFileSize(bytes: number) {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB']
    const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
    const value = bytes / 1024 ** exponent
    return `${value >= 10 || exponent === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[exponent]}`
  }

  function getFileKey(file: File) {
    return `${file.name}-${file.size}-${file.lastModified}`
  }

  function createUploadItem(file: File): UploadItem {
    return {
      key: getFileKey(file),
      file,
      status: 'queued',
      progress: 0,
      uploadedNames: [],
      skippedNames: [],
      summary: '',
      errorMessage: '',
    }
  }

  function syncUploadItems(nextFiles: File[]) {
    const keys = new Set(nextFiles.map((file) => getFileKey(file)))
    const existingCompleted = uploadItems.value.filter(
      (item) => !keys.has(item.key) && item.status !== 'queued',
    )
    const nextItems = nextFiles.map(
      (file) =>
        uploadItems.value.find((item) => item.key === getFileKey(file)) || createUploadItem(file),
    )

    uploadItems.value = [...existingCompleted, ...nextItems]
  }

  function updateUploadItem(file: File, patch: Partial<UploadItem>) {
    const key = getFileKey(file)
    uploadItems.value = uploadItems.value.map((item) =>
      item.key === key ? { ...item, ...patch } : item,
    )
  }

  function resolveItemStatus(result: UploadBatchResult['fileResults'][number] | undefined) {
    if (result?.errorMessage) return 'error'
    const uploadedCount = result?.uploaded?.length || 0
    const skippedCount = result?.skipped?.length || 0
    if (uploadedCount && skippedCount) return 'partial'
    if (uploadedCount) return 'uploaded'
    if (skippedCount) return 'skipped'
    return 'uploaded'
  }

  function buildItemSummary(result: UploadBatchResult['fileResults'][number] | undefined) {
    if (result?.errorMessage) {
      return t('data.fileStatusErrorSummary')
    }
    const uploadedCount = result?.uploaded?.length || 0
    const skippedCount = result?.skipped?.length || 0
    if (uploadedCount && skippedCount) {
      return t('data.fileStatusPartialSummary', { uploaded: uploadedCount, skipped: skippedCount })
    }
    if (uploadedCount) {
      return t('data.fileStatusUploadedSummary', { count: uploadedCount })
    }
    if (skippedCount) {
      return t('data.fileStatusSkippedSummary', { count: skippedCount })
    }
    return ''
  }

  function handleFileProgress({ file, fileProgress, status }: UploadProgressContext) {
    updateUploadItem(file, {
      status,
      progress: fileProgress,
      summary: status === 'processing' ? t('data.fileStatusProcessingSummary') : '',
      errorMessage: '',
    })
  }

  function mergeSelectedFiles(filesLike: File[] | FileList) {
    const incomingFiles = Array.from(filesLike || [])
    const deduped = new Map(selectedFiles.value.map((file) => [getFileKey(file), file]))

    for (const file of incomingFiles) {
      deduped.set(getFileKey(file), file)
    }

    selectedFiles.value = Array.from(deduped.values())
    syncUploadItems(selectedFiles.value)
    uploadResult.value = null
    error.value = ''
  }

  function handleFileSelect(files: File[]) {
    mergeSelectedFiles(files)
  }

  function clearSelectedFiles() {
    selectedFiles.value = []
    uploadItems.value = uploadItems.value.filter((item) => item.status !== 'queued')
    uploadResetToken.value += 1
  }

  function removeSelectedFile(file: File) {
    const removedKey = getFileKey(file)
    selectedFiles.value = selectedFiles.value.filter(
      (selectedFile) => getFileKey(selectedFile) !== removedKey,
    )
    uploadItems.value = uploadItems.value.filter(
      (item) => item.key !== removedKey || item.status !== 'queued',
    )
    if (!selectedFiles.value.length) {
      uploadResetToken.value += 1
    }
  }

  async function startUpload() {
    if (!selectedFiles.value.length || dataStore.uploading) return
    error.value = ''
    uploadResult.value = null
    const filesToUpload = [...selectedFiles.value]
    for (const file of filesToUpload) {
      updateUploadItem(file, {
        status: 'queued',
        progress: 0,
        uploadedNames: [],
        skippedNames: [],
        summary: '',
        errorMessage: '',
      })
    }

    try {
      const result = await dataStore.uploadFiles(filesToUpload, {
        onFileProgress: handleFileProgress,
      })

      for (const file of filesToUpload) {
        const fileResult = result?.fileResults?.find(
          (entry) => getFileKey(entry.file) === getFileKey(file),
        )
        const fileUploadedNames = (fileResult?.uploaded || [])
          .map((item) => item.original_name)
          .filter(Boolean)
        const fileSkippedNames = fileResult?.skipped || []
        updateUploadItem(file, {
          status: resolveItemStatus(fileResult),
          progress: 100,
          uploadedNames: fileUploadedNames,
          skippedNames: fileSkippedNames,
          summary: buildItemSummary(fileResult),
          errorMessage: fileResult?.errorMessage || '',
        })
      }

      uploadResult.value = result
      const uploadedCount = result?.uploaded?.length || 0
      const skippedCount = result?.skipped?.length || 0
      const failedCount =
        result?.fileResults?.filter((entry) => Boolean(entry.errorMessage)).length || 0
      selectedFiles.value = []
      uploadResetToken.value += 1
      await dataStore.fetchTrainingDataset()
      refreshAdminDiagnosticsBackground()
      showToast(
        failedCount
          ? t('data.uploadPartialFailureToast', { failed: failedCount, uploaded: uploadedCount })
          : uploadedCount
            ? t('data.uploadSuccessToast', { count: uploadedCount })
            : t('data.uploadNoNewFilesToast', { count: skippedCount }),
        failedCount ? 'warning' : uploadedCount ? 'success' : 'warning',
      )
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
      for (const file of filesToUpload) {
        updateUploadItem(file, {
          status: 'error',
          errorMessage: getApiErrorMessage(e, t),
          summary: t('data.fileStatusErrorSummary'),
        })
      }
    }
  }

  async function showPreview(dataset: DatasetRow) {
    previewName.value = dataset.original_name
    error.value = ''
    try {
      previewData.value = (await dataStore.fetchPreview(dataset.id)) as DatasetPreviewData
      previewVisible.value = true
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  function handleDelete(row: DatasetRow) {
    confirmDialog.require({
      message: t('data.confirmDelete'),
      header: t('common.delete'),
      icon: 'pi pi-exclamation-triangle',
      rejectProps: { label: t('common.cancel'), severity: 'secondary', outlined: true },
      acceptProps: { label: t('common.delete'), severity: 'danger' },
      accept: async () => {
        try {
          await dataStore.deleteDataset(row.id)
          await dataStore.fetchTrainingDataset()
          refreshAdminDiagnosticsBackground()
        } catch (e) {
          error.value = getApiErrorMessage(e, t)
        }
      },
    })
  }

  function handleDeleteAll() {
    if (!dataStore.datasets.length) return
    confirmDialog.require({
      message: t('data.confirmDeleteCurrentPage'),
      header: t('data.deleteCurrentPage'),
      icon: 'pi pi-exclamation-triangle',
      rejectProps: { label: t('common.cancel'), severity: 'secondary', outlined: true },
      acceptProps: { label: t('data.deleteCurrentPage'), severity: 'danger' },
      accept: async () => {
        try {
          const remainingRecords = Math.max(
            0,
            datasetTotalRecords.value - dataStore.datasets.length,
          )
          const maxPageAfterDelete = Math.max(1, Math.ceil(remainingRecords / datasetRows.value))
          const nextPage = Math.min(datasetTable.page.value, maxPageAfterDelete)

          await dataStore.deleteAllDatasets()
          await fetchDatasetPage(
            nextPage,
            datasetTable.pageSize.value,
            false,
            datasetTable.search.value,
            datasetTable.sort.value,
            datasetTable.order.value,
          )
          if (String(nextPage) !== datasetTable.state.page) {
            await datasetTable.patchState({ page: String(nextPage) })
          }
          await dataStore.fetchTrainingDataset()
          refreshAdminDiagnosticsBackground()
        } catch (e) {
          error.value = getApiErrorMessage(e, t)
        }
      },
    })
  }

  async function handleRescan() {
    if (rescanning.value) return
    error.value = ''
    rescanning.value = true
    try {
      const result = await dataStore.rescanDatasets()
      showToast(
        t('data.rescanSuccessToast', {
          indexed: Number(result?.indexed || 0),
          removed: Number(result?.deleted_stale || 0),
        }),
        'success',
      )
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    } finally {
      rescanning.value = false
    }
  }

  function clearDatasetFilters() {
    datasetSearchInput.value = ''
    datasetTable.resetState()
  }

  function exportDatasets() {
    exportToCSV(
      datasets.value.map((item) => ({
        original_name: item.original_name,
        relative_path: item.relative_path,
        source_type: item.source_type,
        row_count: item.row_count,
        uploaded_at: item.uploaded_at,
      })),
      'dataset-library.csv',
    )
  }

  function formatDate(iso: string) {
    return formatDateValue(iso, { dateStyle: 'medium' })
  }

  async function handleDatasetPage(event: DatasetTablePageEvent) {
    error.value = ''
    await datasetTable.patchState({
      page: String(Number(event?.page ?? 0) + 1),
      page_size: String(Number(event?.rows ?? datasetRows.value)),
    })
  }

  async function handleDatasetSort(event: DatasetTableSortEvent) {
    const sortField =
      typeof event?.sortField === 'string' ? event.sortField : datasetTable.sort.value
    const sortOrder = event?.sortOrder === 1 ? 'asc' : 'desc'
    await datasetTable.patchState({
      page: '1',
      sort: sortField,
      order: sortOrder,
    })
  }
</script>

<template>
  <div class="data-page">
    <AdminWorkspaceHero
      :eyebrow="t('nav.data')"
      :title="t('data.workspaceTitle')"
      :description="t('data.workspaceBody')"
      :metrics="summaryCards"
      :links="adminWorkspaceLinks"
      :status="heroStatusMessage"
      :status-severity="heroStatusSeverity"
    >
      <template #actions>
        <SavedWorkspaceMenu
          page="data"
          :state="{
            page: 'data',
            tab: dataTab,
            filters: {
              search: datasetTable.state.search,
              page: datasetTable.state.page,
              page_size: datasetTable.state.page_size,
              sort: datasetTable.state.sort,
              order: datasetTable.state.order,
            },
          }"
        />
      </template>
    </AdminWorkspaceHero>

    <Tabs v-if="auth.isAdmin" v-model:value="dataTab" class="data-tabs">
      <TabList>
        <Tab value="upload">{{ t('data.upload') }}</Tab>
        <Tab value="quality">{{ t('data.qualitySummary') }}</Tab>
        <Tab value="library">{{ t('common.overview') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="upload">
          <section class="data-admin-grid data-tab-content">
            <DataUploadWorkspace
              :eyebrow="t('data.upload')"
              :title="t('data.uploadTitle')"
              :description="t('data.uploadHint')"
              :selected-files="selectedFiles"
              :upload-items="uploadItems"
              :upload-result="uploadResult"
              :uploading="dataStore.uploading"
              :reset-token="uploadResetToken"
              :max-upload-label="maxUploadLabel"
              :server-free-label="serverFreeLabel"
              :recommended-upload-label="recommendedUploadLabel"
              :reserve-label="reserveLabel"
              :capacity-tone="capacityTone"
              :capacity-message="capacityMessage"
              :upload-progress="dataStore.uploadProgress || 0"
              :upload-progress-label="uploadProgressLabel"
              @select="handleFileSelect"
              @clear="clearSelectedFiles"
              @start="startUpload"
              @remove="removeSelectedFile"
            />

            <aside class="data-side-stack">
              <AdminRunDetailPanel
                :eyebrow="t('nav.prepare')"
                :title="t('workbench.recentPrepareRuns')"
                :description="t('workbench.prepareRunDetailHint')"
                run-type="prepare"
                :runs="workbench.prepareRuns.slice(0, 8)"
                :selected-run-id="selectedPrepareRunId"
                :selected-run="selectedPrepareRun"
                :loading="workbench.prepareRunDetailLoading"
                :error="workbench.prepareRunDetailError || workbench.prepareRunsError"
                @select="loadPrepareRunDetail"
              />
            </aside>
          </section>
        </TabPanel>

        <TabPanel value="quality">
          <section class="quality-grid quality-grid--split data-tab-content">
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
                :rows="10"
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
                :rows="10"
                size="small"
                striped-rows
                responsive-layout="scroll"
              >
                <Column field="canonical" :header="t('data.canonicalLabel')" sortable />
                <Column field="variant_count" :header="t('data.variantCount')" sortable />
                <Column :header="t('data.variants')">
                  <template #body="{ data }">
                    {{ data.variants?.join(', ') || '-' }}
                  </template>
                </Column>
              </DataTable>
            </article>
          </section>
        </TabPanel>

        <TabPanel value="library">
          <DataDatasetLibrary
            class="dataset-library-card data-tab-content"
            :page="'data'"
            :state="{
              page: 'data',
              tab: dataTab,
              filters: {
                search: datasetTable.state.search,
                page: datasetTable.state.page,
                page_size: datasetTable.state.page_size,
                sort: datasetTable.state.sort,
                order: datasetTable.state.order,
              },
            }"
            :search-value="datasetSearchInput"
            :datasets="datasets"
            :loading="dataStore.loading"
            :first="datasetFirst"
            :rows="datasetRows"
            :total-records="datasetTotalRecords"
            :sort-field="datasetTable.sort.value"
            :sort-order="datasetTable.order.value"
            :active-filters="datasetFilterLabels"
            :format-date="formatDate"
            :can-delete="auth.isAdmin"
            @update:search-value="datasetSearchInput = $event"
            @export="exportDatasets"
            @clear="clearDatasetFilters"
            @page="handleDatasetPage"
            @sort="handleDatasetSort"
            @preview="showPreview"
            @delete="handleDelete"
          >
            <template #toolbar-actions>
              <Button
                severity="secondary"
                outlined
                icon="pi pi-refresh"
                :label="t('data.rescanUploads')"
                :loading="rescanning"
                @click="handleRescan"
              />
              <Button
                v-if="datasets.length"
                severity="danger"
                outlined
                icon="pi pi-trash"
                :label="t('data.deleteCurrentPage')"
                @click="handleDeleteAll"
              />
            </template>
          </DataDatasetLibrary>
        </TabPanel>
      </TabPanels>
    </Tabs>

    <DataDatasetLibrary
      v-else
      class="dataset-library-card"
      :page="'data'"
      :state="{
        page: 'data',
        filters: {
          search: datasetTable.state.search,
          page: datasetTable.state.page,
          page_size: datasetTable.state.page_size,
          sort: datasetTable.state.sort,
          order: datasetTable.state.order,
        },
      }"
      :search-value="datasetSearchInput"
      :datasets="datasets"
      :loading="dataStore.loading"
      :first="datasetFirst"
      :rows="datasetRows"
      :total-records="datasetTotalRecords"
      :sort-field="datasetTable.sort.value"
      :sort-order="datasetTable.order.value"
      :active-filters="datasetFilterLabels"
      :format-date="formatDate"
      :can-delete="false"
      @update:search-value="datasetSearchInput = $event"
      @export="exportDatasets"
      @clear="clearDatasetFilters"
      @page="handleDatasetPage"
      @sort="handleDatasetSort"
      @preview="showPreview"
    />

    <div v-if="error" class="state-card state-card-stack" role="alert">
      <EmptyState icon="pi pi-exclamation-triangle" :message="error" />
      <div class="state-card-actions">
        <Button
          size="small"
          severity="secondary"
          outlined
          icon="pi pi-refresh"
          :label="t('common.retry')"
          @click="initializePage"
        />
      </div>
    </div>

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
        <p class="muted">
          {{ t('data.previewRows', { count: formatNumber(previewData.total_rows || 0) }) }}
        </p>
        <DataTable
          :value="previewData.rows || []"
          scrollable
          scroll-height="420px"
          size="small"
          striped-rows
          responsive-layout="scroll"
        >
          <Column v-for="col in previewData.columns" :key="col" :field="col" :header="col">
            <template #body="{ data }">{{ data[col] ?? '-' }}</template>
          </Column>
        </DataTable>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
  .data-page,
  .data-admin-grid,
  .data-side-stack,
  .quality-grid {
    display: grid;
    gap: var(--space-section);
  }

  .data-page {
    --page-accent: var(--accent);
    --page-accent-2: var(--secondary);
  }

  .data-tabs,
  .data-tab-content {
    display: grid;
    gap: 1rem;
  }

  .data-tabs :deep(.p-tablist) {
    padding: 0.35rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 20%);
    border-radius: var(--radius-lg);
    background: color-mix(in srgb, var(--surface-strong) 92%, var(--primary-overlay) 8%);
    box-shadow: 0 10px 22px color-mix(in srgb, var(--shadow-color) 8%, transparent);
    overflow-x: auto;
    scrollbar-width: thin;
  }

  .data-tabs :deep(.p-tabpanels) {
    padding-top: 0.15rem;
  }

  .data-admin-grid {
    grid-template-columns: 1fr;
    align-items: start;
  }

  .data-side-stack,
  .quality-grid,
  .state-card-stack {
    gap: 1rem;
  }

  .quality-grid--split {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quality-card {
    display: grid;
    gap: 1rem;
    padding: 1.1rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--page-accent) 14%, transparent),
        transparent 30%
      ),
      radial-gradient(
        circle at 12% -20%,
        color-mix(in srgb, var(--page-accent-2) 10%, transparent),
        transparent 28%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--glass-highlight) 90%, transparent),
        transparent 34%
      ),
      var(--surface-panel);
    box-shadow: var(--accent-shadow, var(--shadow-sm));
  }

  .preview-dialog {
    display: grid;
    gap: 0.75rem;
  }

  .preview-dialog .muted {
    margin: 0;
    padding: 0.75rem 0.9rem;
    border-radius: var(--radius-sm);
    background: color-mix(
      in srgb,
      var(--surface-panel-muted, var(--surface-soft)) 92%,
      transparent
    );
    border: 1px solid color-mix(in srgb, var(--border) 62%, var(--page-accent) 38%);
  }

  .state-card-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }

  @media (max-width: 1100px) {
    .quality-grid--split {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .quality-card {
      padding: 1rem;
    }
  }
</style>
