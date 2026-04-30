<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useDebounceFn } from '@vueuse/core'
  import { useI18n } from 'vue-i18n'
  import { useConfirm } from 'primevue/useconfirm'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import Dialog from 'primevue/dialog'
  import Skeleton from 'primevue/skeleton'
  import Tab from 'primevue/tab'
  import TabList from 'primevue/tablist'
  import TabPanel from 'primevue/tabpanel'
  import TabPanels from 'primevue/tabpanels'
  import Tabs from 'primevue/tabs'
  import EmptyState from '../components/EmptyState.vue'
  import MetricCard from '../components/MetricCard.vue'
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
  import { readQueryString, readQueryTab } from '../utils/routeQuery'
  import { formatDate as formatDateValue, formatNumber, formatPercent } from '../utils/format'

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
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
  const dataTabs = ['upload', 'quality', 'library'] as const
  const selectedPrepareRunId = ref(readQueryString(route.query.run) || '')
  const dataTab = ref(
    auth.isAdmin
      ? readQueryTab(route.query.tab, dataTabs, 'upload')
      : readQueryTab(route.query.tab, dataTabs, 'library'),
  )
  const datasetPageLoaded = ref(false)
  const datasetPageRequestKey = ref('')
  const qualitySummaryLoaded = ref(false)
  const uploadCapacityLoaded = ref(false)
  const trainingDatasetLoaded = ref(false)
  const prepareRunsLoaded = ref(false)
  const prepareRunsLoading = ref(false)

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

  const qualityOverviewCards = computed(() => [
    {
      label: t('data.coverageRatio'),
      value:
        qualitySummary.value?.coverage_ratio != null
          ? formatPercent(qualitySummary.value.coverage_ratio)
          : '-',
      meta:
        qualitySummary.value?.canonical_reference_total != null
          ? `${formatNumber(qualitySummary.value.covered_municipalities || 0)} / ${formatNumber(qualitySummary.value.canonical_reference_total || 0)}`
          : t('data.referenceCoverageHint'),
    },
    {
      label: t('data.unresolvedMunicipalities'),
      value: formatNumber(qualitySummary.value?.unresolved_labels?.length || 0),
      meta: t('data.unresolvedHint'),
    },
    {
      label: t('data.aliasCollisions'),
      value: formatNumber(qualitySummary.value?.alias_collisions?.length || 0),
      meta: t('data.aliasHint'),
    },
    {
      label: t('data.preparedDataset'),
      value: trainingDataset.value?.exists
        ? formatNumber(trainingDataset.value.rows || 0)
        : t('common.noData'),
      meta: trainingDataset.value?.exists
        ? trainingDataset.value.relative_path || t('common.noData')
        : t('data.noPreparedDataset'),
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

  function syncPrepareRunFromRoute(query = route.query) {
    const nextRunId = readQueryString(query.run)
    if (!nextRunId || selectedPrepareRunId.value === nextRunId) return
    selectedPrepareRunId.value = nextRunId
    if (auth.isAdmin && dataTab.value !== 'upload') {
      dataTab.value = 'upload'
    }
  }

  function syncPrepareRunToRoute(jobId: string) {
    const currentRunId = readQueryString(route.query.run) || ''
    if (currentRunId === jobId) return
    void router.replace({
      query: {
        ...route.query,
        ...(jobId ? { run: jobId } : {}),
      },
    })
  }

  watch(
    () => route.query.tab,
    () => {
      const nextTab = readQueryTab(route.query.tab, dataTabs, auth.isAdmin ? 'upload' : 'library')
      if (dataTab.value !== nextTab) dataTab.value = nextTab
    },
    { immediate: true },
  )

  watch(
    () => route.query.run,
    () => {
      syncPrepareRunFromRoute(route.query)
      const requestedRunId = readQueryString(route.query.run)
      if (
        auth.isAdmin &&
        requestedRunId &&
        (prepareRunsLoaded.value || workbench.prepareRuns.length)
      ) {
        void ensureSelectedPrepareRunLoaded(false, requestedRunId)
      }
    },
    { immediate: true },
  )

  watch(dataTab, (tab) => {
    const currentTab = readQueryTab(route.query.tab, dataTabs, auth.isAdmin ? 'upload' : 'library')
    if (currentTab !== tab) {
      void router.replace({ query: { ...route.query, tab } })
    }
    void loadActiveDataTabData()
  })

  watch(datasetSearchInput, (value) => {
    debouncedDatasetSearchSync(value)
  })

  function handleBackgroundError(cause: unknown) {
    if (!error.value) {
      error.value = getApiErrorMessage(cause, t)
    }
  }

  watch(
    () => [
      datasetTable.state.page,
      datasetTable.state.page_size,
      datasetTable.state.sort,
      datasetTable.state.order,
      datasetTable.state.search,
    ],
    async () => {
      if (dataTab.value !== 'library') return
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
    datasetPageLoaded.value = true
    datasetPageRequestKey.value = JSON.stringify({ page, perPage, search, sort, order })
  }

  function currentDatasetPageRequestKey() {
    return JSON.stringify({
      page: datasetTable.page.value,
      perPage: datasetTable.pageSize.value,
      search: datasetTable.search.value,
      sort: datasetTable.sort.value,
      order: datasetTable.order.value,
    })
  }

  async function ensureDatasetPageLoaded(force = false) {
    if (
      !force &&
      datasetPageLoaded.value &&
      datasetPageRequestKey.value === currentDatasetPageRequestKey()
    ) {
      return
    }
    await fetchDatasetPage(
      datasetTable.page.value,
      datasetTable.pageSize.value,
      false,
      datasetTable.search.value,
      datasetTable.sort.value,
      datasetTable.order.value,
    )
  }

  async function ensureTrainingDatasetLoaded(force = false) {
    if (!auth.isAdmin) return
    if (!force && (trainingDatasetLoaded.value || Boolean(trainingDataset.value))) {
      trainingDatasetLoaded.value = true
      return
    }
    await dataStore.fetchTrainingDataset()
    trainingDatasetLoaded.value = true
  }

  async function ensureQualitySummaryLoaded(force = false) {
    if (!auth.isAdmin) return
    if (!force && (qualitySummaryLoaded.value || Boolean(qualitySummary.value))) {
      qualitySummaryLoaded.value = true
      return
    }
    await dataStore.fetchQualitySummary()
    qualitySummaryLoaded.value = true
  }

  async function ensureUploadCapacityLoaded(force = false) {
    if (!auth.isAdmin) return
    if (!force && (uploadCapacityLoaded.value || Boolean(uploadCapacity.value))) {
      uploadCapacityLoaded.value = true
      return
    }
    await dataStore.fetchUploadCapacity()
    uploadCapacityLoaded.value = true
  }

  async function ensurePrepareRunsLoaded(force = false) {
    if (!auth.isAdmin) return
    if (!force && (prepareRunsLoaded.value || prepareRunsLoading.value)) return

    prepareRunsLoading.value = true
    try {
      await workbench.fetchPrepareRuns(force)
      prepareRunsLoaded.value = true
    } finally {
      prepareRunsLoading.value = false
    }
  }

  async function ensureSelectedPrepareRunLoaded(force = false, jobId = selectedPrepareRunId.value) {
    if (!auth.isAdmin || !jobId) return
    await ensurePrepareRunsLoaded(force)
    if (
      workbench.prepareRuns.some((item) => item.id === jobId) &&
      selectedPrepareRun.value?.id !== jobId
    ) {
      await workbench.fetchPrepareRunDetail(jobId)
    }
  }

  function refreshAdminDiagnosticsBackground(force = false) {
    if (!auth.isAdmin) return

    void ensureQualitySummaryLoaded(force).catch(handleBackgroundError)
    void ensureUploadCapacityLoaded(force).catch(handleBackgroundError)
  }

  function refreshDataSummaryBackground(force = false) {
    if (!auth.isAdmin) return
    void ensureTrainingDatasetLoaded(force).catch(handleBackgroundError)
    refreshAdminDiagnosticsBackground(force)
  }

  async function loadActiveDataTabData(force = false) {
    if (auth.isAdmin && dataTab.value === 'upload') {
      await ensureUploadCapacityLoaded(force)
      if (readQueryString(route.query.run)) {
        await ensureSelectedPrepareRunLoaded(force)
      } else {
        void ensurePrepareRunsLoaded(force).catch(handleBackgroundError)
      }
      refreshDataSummaryBackground(force)
      return
    }

    if (auth.isAdmin && dataTab.value === 'quality') {
      const results = await Promise.allSettled([
        ensureQualitySummaryLoaded(force),
        ensureTrainingDatasetLoaded(force),
      ])
      const firstFailure = results.find((result) => result.status === 'rejected')
      if (firstFailure && firstFailure.status === 'rejected') {
        throw firstFailure.reason
      }
      void ensureUploadCapacityLoaded(force).catch(handleBackgroundError)
      return
    }

    await ensureDatasetPageLoaded(force)
    refreshDataSummaryBackground(force)
  }

  async function initializePage() {
    error.value = ''
    await loadActiveDataTabData()
  }

  onMounted(async () => {
    try {
      await initializePage()
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  })

  async function loadPrepareRunDetail(jobId: string) {
    if (!jobId) return
    selectedPrepareRunId.value = jobId
    if (auth.isAdmin && dataTab.value !== 'upload') {
      dataTab.value = 'upload'
    }
    syncPrepareRunToRoute(jobId)
    await workbench.fetchPrepareRunDetail(jobId)
  }

  watch(
    () => workbench.prepareRuns,
    (runs) => {
      if (!runs.length) return
      const hasRequestedRun = Boolean(readQueryString(route.query.run))

      const resolvedRunId = runs.some((item) => item.id === selectedPrepareRunId.value)
        ? selectedPrepareRunId.value
        : runs[0].id

      if (!resolvedRunId) return

      if (selectedPrepareRunId.value !== resolvedRunId) {
        selectedPrepareRunId.value = resolvedRunId
      }

      if (selectedPrepareRun.value?.id !== resolvedRunId) {
        if (hasRequestedRun) {
          void loadPrepareRunDetail(resolvedRunId)
        } else {
          void workbench.fetchPrepareRunDetail(resolvedRunId)
        }
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
      datasetPageLoaded.value = false
      datasetPageRequestKey.value = ''
      trainingDatasetLoaded.value = true
      qualitySummaryLoaded.value = true
      uploadCapacityLoaded.value = true
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
          await ensureTrainingDatasetLoaded(true)
          refreshAdminDiagnosticsBackground(true)
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
          await ensureTrainingDatasetLoaded(true)
          refreshAdminDiagnosticsBackground(true)
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
      datasetPageLoaded.value = false
      datasetPageRequestKey.value = ''
      trainingDatasetLoaded.value = true
      qualitySummaryLoaded.value = true
      uploadCapacityLoaded.value = true
      if (dataTab.value === 'library') {
        await ensureDatasetPageLoaded(true)
      }
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
              run: selectedPrepareRunId,
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
              <div
                v-if="prepareRunsLoading && !prepareRunsLoaded"
                class="card data-run-skeleton"
                aria-busy="true"
              >
                <div class="data-run-skeleton-copy">
                  <Skeleton width="38%" height="0.9rem" />
                  <Skeleton width="68%" height="1.1rem" />
                  <Skeleton width="100%" height="10rem" border-radius="var(--radius-sm)" />
                </div>
              </div>
              <AdminRunDetailPanel
                v-else
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
          <section class="quality-board data-tab-content">
            <article class="card quality-overview-card">
              <div class="quality-board-head">
                <div class="quality-board-copy">
                  <p class="quality-eyebrow">{{ t('nav.data') }}</p>
                  <h2>{{ t('data.qualitySummary') }}</h2>
                  <p>
                    {{ t('data.referenceCoverageHint') }}
                  </p>
                </div>
                <p class="quality-board-note">
                  {{ t('data.qualityHint') }}
                </p>
              </div>

              <div class="kpi-grid quality-overview-grid">
                <MetricCard
                  v-for="item in qualityOverviewCards"
                  :key="item.label"
                  :label="item.label"
                  :value="item.value"
                  :meta="item.meta"
                />
              </div>
            </article>

            <section class="quality-grid quality-grid--split">
              <article class="card quality-card">
                <div class="quality-card-head">
                  <div class="quality-card-copy">
                    <p class="quality-card-kicker">{{ t('data.qualitySummary') }}</p>
                    <h3>{{ t('data.unresolvedMunicipalities') }}</h3>
                    <p>{{ t('data.unresolvedHint') }}</p>
                  </div>
                  <strong class="quality-card-value">
                    {{ formatNumber(qualitySummary?.unresolved_labels?.length || 0) }}
                  </strong>
                </div>

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
                <div class="quality-card-head">
                  <div class="quality-card-copy">
                    <p class="quality-card-kicker">{{ t('data.qualitySummary') }}</p>
                    <h3>{{ t('data.aliasCollisions') }}</h3>
                    <p>{{ t('data.aliasHint') }}</p>
                  </div>
                  <strong class="quality-card-value">
                    {{ formatNumber(qualitySummary?.alias_collisions?.length || 0) }}
                  </strong>
                </div>

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
  .quality-grid,
  .quality-board {
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

  .quality-board {
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

  .data-run-skeleton {
    padding: 1rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    background: var(--surface-panel);
    box-shadow: var(--accent-shadow, var(--shadow-sm));
  }

  .data-run-skeleton-copy {
    display: grid;
    gap: 0.85rem;
  }

  .quality-grid--split {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quality-overview-card,
  .quality-card {
    display: grid;
    gap: 1rem;
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

  .quality-overview-card {
    padding: 1.2rem;
    gap: 1.15rem;
  }

  .quality-board-head {
    display: grid;
    grid-template-columns: minmax(0, 1.35fr) minmax(16rem, 22rem);
    gap: 1rem;
    align-items: start;
  }

  .quality-board-copy,
  .quality-card-copy {
    display: grid;
    gap: 0.45rem;
    min-width: 0;
  }

  .quality-board-copy h2,
  .quality-card-copy h3 {
    margin: 0;
    font-family: var(--font-display);
    line-height: 1.02;
    letter-spacing: -0.04em;
  }

  .quality-board-copy h2 {
    font-size: clamp(1.45rem, 2vw, 2rem);
  }

  .quality-card-copy h3 {
    font-size: 1.25rem;
  }

  .quality-board-copy p,
  .quality-card-copy p {
    margin: 0;
    color: var(--text-soft);
    line-height: 1.55;
  }

  .quality-eyebrow,
  .quality-card-kicker {
    display: inline-flex;
    width: fit-content;
    align-items: center;
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--page-accent) 20%, var(--border) 80%);
    background: color-mix(in srgb, var(--surface-card-strong) 92%, var(--page-accent) 8%);
    color: color-mix(in srgb, var(--page-accent) 78%, var(--text) 22%);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .quality-board-note {
    margin: 0;
    padding: 0.95rem 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 70%, var(--page-accent) 30%);
    background: color-mix(in srgb, var(--surface-soft) 90%, var(--page-accent) 10%);
    color: var(--text-soft);
    line-height: 1.55;
  }

  .quality-overview-grid {
    margin-top: 0.1rem;
  }

  .quality-card {
    padding: 1.1rem;
  }

  .quality-card-head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1rem;
    align-items: start;
  }

  .quality-card-value {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 3.2rem;
    padding: 0.55rem 0.8rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--surface-soft) 84%, var(--page-accent) 16%);
    color: var(--text);
    font-size: 1rem;
    line-height: 1;
    box-shadow: inset 0 1px 0 var(--glass-highlight);
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
    .quality-board-head,
    .quality-grid--split {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .quality-overview-card,
    .quality-card {
      padding: 1rem;
    }

    .quality-card-head {
      grid-template-columns: 1fr;
    }

    .quality-card-value {
      justify-self: start;
    }
  }
</style>
