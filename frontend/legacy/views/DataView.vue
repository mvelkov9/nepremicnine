<script setup>
  import { computed, onMounted, ref } from 'vue'
  import { RouterLink } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import Dialog from 'primevue/dialog'
  import InputText from 'primevue/inputtext'
  import Tag from 'primevue/tag'
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

  const fileInput = ref(null)
  const previewData = ref(null)
  const previewName = ref('')
  const previewVisible = ref(false)
  const uploadResult = ref(null)
  const error = ref('')
  const datasetFilter = ref('')

  const qualitySummary = computed(() => dataStore.qualitySummary)
  const latestDataset = computed(() => {
    if (!Array.isArray(dataStore.datasets) || !dataStore.datasets.length) return null
    return [...dataStore.datasets].sort((left, right) => {
      const leftTime = Date.parse(left.uploaded_at || '') || 0
      const rightTime = Date.parse(right.uploaded_at || '') || 0
      return rightTime - leftTime
    })[0]
  })
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
  const heroStoryCards = computed(() => [
    {
      label: t('data.preparedDataset'),
      value: dataStore.trainingDataset?.exists
        ? t('model.preparedDatasetReady')
        : t('model.preparedDatasetMissing'),
      meta: dataStore.trainingDataset?.exists
        ? dataStore.trainingDataset.relative_path
        : t('data.noPreparedDataset'),
      tone: dataStore.trainingDataset?.exists ? 'success' : 'default',
    },
    {
      label: t('data.datasets'),
      value: latestDataset.value?.original_name || t('empty.noDatasets'),
      meta: latestDataset.value
        ? `${formatSize(latestDataset.value.row_count)} ${t('data.rows')} · ${formatDate(latestDataset.value.uploaded_at)}`
        : t('data.datasetLibraryHint'),
      tone: latestDataset.value ? 'default' : 'default',
    },
    {
      label: t('data.qualitySummary'),
      value:
        qualitySummary.value?.coverage_ratio != null
          ? formatPercent(qualitySummary.value.coverage_ratio)
          : '—',
      meta:
        qualitySummary.value?.unresolved_rows != null
          ? `${formatNumber(qualitySummary.value.unresolved_rows)} · ${t('data.unresolvedRows')}`
          : t('data.qualityHint'),
      tone:
        qualitySummary.value?.unresolved_rows != null &&
        Number(qualitySummary.value.unresolved_rows) === 0
          ? 'success'
          : 'warning',
    },
  ])
  const studioNotes = computed(() => [
    {
      label: t('data.datasets'),
      value: formatNumber(dataStore.datasets.length),
      meta: latestDataset.value?.relative_path || t('data.datasetLibraryHint'),
      tone: dataStore.datasets.length ? 'success' : 'default',
    },
    {
      label: t('data.coverageRatio'),
      value:
        qualitySummary.value?.coverage_ratio != null
          ? formatPercent(qualitySummary.value.coverage_ratio)
          : '—',
      meta: t('data.referenceCoverageHint'),
      tone:
        qualitySummary.value?.coverage_ratio != null &&
        Number(qualitySummary.value.coverage_ratio) >= 0.98
          ? 'success'
          : 'warning',
    },
    {
      label: t('data.unresolvedRows'),
      value: formatNumber(qualitySummary.value?.unresolved_rows || 0),
      meta: t('data.qualityHint'),
      tone:
        qualitySummary.value?.unresolved_rows != null &&
        Number(qualitySummary.value.unresolved_rows) === 0
          ? 'success'
          : 'warning',
    },
  ])
  const libraryRibbonCards = computed(() => [
    {
      label: t('data.datasets'),
      value: formatNumber(dataStore.datasets.length),
      meta: t('data.datasetLibraryHint'),
      tone: dataStore.datasets.length ? 'success' : 'default',
    },
    {
      label: t('common.search'),
      value: formatNumber(filteredDatasets.value.length),
      meta: datasetFilter.value || t('common.noData'),
      tone: datasetFilter.value ? 'warning' : 'default',
    },
    {
      label: t('data.uploaded'),
      value: latestDataset.value ? formatDate(latestDataset.value.uploaded_at) : t('common.noData'),
      meta: latestDataset.value?.relative_path || t('data.uploadHint'),
      tone: latestDataset.value ? 'success' : 'default',
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
    if (!confirm(t('data.confirmDelete'))) return
    try {
      await dataStore.deleteDataset(id)
      await Promise.all([dataStore.fetchTrainingDataset(), dataStore.fetchQualitySummary()])
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function handleDeleteAll() {
    if (!dataStore.datasets.length) return
    if (!confirm(t('data.confirmDeleteAll'))) return
    try {
      await dataStore.deleteAllDatasets()
      await Promise.all([dataStore.fetchTrainingDataset(), dataStore.fetchQualitySummary()])
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
    <section class="card data-hero">
      <div class="hero-main">
        <PageHeader
          :eyebrow="t('nav.data')"
          :title="t('data.workspaceTitle')"
          :description="t('data.workspaceBody')"
        />

        <div v-if="auth.isAdmin" class="hero-actions">
          <RouterLink to="/admin/priprava">
            <Button icon="pi pi-arrow-right" :label="t('model.goToPrepare')" />
          </RouterLink>
          <RouterLink to="/admin/model">
            <Button
              severity="secondary"
              outlined
              icon="pi pi-bolt"
              :label="t('model.trainButton')"
            />
          </RouterLink>
        </div>

        <div class="hero-story-grid">
          <article
            v-for="card in heroStoryCards"
            :key="card.label"
            class="story-card"
            :class="`tone-${card.tone}`"
          >
            <span class="eyebrow">{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <p>{{ card.meta }}</p>
          </article>
        </div>
      </div>

      <aside class="hero-side">
        <article class="spotlight-card">
          <div class="spotlight-head">
            <span class="eyebrow">{{ t('data.upload') }}</span>
            <div class="spotlight-tags">
              <Tag severity="secondary" :value="latestDataset?.source_type || t('data.datasets')" />
              <Tag
                :severity="dataStore.trainingDataset?.exists ? 'success' : 'warn'"
                :value="
                  dataStore.trainingDataset?.exists
                    ? t('model.preparedDatasetReady')
                    : t('model.preparedDatasetMissing')
                "
              />
            </div>
          </div>

          <h2>{{ latestDataset?.original_name || t('empty.noDatasets') }}</h2>
          <p>
            {{
              latestDataset
                ? `${formatSize(latestDataset.row_count)} ${t('data.rows')} · ${formatDate(latestDataset.uploaded_at)}`
                : t('data.uploadHint')
            }}
          </p>

          <div class="spotlight-summary">
            <span>{{ latestDataset?.relative_path || t('data.datasetLibraryHint') }}</span>
            <span>
              {{
                dataStore.trainingDataset?.exists
                  ? dataStore.trainingDataset.relative_path
                  : t('data.noPreparedDataset')
              }}
            </span>
          </div>
        </article>

        <div v-if="auth.isAdmin" class="metrics-grid hero-metrics">
          <MetricCard
            v-for="card in summaryCards"
            :key="card.label"
            :label="card.label"
            :value="card.value"
            :meta="card.meta"
          />
        </div>
      </aside>
    </section>

    <section v-if="auth.isAdmin" class="card upload-studio">
      <div class="studio-main">
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
      </div>

      <aside class="studio-side">
        <article
          v-for="note in studioNotes"
          :key="note.label"
          class="studio-note"
          :class="`tone-${note.tone}`"
        >
          <span class="eyebrow">{{ note.label }}</span>
          <strong>{{ note.value }}</strong>
          <p>{{ note.meta }}</p>
        </article>
      </aside>
    </section>

    <section v-if="auth.isAdmin" class="quality-grid">
      <article class="card">
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

      <article class="card">
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

      <div class="library-ribbon">
        <article
          v-for="card in libraryRibbonCards"
          :key="card.label"
          class="ribbon-card"
          :class="`tone-${card.tone}`"
        >
          <span class="eyebrow">{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <p>{{ card.meta }}</p>
        </article>
      </div>

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
  .hero-story-grid,
  .hero-side,
  .metrics-grid,
  .quality-grid,
  .library-ribbon {
    display: grid;
    gap: 1rem;
  }

  .data-hero {
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
    gap: 1.2rem;
    align-items: start;
    overflow: hidden;
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--ui-secondary) 12%, transparent) 0%,
        transparent 28%
      ),
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--ui-primary) 14%, transparent) 0%,
        transparent 34%
      ),
      var(--surface-panel-strong);
  }

  .hero-main,
  .studio-main,
  .studio-side {
    display: grid;
    gap: 1rem;
  }

  .hero-actions,
  .spotlight-tags {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .hero-story-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .story-card,
  .studio-note,
  .ribbon-card,
  .spotlight-card {
    position: relative;
    overflow: hidden;
    display: grid;
    gap: 0.6rem;
    padding: 1.1rem 1.15rem;
    border-radius: 1.35rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 80%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 14px 26px rgb(15 23 42 / 8%);
    transition:
      transform 180ms ease,
      border-color 180ms ease,
      box-shadow 180ms ease,
      background 180ms ease;
  }

  .story-card::before,
  .studio-note::before,
  .ribbon-card::before,
  .spotlight-card::before {
    content: '';
    position: absolute;
    inset: auto auto calc(100% - 4.5rem) -1.25rem;
    width: 6rem;
    height: 6rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--ui-primary) 14%, transparent);
    filter: blur(16px);
    opacity: 0.95;
    pointer-events: none;
  }

  .story-card:hover,
  .studio-note:hover,
  .ribbon-card:hover,
  .spotlight-card:hover {
    transform: translateY(-3px);
    border-color: color-mix(in srgb, var(--ui-primary) 26%, var(--border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 16%),
      0 22px 38px rgb(15 23 42 / 12%);
  }

  .story-card strong,
  .studio-note strong,
  .ribbon-card strong,
  .spotlight-card h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.22rem, 2vw, 1.9rem);
    line-height: 1.02;
    letter-spacing: -0.045em;
  }

  .story-card p,
  .studio-note p,
  .ribbon-card p,
  .spotlight-card p {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.9rem;
    line-height: 1.55;
  }

  .tone-success {
    border-color: color-mix(in srgb, var(--success) 26%, var(--border));
  }

  .tone-success::before {
    background: color-mix(in srgb, var(--success) 16%, transparent);
  }

  .tone-warning {
    border-color: color-mix(in srgb, var(--warning) 28%, var(--border));
  }

  .tone-warning::before {
    background: color-mix(in srgb, var(--warning) 16%, transparent);
  }

  .spotlight-card {
    gap: 0.9rem;
    min-height: 16rem;
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--ui-secondary) 14%, transparent) 0%,
        transparent 34%
      ),
      linear-gradient(
        145deg,
        color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
        color-mix(in srgb, var(--ui-primary) 8%, transparent)
      );
  }

  .spotlight-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .spotlight-summary {
    display: grid;
    gap: 0.6rem;
    margin-top: auto;
  }

  .spotlight-summary span {
    display: inline-flex;
    align-items: center;
    min-height: 2.75rem;
    padding: 0.7rem 0.85rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--ui-primary) 14%, var(--border));
    background: color-mix(in srgb, var(--surface-soft) 84%, transparent);
    color: var(--text);
    font-size: 0.85rem;
    line-height: 1.45;
  }

  .metrics-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .hero-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quality-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .upload-studio {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(260px, 0.9fr);
    gap: 1.1rem;
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
    width: 100%;
    min-width: min(100%, 28rem);
    padding: 1rem 1rem;
    border-radius: 1.25rem;
    border: 1px dashed color-mix(in srgb, var(--border) 88%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--ui-primary) 6%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 22px rgb(15 23 42 / 6%);
    transition:
      transform 180ms ease,
      border-color 180ms ease,
      box-shadow 180ms ease,
      background 180ms ease;
  }

  .upload-shell input[type='file']:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--ui-primary) 28%, var(--border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 18px 32px rgb(15 23 42 / 10%);
  }

  .upload-shell input[type='file']:focus-visible {
    outline: none;
    border-color: color-mix(in srgb, var(--ui-primary) 34%, var(--border));
    box-shadow:
      0 0 0 4px color-mix(in srgb, var(--ui-primary) 14%, transparent),
      0 18px 32px rgb(15 23 42 / 10%);
  }

  .upload-shell input[type='file']::file-selector-button {
    margin-right: 0.9rem;
    padding: 0.6rem 0.9rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--primary) 22%, transparent);
    background: color-mix(in srgb, var(--primary) 10%, transparent);
    color: var(--primary);
    font-weight: 700;
  }

  .preview-dialog {
    display: grid;
    gap: 0.75rem;
  }

  .library-ribbon {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin-top: 1rem;
  }

  @media (max-width: 960px) {
    .data-hero,
    .upload-studio,
    .metrics-grid,
    .quality-grid {
      grid-template-columns: 1fr;
    }

    .hero-story-grid,
    .library-ribbon,
    .hero-metrics {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .spotlight-head,
    .table-actions,
    .row-actions {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
