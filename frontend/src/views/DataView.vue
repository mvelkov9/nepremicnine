<script setup lang="ts">
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useConfirm } from 'primevue/useconfirm'
  import { useToast } from '../composables/useToast'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { useAuthStore } from '../stores/auth'
  import type { UploadProgressContext } from '../stores/data'
  import { useDataStore } from '../stores/data'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatDate as formatDateValue, formatNumber, formatPercent } from '../utils/format'

  const { t } = useI18n()
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const confirmDialog = useConfirm()
  const { showToast } = useToast()

  const fileInput = ref(null)
  const previewData = ref(null)
  const previewName = ref('')
  const previewVisible = ref(false)
  const uploadResult = ref(null)
  const selectedFiles = ref<File[]>([])
  const uploadItems = ref<UploadItem[]>([])
  const isDragActive = ref(false)
  const error = ref('')
  const datasetFilter = ref('')

  type UploadItemStatus =
    | 'queued'
    | 'uploading'
    | 'processing'
    | 'uploaded'
    | 'skipped'
    | 'partial'
    | 'error'

  interface UploadItem {
    key: string
    file: File
    status: UploadItemStatus
    progress: number
    uploadedNames: string[]
    skippedNames: string[]
    summary: string
    errorMessage: string
  }

  const qualitySummary = computed(() => dataStore.qualitySummary)
  const uploadCapacity = computed(() => dataStore.uploadCapacity)
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

  const totalSelectedBytes = computed(() =>
    selectedFiles.value.reduce((total, file) => total + (file.size || 0), 0),
  )

  const uploadedFileCount = computed(
    () => uploadItems.value.filter((item) => item.status === 'uploaded').length,
  )

  const skippedFileCount = computed(
    () => uploadItems.value.filter((item) => item.status === 'skipped').length,
  )

  const partialFileCount = computed(
    () => uploadItems.value.filter((item) => item.status === 'partial').length,
  )

  const errorFileCount = computed(
    () => uploadItems.value.filter((item) => item.status === 'error').length,
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
    t('data.uploadProgressValue', { progress: dataStore.uploadProgress || 0 }),
  )

  const uploadedNames = computed(() =>
    (uploadResult.value?.uploaded || []).map((item) => item.original_name).filter(Boolean),
  )

  const skippedNames = computed(() => (uploadResult.value?.skipped || []).filter(Boolean))

  const uploadStatusTone = computed(() => {
    if (errorFileCount.value) return 'danger'
    if (partialFileCount.value || skippedFileCount.value) return 'warn'
    if (uploadedFileCount.value) return 'success'
    if (!uploadResult.value) return 'contrast'
    return 'warn'
  })

  const uploadStatusMessage = computed(() => {
    if (dataStore.uploading) return t('data.uploadInProgress')

    if (!uploadResult.value) {
      if (selectedFiles.value.length) {
        return t('data.readyToUpload', { count: selectedFiles.value.length })
      }
      return t('data.uploadEmptyState')
    }

    const parts = []
    if (uploadedFileCount.value) {
      parts.push(t('data.uploadedArchiveCount', { count: uploadedFileCount.value }))
    }
    if (skippedFileCount.value) {
      parts.push(t('data.skippedArchiveCount', { count: skippedFileCount.value }))
    }
    if (partialFileCount.value) {
      parts.push(t('data.partialArchiveCount', { count: partialFileCount.value }))
    }
    if (errorFileCount.value) {
      parts.push(t('data.errorArchiveCount', { count: errorFileCount.value }))
    }
    return parts.join(' • ')
  })

  const uploadStatusBadge = computed(() => {
    if (dataStore.uploading) return t('common.loading')
    if (selectedFiles.value.length) {
      return t('data.selectedFilesCount', { count: selectedFiles.value.length })
    }
    if (errorFileCount.value) {
      return t('data.errorArchiveCount', { count: errorFileCount.value })
    }
    if (partialFileCount.value) {
      return t('data.partialArchiveCount', { count: partialFileCount.value })
    }
    if (uploadedFileCount.value) {
      return t('data.uploadedArchiveCount', { count: uploadedFileCount.value })
    }
    if (skippedFileCount.value) {
      return t('data.skippedArchiveCount', { count: skippedFileCount.value })
    }
    return t('data.selectedFilesCount', { count: 0 })
  })

  async function loadDataView() {
    await Promise.all([
      dataStore.fetchDatasets(),
      dataStore.fetchTrainingDataset(),
      auth.isAdmin ? dataStore.fetchQualitySummary() : Promise.resolve(),
      auth.isAdmin ? dataStore.fetchUploadCapacity() : Promise.resolve(),
    ])
  }

  onMounted(async () => {
    try {
      await loadDataView()
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  })

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
      (item: UploadItem) => !keys.has(item.key) && item.status !== 'queued',
    )
    const nextItems = nextFiles.map((file) => {
      const key = getFileKey(file)
      return (
        uploadItems.value.find((item: UploadItem) => item.key === key) || createUploadItem(file)
      )
    })

    uploadItems.value = [...existingCompleted, ...nextItems]
  }

  function updateUploadItem(file: File, patch: Partial<UploadItem>) {
    const key = getFileKey(file)
    uploadItems.value = uploadItems.value.map((item: UploadItem) =>
      item.key === key ? { ...item, ...patch } : item,
    )
  }

  function resolveItemStatus(result: any): UploadItemStatus {
    if (result?.errorMessage) return 'error'
    const uploadedCount = result?.uploaded?.length || 0
    const skippedCount = result?.skipped?.length || 0
    if (uploadedCount && skippedCount) return 'partial'
    if (uploadedCount) return 'uploaded'
    if (skippedCount) return 'skipped'
    return 'uploaded'
  }

  function buildItemSummary(result: any) {
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

  function getUploadItemTone(status: UploadItemStatus) {
    if (status === 'uploaded') return 'success'
    if (status === 'partial' || status === 'processing') return 'warn'
    if (status === 'skipped') return 'secondary'
    if (status === 'error') return 'danger'
    return 'contrast'
  }

  function getUploadItemLabel(status: UploadItemStatus) {
    return t(`data.fileStatus.${status}`)
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
    const deduped = new Map(
      selectedFiles.value.map((file) => [`${file.name}-${file.size}-${file.lastModified}`, file]),
    )

    for (const file of incomingFiles) {
      deduped.set(`${file.name}-${file.size}-${file.lastModified}`, file)
    }

    selectedFiles.value = Array.from(deduped.values())
    syncUploadItems(selectedFiles.value)
    uploadResult.value = null
    error.value = ''
  }

  function handleFileSelect(event: any) {
    mergeSelectedFiles(event.files || [])
  }

  function handleDrop(event: DragEvent) {
    isDragActive.value = false
    const files = event.dataTransfer?.files
    if (!files?.length) return
    mergeSelectedFiles(files)
  }

  function openFilePicker() {
    if (fileInput.value?.choose) {
      fileInput.value.choose()
      return
    }
    fileInput.value?.$el?.querySelector?.('input[type="file"]')?.click?.()
  }

  function clearSelectedFiles() {
    selectedFiles.value = []
    uploadItems.value = uploadItems.value.filter((item: UploadItem) => item.status !== 'queued')
    fileInput.value?.clear()
  }

  function removeSelectedFile(file: File) {
    const removedKey = getFileKey(file)
    selectedFiles.value = selectedFiles.value.filter(
      (selectedFile) => getFileKey(selectedFile) !== removedKey,
    )
    uploadItems.value = uploadItems.value.filter(
      (item: UploadItem) => item.key !== removedKey || item.status !== 'queued',
    )
    if (!selectedFiles.value.length) {
      fileInput.value?.clear()
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
      selectedFiles.value = []
      fileInput.value?.clear()
      await Promise.all([
        dataStore.fetchTrainingDataset(),
        dataStore.fetchQualitySummary(),
        dataStore.fetchUploadCapacity(),
      ])
      showToast(
        uploadedCount
          ? t('data.uploadSuccessToast', { count: uploadedCount })
          : t('data.uploadNoNewFilesToast', { count: skippedCount }),
        uploadedCount ? 'success' : 'warning',
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
          await Promise.all([
            dataStore.fetchTrainingDataset(),
            dataStore.fetchQualitySummary(),
            dataStore.fetchUploadCapacity(),
          ])
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
          await Promise.all([
            dataStore.fetchTrainingDataset(),
            dataStore.fetchQualitySummary(),
            dataStore.fetchUploadCapacity(),
          ])
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
          <Tag severity="secondary" :value="maxUploadLabel" />
        </template>
      </PageHeader>

      <div class="upload-shell">
        <div class="upload-copy">
          <strong>{{ t('data.uploadTitle') }}</strong>
          <p class="muted">{{ t('data.uploadHint') }}</p>
          <div class="upload-meta">
            <Tag severity="contrast" :value="t('data.acceptedFormats')" />
            <Tag severity="secondary" :value="maxUploadLabel" />
            <Tag :severity="capacityTone" :value="t('data.serverFreeValue', { size: serverFreeLabel })" />
          </div>
        </div>
        <div class="upload-actions">
          <FileUpload
            ref="fileInput"
            mode="basic"
            multiple
            accept=".csv,.zip,.gpkg"
            :auto="false"
            choose-icon="pi pi-folder-open"
            :choose-label="t('data.chooseFiles')"
            :aria-label="t('data.chooseFiles')"
            @select="handleFileSelect"
          />
          <Button
            icon="pi pi-cloud-upload"
            :label="t('data.uploadButton')"
            :disabled="!selectedFiles.length"
            :loading="dataStore.uploading"
            @click="startUpload"
          />
          <Button
            v-if="selectedFiles.length"
            severity="secondary"
            outlined
            icon="pi pi-times"
            :label="t('data.clearSelection')"
            :disabled="dataStore.uploading"
            @click="clearSelectedFiles"
          />
        </div>
      </div>

      <div class="upload-status-card">
        <div
          class="upload-dropzone"
          :class="{ active: isDragActive }"
          @click="openFilePicker"
          @dragenter.prevent="isDragActive = true"
          @dragover.prevent="isDragActive = true"
          @dragleave.prevent="isDragActive = false"
          @drop.prevent="handleDrop"
        >
          <i class="pi pi-cloud-upload" aria-hidden="true" />
          <div>
            <strong>{{ t('data.dropzoneTitle') }}</strong>
            <p>{{ t('data.dropzoneBody') }}</p>
          </div>
        </div>

        <div class="upload-status-head">
          <div>
            <span class="upload-status-label">{{ t('data.uploadQueue') }}</span>
            <strong>{{ uploadStatusMessage }}</strong>
          </div>
          <Tag
            :severity="uploadStatusTone"
            :value="uploadStatusBadge"
          />
        </div>

        <div class="upload-summary-grid">
          <article class="upload-stat">
            <span>{{ t('data.selectedFiles') }}</span>
            <strong>{{ formatNumber(selectedFiles.length) }}</strong>
          </article>
          <article class="upload-stat">
            <span>{{ t('data.totalSize') }}</span>
            <strong>{{ formatFileSize(totalSelectedBytes) }}</strong>
          </article>
          <article class="upload-stat">
            <span>{{ t('data.dedupMode') }}</span>
            <strong>{{ t('data.dedupModeValue') }}</strong>
          </article>
          <article class="upload-stat">
            <span>{{ t('data.recommendedUpload') }}</span>
            <strong>{{ recommendedUploadLabel }}</strong>
          </article>
          <article class="upload-stat">
            <span>{{ t('data.serverFree') }}</span>
            <strong>{{ serverFreeLabel }}</strong>
          </article>
          <article class="upload-stat">
            <span>{{ t('data.serverReserve') }}</span>
            <strong>{{ reserveLabel }}</strong>
          </article>
        </div>

        <div class="capacity-banner" :class="capacityTone">
          <strong>{{ capacityMessage }}</strong>
          <span>{{ t('data.capacityBody', { free: serverFreeLabel, reserve: reserveLabel }) }}</span>
        </div>

        <div v-if="dataStore.uploading" class="upload-progress-panel">
          <div class="upload-progress-head">
            <span>{{ t('data.uploadProgress') }}</span>
            <strong>{{ uploadProgressLabel }}</strong>
          </div>
          <ProgressBar :value="dataStore.uploadProgress || 0" :show-value="false" />
        </div>

        <div v-if="uploadItems.length" class="upload-file-list">
          <article
            v-for="item in uploadItems"
            :key="item.key"
            class="upload-file-item"
            :class="`status-${item.status}`"
          >
            <div class="upload-file-main">
              <div class="upload-file-meta">
                <strong>{{ item.file.name }}</strong>
                <span>{{ formatFileSize(item.file.size || 0) }}</span>
              </div>
              <div class="upload-file-status">
                <Tag :severity="getUploadItemTone(item.status)" :value="getUploadItemLabel(item.status)" />
                <span v-if="item.status === 'uploading' || item.status === 'processing'">
                  {{ item.progress }}%
                </span>
              </div>
              <p v-if="item.summary" class="upload-file-summary">{{ item.summary }}</p>
              <p v-if="item.errorMessage" class="upload-file-error">{{ item.errorMessage }}</p>
              <ProgressBar
                v-if="item.status === 'uploading' || item.status === 'processing'"
                :value="item.progress"
                :show-value="false"
              />
              <div
                v-if="item.uploadedNames.length || item.skippedNames.length"
                class="upload-file-detail-grid"
              >
                <div v-if="item.uploadedNames.length" class="upload-file-detail success">
                  <span class="upload-status-label">{{ t('data.uploadedFilesLabel') }}</span>
                  <ul>
                    <li v-for="name in item.uploadedNames" :key="`${item.key}-uploaded-${name}`">{{ name }}</li>
                  </ul>
                </div>
                <div v-if="item.skippedNames.length" class="upload-file-detail warn">
                  <span class="upload-status-label">{{ t('data.skippedFilesLabel') }}</span>
                  <ul>
                    <li v-for="name in item.skippedNames" :key="`${item.key}-skipped-${name}`">{{ name }}</li>
                  </ul>
                </div>
              </div>
            </div>
            <Button
              v-if="item.status === 'queued'"
              text
              rounded
              severity="secondary"
              icon="pi pi-times"
              :aria-label="t('data.removeFile')"
              :disabled="dataStore.uploading"
              @click="removeSelectedFile(item.file)"
            />
          </article>
        </div>

        <div v-else class="upload-placeholder">
          <i class="pi pi-inbox" aria-hidden="true" />
          <span>{{ t('data.uploadEmptyState') }}</span>
        </div>

        <div v-if="uploadResult" class="upload-result">
          <Tag
            v-if="errorFileCount"
            severity="danger"
            :value="t('data.errorArchiveCount', { count: errorFileCount })"
          />
          <Tag
            v-if="partialFileCount"
            severity="warn"
            :value="t('data.partialArchiveCount', { count: partialFileCount })"
          />
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

        <div v-if="uploadedNames.length || skippedNames.length" class="upload-detail-grid">
          <article v-if="uploadedNames.length" class="upload-detail-card success">
            <span class="upload-status-label">{{ t('data.uploadedFilesLabel') }}</span>
            <ul>
              <li v-for="name in uploadedNames" :key="name">{{ name }}</li>
            </ul>
          </article>
          <article v-if="skippedNames.length" class="upload-detail-card warn">
            <span class="upload-status-label">{{ t('data.skippedFilesLabel') }}</span>
            <ul>
              <li v-for="name in skippedNames" :key="name">{{ name }}</li>
            </ul>
          </article>
        </div>
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
        <p class="muted">{{ t('data.previewRows', { count: formatNumber(previewData.total_rows || 0) }) }}</p>
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
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(18rem, 1fr);
    gap: 1rem;
    align-items: start;
    padding: 0.3rem 0;
  }

  .upload-copy {
    display: grid;
    gap: 0.75rem;
    max-width: 42rem;
  }

  .upload-copy strong {
    font-size: 1rem;
  }

  .upload-meta,
  .upload-actions,
  .upload-result,
  .upload-status-head,
  .upload-file-item,
  .upload-progress-head,
  .table-actions,
  .row-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .upload-actions {
    justify-content: flex-end;
    align-self: center;
  }

  .upload-status-card {
    display: grid;
    gap: 1rem;
    padding: 1rem;
    border-radius: 1.25rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(135deg, color-mix(in srgb, var(--surface-soft) 86%, white 14%), transparent),
      color-mix(in srgb, var(--surface-panel-muted, var(--surface-soft)) 90%, transparent);
  }

  .upload-dropzone {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 1rem;
    align-items: center;
    padding: 1.1rem 1.2rem;
    border-radius: 1.1rem;
    border: 1px dashed color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    background: color-mix(in srgb, var(--surface) 82%, transparent);
    cursor: pointer;
    transition:
      border-color 160ms ease,
      transform 160ms ease,
      background 160ms ease;
  }

  .upload-dropzone.active {
    border-color: color-mix(in srgb, var(--primary) 74%, white 26%);
    background: color-mix(in srgb, var(--primary) 8%, var(--surface) 92%);
    transform: translateY(-1px);
  }

  .upload-dropzone i {
    font-size: 1.4rem;
    color: var(--primary);
  }

  .upload-dropzone p {
    margin: 0.25rem 0 0;
    color: var(--text-muted);
  }

  .upload-status-head {
    justify-content: space-between;
    align-items: flex-start;
  }

  .upload-status-head strong {
    display: block;
    font-size: 1rem;
    margin-top: 0.25rem;
  }

  .upload-status-label {
    display: inline-block;
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .upload-summary-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .upload-stat {
    display: grid;
    gap: 0.3rem;
    padding: 0.85rem 1rem;
    border-radius: 1rem;
    background: color-mix(in srgb, var(--surface) 82%, transparent);
    border: 1px solid color-mix(in srgb, var(--border) 80%, transparent);
  }

  .upload-stat span,
  .upload-file-item span {
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .upload-file-list {
    display: grid;
    gap: 0.75rem;
  }

  .capacity-banner {
    display: grid;
    gap: 0.25rem;
    padding: 0.9rem 1rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 76%, transparent);
    background: color-mix(in srgb, var(--surface) 88%, transparent);
  }

  .capacity-banner.success {
    border-color: color-mix(in srgb, var(--green-500, #22c55e) 48%, var(--border) 52%);
  }

  .capacity-banner.warn {
    border-color: color-mix(in srgb, var(--orange-500, #f97316) 52%, var(--border) 48%);
  }

  .capacity-banner.danger {
    border-color: color-mix(in srgb, var(--red-500, #ef4444) 56%, var(--border) 44%);
  }

  .capacity-banner span {
    color: var(--text-muted);
  }

  .upload-progress-panel {
    display: grid;
    gap: 0.75rem;
    padding: 0.9rem 1rem;
    border-radius: 1rem;
    background: color-mix(in srgb, var(--surface) 88%, transparent);
    border: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
  }

  .upload-progress-head {
    justify-content: space-between;
  }

  .upload-detail-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .upload-detail-card {
    display: grid;
    gap: 0.75rem;
    padding: 1rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
    background: color-mix(in srgb, var(--surface) 90%, transparent);
  }

  .upload-detail-card.success {
    border-color: color-mix(in srgb, var(--green-500, #22c55e) 46%, var(--border) 54%);
  }

  .upload-detail-card.warn {
    border-color: color-mix(in srgb, var(--orange-500, #f97316) 48%, var(--border) 52%);
  }

  .upload-detail-card ul {
    margin: 0;
    padding-left: 1rem;
    display: grid;
    gap: 0.4rem;
    max-height: 12rem;
    overflow: auto;
  }

  .upload-file-item {
    justify-content: space-between;
    padding: 0.9rem 1rem;
    border-radius: 1rem;
    background: color-mix(in srgb, var(--surface) 90%, transparent);
    border: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
  }

  .upload-file-item.status-uploaded {
    border-color: color-mix(in srgb, var(--green-500, #22c55e) 46%, var(--border) 54%);
  }

  .upload-file-item.status-partial,
  .upload-file-item.status-processing {
    border-color: color-mix(in srgb, var(--orange-500, #f97316) 48%, var(--border) 52%);
  }

  .upload-file-item.status-error {
    border-color: color-mix(in srgb, var(--red-500, #ef4444) 54%, var(--border) 46%);
  }

  .upload-file-main {
    display: grid;
    gap: 0.6rem;
    width: 100%;
  }

  .upload-file-meta,
  .upload-file-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .upload-file-summary,
  .upload-file-error {
    margin: 0;
    font-size: 0.92rem;
  }

  .upload-file-error {
    color: var(--red-500, #ef4444);
  }

  .upload-file-detail-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .upload-file-detail {
    display: grid;
    gap: 0.4rem;
    padding: 0.85rem 0.95rem;
    border-radius: 0.9rem;
    border: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
    background: color-mix(in srgb, var(--surface) 92%, transparent);
  }

  .upload-file-detail.success {
    border-color: color-mix(in srgb, var(--green-500, #22c55e) 46%, var(--border) 54%);
  }

  .upload-file-detail.warn {
    border-color: color-mix(in srgb, var(--orange-500, #f97316) 48%, var(--border) 52%);
  }

  .upload-file-detail ul {
    margin: 0;
    padding-left: 1rem;
    display: grid;
    gap: 0.25rem;
  }

  .upload-file-item > div {
    display: grid;
    gap: 0.2rem;
    min-width: 0;
  }

  .upload-file-item strong {
    word-break: break-word;
  }

  .upload-placeholder {
    display: grid;
    place-items: center;
    gap: 0.5rem;
    min-height: 7rem;
    padding: 1rem;
    border-radius: 1rem;
    border: 1px dashed color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    color: var(--text-muted);
    background: color-mix(in srgb, var(--surface) 72%, transparent);
  }

  .upload-placeholder i {
    font-size: 1.4rem;
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
    background: color-mix(
      in srgb,
      var(--surface-panel-muted, var(--surface-soft)) 92%,
      transparent
    );
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
  }

  @media (max-width: 960px) {
    .metrics-grid,
    .quality-grid,
    .upload-detail-grid,
    .upload-file-detail-grid,
    .upload-summary-grid,
    .upload-shell {
      grid-template-columns: 1fr;
    }

    .upload-shell {
      align-items: stretch;
    }

    .upload-actions,
    .upload-status-head {
      display: grid;
      grid-template-columns: 1fr;
      width: 100%;
    }

    .table-actions,
    .row-actions {
      display: grid;
      grid-template-columns: 1fr;
      width: 100%;
    }

    .search-field,
    .upload-actions :deep(.p-button),
    .upload-actions :deep(.p-fileupload-basic),
    .row-actions :deep(.p-button),
    .table-actions :deep(.p-button) {
      width: 100%;
    }
  }
</style>
