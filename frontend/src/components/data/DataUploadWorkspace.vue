<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import FileUpload from 'primevue/fileupload'
  import ProgressBar from 'primevue/progressbar'
  import Tag from 'primevue/tag'
  import SectionPanel from '../SectionPanel.vue'
  import type { UploadBatchResult, UploadItem } from '../../features/data/types'

  const props = defineProps<{
    eyebrow: string
    title: string
    description: string
    selectedFiles: File[]
    uploadItems: UploadItem[]
    uploadResult: UploadBatchResult | null
    uploading: boolean
    resetToken: number
    maxUploadLabel: string
    serverFreeLabel: string
    recommendedUploadLabel: string
    reserveLabel: string
    capacityTone: 'success' | 'warn' | 'danger'
    capacityMessage: string
    uploadProgress: number
    uploadProgressLabel: string
  }>()

  const emit = defineEmits<{
    select: [files: File[]]
    clear: []
    start: []
    remove: [file: File]
  }>()

  const { t } = useI18n()
  const fileInput = ref<{ choose?: () => void; clear?: () => void; $el?: HTMLElement } | null>(
    null,
  )
  const isDragActive = ref(false)

  const selectedCount = computed(() => props.selectedFiles.length)
  const totalSelectedBytes = computed(() =>
    props.selectedFiles.reduce((total, file) => total + (file.size || 0), 0),
  )
  const uploadedFileCount = computed(
    () => props.uploadItems.filter((item) => item.status === 'uploaded').length,
  )
  const skippedFileCount = computed(
    () => props.uploadItems.filter((item) => item.status === 'skipped').length,
  )
  const partialFileCount = computed(
    () => props.uploadItems.filter((item) => item.status === 'partial').length,
  )
  const errorFileCount = computed(
    () => props.uploadItems.filter((item) => item.status === 'error').length,
  )
  const uploadedNames = computed(
    () => props.uploadResult?.uploaded.map((item) => item.original_name).filter(Boolean) || [],
  )
  const skippedNames = computed(() => props.uploadResult?.skipped?.filter(Boolean) || [])
  const totalSelectedSizeLabel = computed(() => formatFileSize(totalSelectedBytes.value))

  const statusTone = computed(() => {
    if (props.uploading) return 'warn'
    if (errorFileCount.value) return 'danger'
    if (partialFileCount.value || skippedFileCount.value) return 'warn'
    if (uploadedFileCount.value) return 'success'
    if (!props.uploadResult) return 'contrast'
    return 'warn'
  })

  const statusBadge = computed(() => {
    if (props.uploading) return t('common.loading')
    if (selectedCount.value) {
      return t('data.selectedFilesCount', { count: selectedCount.value })
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

  const statusMessage = computed(() => {
    if (props.uploading) return t('data.uploadInProgress')
    if (!props.uploadResult) {
      if (selectedCount.value) {
        return t('data.readyToUpload', { count: selectedCount.value })
      }
      return t('data.uploadEmptyState')
    }

    const parts: string[] = []
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
    return parts.join(' | ')
  })

  function openFilePicker() {
    if (fileInput.value?.choose) {
      fileInput.value.choose()
      return
    }
    const input = fileInput.value?.$el?.querySelector?.('input[type="file"]') as
      | HTMLInputElement
      | null
      | undefined
    input?.click()
  }

  function clearFileInput() {
    fileInput.value?.clear?.()
  }

  function formatFileSize(bytes: number) {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB']
    const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
    const value = bytes / 1024 ** exponent
    return `${value >= 10 || exponent === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[exponent]}`
  }

  function handleSelect(event: { files?: File[] }) {
    emit('select', event.files || [])
  }

  function handleDrop(event: DragEvent) {
    isDragActive.value = false
    const files = event.dataTransfer?.files
    if (!files?.length) return
    emit('select', Array.from(files))
  }

  function handleDropzoneKeydown(event: KeyboardEvent) {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    openFilePicker()
  }

  watch(
    () => props.resetToken,
    () => {
      clearFileInput()
      isDragActive.value = false
    },
  )
</script>

<template>
  <SectionPanel class="data-upload-workspace" :eyebrow="eyebrow" :title="title">
    <template #actions>
      <Tag severity="contrast" :value="maxUploadLabel" />
      <Tag severity="secondary" :value="serverFreeLabel" />
    </template>

    <div class="upload-workspace-shell">
      <div class="upload-workspace-copy">
        <p class="upload-workspace-label">{{ description }}</p>
        <div class="upload-workspace-meta">
          <Tag severity="contrast" :value="t('data.acceptedFormats')" />
          <Tag severity="secondary" :value="recommendedUploadLabel" />
          <Tag :severity="capacityTone" :value="reserveLabel" />
        </div>
        <div class="upload-workspace-stats">
          <article class="upload-stat">
            <span>{{ t('data.selectedFiles') }}</span>
            <strong>{{ selectedCount }}</strong>
          </article>
          <article class="upload-stat">
            <span>{{ t('data.totalSize') }}</span>
            <strong>{{ totalSelectedSizeLabel }}</strong>
          </article>
          <article class="upload-stat">
            <span>{{ t('data.dedupMode') }}</span>
            <strong>{{ t('data.dedupModeValue') }}</strong>
          </article>
        </div>
        <div class="capacity-banner" :class="capacityTone">
          <strong>{{ capacityMessage }}</strong>
          <span>{{ t('data.capacityBody', { free: serverFreeLabel, reserve: reserveLabel }) }}</span>
        </div>
      </div>

      <div class="upload-workspace-actions">
        <FileUpload
          ref="fileInput"
          mode="basic"
          multiple
          accept=".csv,.zip,.gpkg"
          :auto="false"
          choose-icon="pi pi-folder-open"
          :choose-label="t('data.chooseFiles')"
          :aria-label="t('data.chooseFiles')"
          @select="handleSelect"
        />
        <Button
          icon="pi pi-cloud-upload"
          :label="t('data.uploadButton')"
          :disabled="!selectedFiles.length"
          :loading="uploading"
          @click="emit('start')"
        />
        <Button
          v-if="selectedFiles.length"
          severity="secondary"
          outlined
          icon="pi pi-times"
          :label="t('data.clearSelection')"
          :disabled="uploading"
          @click="emit('clear')"
        />
        <div
          class="upload-dropzone"
          :class="{ active: isDragActive }"
          role="button"
          tabindex="0"
          :aria-label="t('data.chooseFiles')"
          @click="openFilePicker"
          @keydown="handleDropzoneKeydown"
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
      </div>
    </div>

    <div class="upload-status-card" :class="{ 'is-uploading': uploading, 'has-result': Boolean(uploadResult) }">
      <div class="upload-status-head">
        <div>
          <span class="upload-status-label">{{ t('data.uploadQueue') }}</span>
          <strong>{{ statusMessage }}</strong>
        </div>
        <Tag :severity="statusTone" :value="statusBadge" />
      </div>

      <div class="upload-summary-grid">
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
        <article class="upload-stat">
          <span>{{ t('data.selectedFiles') }}</span>
          <strong>{{ selectedCount }}</strong>
        </article>
      </div>

      <div v-if="uploading" class="upload-progress-panel">
        <div class="upload-progress-head">
          <span>{{ t('data.uploadProgress') }}</span>
          <strong>{{ uploadProgressLabel }}</strong>
        </div>
        <ProgressBar :value="uploadProgress || 0" :show-value="false" />
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
              <Tag
                :severity="
                  item.status === 'uploaded'
                    ? 'success'
                    : item.status === 'partial' || item.status === 'processing'
                      ? 'warn'
                      : item.status === 'skipped'
                        ? 'secondary'
                        : item.status === 'error'
                          ? 'danger'
                          : 'contrast'
                "
                :value="t(`data.fileStatus.${item.status}`)"
              />
              <span v-if="item.status === 'uploading' || item.status === 'processing'">
                {{ `${Math.round(item.progress)}%` }}
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
                  <li v-for="name in item.uploadedNames" :key="`${item.key}-uploaded-${name}`">
                    {{ name }}
                  </li>
                </ul>
              </div>
              <div v-if="item.skippedNames.length" class="upload-file-detail warn">
                <span class="upload-status-label">{{ t('data.skippedFilesLabel') }}</span>
                <ul>
                  <li v-for="name in item.skippedNames" :key="`${item.key}-skipped-${name}`">
                    {{ name }}
                  </li>
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
            :disabled="uploading"
            @click="emit('remove', item.file)"
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
  </SectionPanel>
</template>

<style scoped>
  .data-upload-workspace {
    gap: 1rem;
  }

  .upload-workspace-shell,
  .upload-workspace-meta,
  .upload-workspace-stats,
  .upload-status-head,
  .upload-file-meta,
  .upload-file-status,
  .upload-progress-head,
  .upload-result {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .upload-workspace-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(18rem, 0.9fr);
    gap: 1rem;
    align-items: start;
  }

  .upload-workspace-copy {
    display: grid;
    gap: 0.85rem;
  }

  .upload-workspace-label,
  .upload-status-label {
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .upload-workspace-meta {
    align-items: flex-start;
  }

  .upload-workspace-stats {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .upload-stat {
    display: grid;
    gap: 0.25rem;
    padding: 0.85rem 0.95rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 94%, transparent);
    box-shadow: var(--shadow-sm);
  }

  .upload-stat span {
    color: var(--text-muted);
    font-size: 0.88rem;
  }

  .upload-stat strong {
    font-size: 1rem;
    line-height: 1.1;
  }

  .upload-workspace-actions {
    display: grid;
    gap: 0.8rem;
    align-self: start;
  }

  .upload-dropzone {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.9rem;
    align-items: center;
    padding: 1rem 1.05rem;
    border-radius: var(--radius-md);
    border: 1px dashed color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    background: color-mix(in srgb, var(--surface) 84%, transparent);
    cursor: pointer;
    transition:
      border-color 160ms ease,
      transform 160ms ease,
      background 160ms ease,
      box-shadow 160ms ease;
  }

  .upload-dropzone:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 48%, var(--border) 52%);
  }

  .upload-dropzone.active {
    border-color: color-mix(in srgb, var(--primary) 74%, var(--surface-strong) 26%);
    background: color-mix(in srgb, var(--primary) 8%, var(--surface) 92%);
    box-shadow: 0 14px 28px color-mix(in srgb, var(--shadow-color) 10%, transparent);
  }

  .upload-dropzone i {
    font-size: 1.4rem;
    color: var(--primary);
  }

  .upload-dropzone p {
    margin: 0.25rem 0 0;
    color: var(--text-muted);
  }

  .capacity-banner {
    display: grid;
    gap: 0.25rem;
    padding: 0.9rem 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background: var(--surface-subtle);
    box-shadow: var(--shadow-sm);
  }

  .capacity-banner.success {
    border-color: color-mix(in srgb, var(--success) 38%, var(--border) 62%);
  }

  .capacity-banner.warn {
    border-color: color-mix(in srgb, var(--warning) 42%, var(--border) 58%);
  }

  .capacity-banner.danger {
    border-color: color-mix(in srgb, var(--danger) 44%, var(--border) 56%);
  }

  .capacity-banner span {
    color: var(--text-muted);
  }

  .upload-status-card {
    display: grid;
    gap: 0.95rem;
    padding: 1rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 94%, transparent),
        transparent 34%
      ),
      color-mix(in srgb, var(--surface-panel-muted, var(--surface-soft)) 92%, transparent);
    box-shadow: var(--shadow-sm);
  }

  .upload-status-card.is-uploading {
    border-color: color-mix(in srgb, var(--warning) 42%, var(--border) 58%);
  }

  .upload-status-card.has-result {
    border-color: color-mix(in srgb, var(--primary) 32%, var(--border) 68%);
  }

  .upload-status-head {
    justify-content: space-between;
    align-items: flex-start;
  }

  .upload-status-head strong {
    display: block;
    margin-top: 0.25rem;
    font-size: 1rem;
  }

  .upload-summary-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .upload-progress-panel {
    display: grid;
    gap: 0.75rem;
    padding: 0.9rem 1rem;
    border-radius: var(--radius-md);
    background: var(--surface-subtle);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    box-shadow: var(--shadow-sm);
  }

  .upload-progress-head {
    justify-content: space-between;
  }

  .upload-file-list,
  .upload-detail-grid {
    display: grid;
    gap: 0.75rem;
  }

  .upload-file-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.9rem;
    padding: 0.95rem 1rem;
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 94%, transparent);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    box-shadow: var(--shadow-sm);
  }

  .upload-file-item.status-uploaded {
    border-color: color-mix(in srgb, var(--success) 36%, var(--border) 64%);
  }

  .upload-file-item.status-partial,
  .upload-file-item.status-processing {
    border-color: color-mix(in srgb, var(--warning) 40%, var(--border) 60%);
  }

  .upload-file-item.status-error {
    border-color: color-mix(in srgb, var(--danger) 44%, var(--border) 56%);
  }

  .upload-file-main {
    display: grid;
    gap: 0.55rem;
    width: 100%;
  }

  .upload-file-meta,
  .upload-file-status {
    justify-content: space-between;
  }

  .upload-file-meta span {
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .upload-file-summary,
  .upload-file-error {
    margin: 0;
    font-size: 0.92rem;
  }

  .upload-file-error {
    color: var(--danger);
  }

  .upload-file-detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .upload-file-detail,
  .upload-detail-card {
    display: grid;
    gap: 0.4rem;
    padding: 0.85rem 0.95rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background: var(--surface-soft-strong);
  }

  .upload-file-detail.success,
  .upload-detail-card.success {
    border-color: color-mix(in srgb, var(--success) 36%, var(--border) 64%);
  }

  .upload-file-detail.warn,
  .upload-detail-card.warn {
    border-color: color-mix(in srgb, var(--warning) 40%, var(--border) 60%);
  }

  .upload-file-detail ul,
  .upload-detail-card ul {
    margin: 0;
    padding-left: 1rem;
    display: grid;
    gap: 0.25rem;
    max-height: 12rem;
    overflow: auto;
  }

  .upload-placeholder {
    display: grid;
    place-items: center;
    gap: 0.5rem;
    min-height: 7rem;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px dashed color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    color: var(--text-muted);
    background: color-mix(in srgb, var(--surface) 76%, transparent);
  }

  .upload-placeholder i {
    font-size: 1.4rem;
  }

  @media (max-width: 960px) {
    .upload-workspace-shell,
    .upload-summary-grid,
    .upload-file-detail-grid,
    .upload-workspace-stats {
      grid-template-columns: 1fr;
    }
  }
</style>
