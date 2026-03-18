<script setup lang="ts">
  definePageMeta({ middleware: ['admin'] })

  const { t } = useI18n()
  const dataStore = useDataStore()

  const fileInput = ref<HTMLInputElement | null>(null)
  const datasetFilter = ref('')
  const uploadResult = ref<any>(null)
  const error = ref('')
  const previewOpen = ref(false)
  const previewData = ref<any>(null)
  const previewName = ref('')

  // Computed
  const qualitySummary = computed(() => dataStore.qualitySummary)
  const latestDataset = computed(() => {
    if (!Array.isArray(dataStore.datasets) || !dataStore.datasets.length) return null
    return [...dataStore.datasets].sort((a, b) => {
      return (Date.parse(b.uploaded_at ?? '') || 0) - (Date.parse(a.uploaded_at ?? '') || 0)
    })[0]
  })

  const filteredDatasets = computed(() => {
    const q = datasetFilter.value.trim().toLowerCase()
    if (!q) return dataStore.datasets
    return dataStore.datasets.filter((d) =>
      [d.original_name, (d as any).relative_path, d.source_type].some((v) =>
        String(v ?? '')
          .toLowerCase()
          .includes(q),
      ),
    )
  })

  const kpiCards = computed(() => [
    {
      label: t('data.preparedDataset'),
      value: (dataStore.trainingDataset as any)?.exists
        ? formatNumber((dataStore.trainingDataset as any)?.rows ?? 0)
        : t('common.noData'),
      meta: (dataStore.trainingDataset as any)?.exists
        ? (dataStore.trainingDataset as any)?.relative_path
        : t('data.noPreparedDataset'),
    },
    {
      label: t('data.coveredMunicipalities'),
      value: formatNumber(qualitySummary.value?.covered_municipalities ?? 0),
      meta: qualitySummary.value
        ? `${formatNumber(qualitySummary.value.covered_municipalities ?? 0)} / ${formatNumber((qualitySummary.value as any)?.canonical_reference_total ?? 0)}`
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
      value: formatNumber(qualitySummary.value?.unresolved_rows ?? 0),
      meta: t('data.qualityHint'),
    },
  ])

  // Dataset table columns
  const datasetColumns = [
    { accessorKey: 'original_name', header: t('data.fileName') },
    { accessorKey: 'relative_path', header: t('data.relativePath') },
    { accessorKey: 'row_count', header: t('data.rows') },
    { accessorKey: 'uploaded_at', header: t('data.uploaded') },
    { accessorKey: 'actions', header: t('data.actions'), enableSorting: false },
  ]

  async function loadAll() {
    error.value = ''
    try {
      await Promise.all([
        dataStore.fetchDatasets(),
        dataStore.fetchTrainingDataset(),
        dataStore.fetchQualitySummary(),
      ])
    } catch (e: any) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function handleUpload() {
    const files = fileInput.value?.files
    if (!files?.length) return
    error.value = ''
    uploadResult.value = null
    try {
      const result = await dataStore.uploadFiles(Array.from(files))
      uploadResult.value = result
      if (fileInput.value) fileInput.value.value = ''
      await Promise.all([dataStore.fetchTrainingDataset(), dataStore.fetchQualitySummary()])
    } catch (e: any) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function showPreview(dataset: any) {
    previewName.value = dataset.original_name
    error.value = ''
    try {
      previewData.value = await dataStore.fetchPreview(dataset.id)
      previewOpen.value = true
    } catch (e: any) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function handleDelete(id: number) {
    if (!confirm(t('data.confirmDelete'))) return
    try {
      await dataStore.deleteDataset(id)
      await Promise.all([dataStore.fetchTrainingDataset(), dataStore.fetchQualitySummary()])
    } catch (e: any) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function handleDeleteAll() {
    if (!dataStore.datasets.length) return
    if (!confirm(t('data.confirmDeleteAll'))) return
    try {
      await dataStore.deleteAllDatasets()
      await Promise.all([dataStore.fetchTrainingDataset(), dataStore.fetchQualitySummary()])
    } catch (e: any) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  await useAsyncData('admin-data', loadAll)
</script>

<template>
  <div class="data-page">
    <!-- Hero / status panel -->
    <section class="card">
      <div class="section-head">
        <div>
          <p class="eyebrow">{{ t('nav.data') }}</p>
          <h1>{{ t('data.workspaceTitle') }}</h1>
          <p class="muted">{{ t('data.workspaceBody') }}</p>
        </div>
        <div class="hero-actions">
          <NuxtLink to="/admin/priprava">
            <UButton icon="i-lucide-arrow-right" :label="t('model.goToPrepare')" />
          </NuxtLink>
          <NuxtLink to="/admin/model">
            <UButton
              icon="i-lucide-bolt"
              variant="outline"
              color="neutral"
              :label="t('model.trainButton')"
            />
          </NuxtLink>
        </div>
      </div>

      <!-- KPI cards -->
      <div class="kpi-grid">
        <KpiCard
          v-for="card in kpiCards"
          :key="card.label"
          :label="card.label"
          :value="card.value"
          :meta="card.meta"
        />
      </div>

      <!-- Training dataset status -->
      <div class="training-status">
        <UBadge
          :label="
            (dataStore.trainingDataset as any)?.exists
              ? t('model.preparedDatasetReady')
              : t('model.preparedDatasetMissing')
          "
          :color="(dataStore.trainingDataset as any)?.exists ? 'success' : 'warning'"
          variant="soft"
        />
        <span
          v-if="(dataStore.trainingDataset as any)?.exists"
          class="muted"
          style="font-size: 0.84rem"
        >
          {{ (dataStore.trainingDataset as any)?.relative_path }}
        </span>
      </div>
    </section>

    <!-- Upload panel -->
    <section class="card">
      <div class="section-head">
        <div>
          <p class="eyebrow subtle">{{ t('data.upload') }}</p>
          <h2>{{ t('data.uploadTitle') }}</h2>
          <p class="muted">{{ t('data.uploadHint') }}</p>
        </div>
        <UBadge :label="t('data.maxUpload')" color="neutral" variant="soft" />
      </div>

      <div class="upload-shell">
        <input
          ref="fileInput"
          type="file"
          multiple
          accept=".csv,.zip"
          class="file-input"
          :aria-label="t('data.upload')"
        />
        <UButton
          icon="i-lucide-upload"
          :loading="dataStore.uploading"
          :label="dataStore.uploading ? t('common.loading') : t('data.uploadButton')"
          @click="handleUpload"
        />
      </div>

      <div v-if="uploadResult" class="upload-result">
        <UBadge
          v-if="uploadResult.uploaded?.length"
          :label="t('data.uploadedCount', { count: uploadResult.uploaded.length })"
          color="success"
          variant="soft"
        />
        <UBadge
          v-if="uploadResult.skipped?.length"
          :label="t('data.skippedCount', { count: uploadResult.skipped.length })"
          color="warning"
          variant="soft"
        />
      </div>

      <UAlert
        v-if="error"
        :description="error"
        color="error"
        variant="soft"
        icon="i-lucide-alert-circle"
      />
    </section>

    <!-- Quality summary -->
    <section v-if="qualitySummary" class="grid-two">
      <article class="card">
        <div class="section-head compact">
          <div>
            <p class="eyebrow subtle">{{ t('data.qualitySummary') }}</p>
            <h2>{{ t('data.unresolvedMunicipalities') }}</h2>
          </div>
        </div>
        <div class="table-wrap">
          <UTable
            :columns="[
              { accessorKey: 'label', header: t('dashboard.municipality') },
              { accessorKey: 'count', header: t('dashboard.transactions') },
            ]"
            :data="(qualitySummary as any).unresolved_labels ?? []"
          />
        </div>
      </article>

      <article class="card">
        <div class="section-head compact">
          <div>
            <p class="eyebrow subtle">{{ t('data.qualitySummary') }}</p>
            <h2>{{ t('data.aliasCollisions') }}</h2>
          </div>
        </div>
        <div class="table-wrap">
          <UTable
            :columns="[
              { accessorKey: 'canonical', header: t('data.canonicalLabel') },
              { accessorKey: 'variant_count', header: t('data.variantCount') },
              { accessorKey: 'variants', header: t('data.variants'), enableSorting: false },
            ]"
            :data="qualitySummary.alias_collisions ?? []"
          >
            <template #variants-cell="{ row }">
              {{ row.original.variants?.join(', ') ?? '—' }}
            </template>
          </UTable>
        </div>
      </article>
    </section>

    <!-- Dataset library -->
    <section class="card">
      <div class="section-head">
        <div>
          <p class="eyebrow subtle">{{ t('data.datasets') }}</p>
          <h2>{{ t('data.datasetLibrary') }}</h2>
          <p class="muted">{{ t('data.datasetLibraryHint') }}</p>
        </div>
        <div class="table-actions">
          <UInput
            v-model="datasetFilter"
            icon="i-lucide-search"
            :placeholder="t('common.search')"
          />
          <UButton
            v-if="dataStore.datasets.length"
            icon="i-lucide-trash-2"
            color="error"
            variant="outline"
            :label="t('data.deleteAll')"
            @click="handleDeleteAll"
          />
        </div>
      </div>

      <div v-if="dataStore.loading" class="grid gap-2">
        <USkeleton v-for="i in 5" :key="i" class="h-10" />
      </div>
      <p v-else-if="!dataStore.datasets.length" class="muted">{{ t('empty.noDatasets') }}</p>
      <div v-else class="table-wrap">
        <UTable :columns="datasetColumns" :data="filteredDatasets">
          <template #row_count-cell="{ row }">
            {{ formatNumber(row.original.row_count) }}
          </template>
          <template #uploaded_at-cell="{ row }">
            {{ formatDate(row.original.uploaded_at, { dateStyle: 'medium' }) }}
          </template>
          <template #actions-cell="{ row }">
            <div class="row-actions">
              <UButton
                size="xs"
                variant="outline"
                color="neutral"
                icon="i-lucide-eye"
                :label="t('data.preview')"
                @click="showPreview(row.original)"
              />
              <UButton
                size="xs"
                variant="outline"
                color="error"
                icon="i-lucide-trash-2"
                :label="t('common.delete')"
                @click="handleDelete(row.original.id)"
              />
            </div>
          </template>
        </UTable>
      </div>
    </section>

    <!-- Preview modal -->
    <UModal v-model:open="previewOpen">
      <template #content>
        <div class="p-6">
          <h2 style="margin: 0 0 0.75rem; font-family: var(--font-display)">
            {{ previewName || t('data.preview') }}
          </h2>
          <div v-if="previewData">
            <p class="muted" style="font-size: 0.85rem; margin-bottom: 0.75rem">
              {{ t('data.columns') }}: {{ previewData.columns?.join(', ') }}
            </p>
            <div class="table-wrap" style="max-height: 420px; overflow-y: auto">
              <UTable
                :columns="
                  (previewData.columns ?? []).map((c: string) => ({ accessorKey: c, header: c }))
                "
                :data="previewData.rows ?? []"
              />
            </div>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>

<style scoped>
  .data-page {
    display: grid;
    gap: 1rem;
  }

  .card {
    padding: 1.25rem;
    border-radius: 1.5rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
    display: grid;
    gap: 1rem;
  }

  .section-head h1 {
    font-size: clamp(1.5rem, 2vw, 2rem);
  }

  .training-status {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .upload-shell {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .file-input {
    flex: 1;
    min-width: min(100%, 28rem);
    padding: 0.85rem 1rem;
    border-radius: 1.25rem;
    border: 1px dashed color-mix(in srgb, var(--border) 88%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--primary) 6%, transparent)
    );
    transition: border-color 180ms ease;
  }

  .file-input:hover {
    border-color: color-mix(in srgb, var(--primary) 28%, var(--border));
  }

  .file-input::file-selector-button {
    margin-right: 0.9rem;
    padding: 0.5rem 0.85rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--primary) 22%, transparent);
    background: color-mix(in srgb, var(--primary) 10%, transparent);
    color: var(--primary);
    font-weight: 700;
    cursor: pointer;
  }

  .upload-result {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .grid-two {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }

  .table-actions {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .row-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  @media (max-width: 720px) {
    .grid-two {
      grid-template-columns: 1fr;
    }

    .section-head {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
