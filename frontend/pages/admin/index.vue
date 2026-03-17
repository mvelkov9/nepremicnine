<script setup>
  import { computed } from 'vue'
  import { useAsyncState } from '@vueuse/core'
  import { useI18n } from 'vue-i18n'
  import { useAuthStore } from '~/legacy/stores/auth'
  import { useDataStore } from '~/legacy/stores/data'
  import { useModelStore } from '~/legacy/stores/model'
  import { getApiErrorMessage } from '~/legacy/utils/apiError'
  import { formatDate, formatNumber, formatPercent } from '~/legacy/utils/format'

  definePageMeta({ middleware: ['admin'] })

  const EMPTY_WORKBENCH = {
    trainingDataset: null,
    qualitySummary: null,
    modelInfo: null,
    activeTraining: null,
    recentRuns: [],
  }

  const { t } = useI18n()
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const modelStore = useModelStore()

  useSeoMeta({
    title: () => `${t('layout.adminWorkbench')} | ${t('app.title')}`,
    description: () => t('layout.page.adminHome'),
  })

  function fmt(value, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  const {
    state: workbenchState,
    isLoading: workbenchLoading,
    error: workbenchFailure,
    execute: refreshWorkbench,
  } = useAsyncState(
    async () => {
      const [trainingDataset, qualitySummary, modelInfo, activeTraining, recentRuns] =
        await Promise.allSettled([
          dataStore.fetchTrainingDataset(),
          dataStore.fetchQualitySummary(),
          modelStore.fetchInfo(),
          modelStore.fetchActiveTraining(),
          modelStore.fetchRuns({ per_page: 4 }),
        ])

      return {
        trainingDataset: trainingDataset.status === 'fulfilled' ? trainingDataset.value : null,
        qualitySummary: qualitySummary.status === 'fulfilled' ? qualitySummary.value : null,
        modelInfo: modelInfo.status === 'fulfilled' ? modelInfo.value : null,
        activeTraining: activeTraining.status === 'fulfilled' ? activeTraining.value : null,
        recentRuns:
          recentRuns.status === 'fulfilled'
            ? recentRuns.value?.items || modelStore.modelRuns || []
            : modelStore.modelRuns || [],
      }
    },
    EMPTY_WORKBENCH,
    {
      immediate: false,
      resetOnExecute: false,
    },
  )

  await refreshWorkbench()

  const pageError = computed(() =>
    workbenchFailure.value ? getApiErrorMessage(workbenchFailure.value, t) : '',
  )

  const trainingDataset = computed(() => workbenchState.value.trainingDataset)
  const qualitySummary = computed(() => workbenchState.value.qualitySummary || {})
  const modelInfo = computed(() => workbenchState.value.modelInfo)
  const activeTraining = computed(() => workbenchState.value.activeTraining)
  const recentRuns = computed(() => workbenchState.value.recentRuns || [])

  const coverageLabel = computed(() => {
    if (qualitySummary.value?.coverage_ratio == null) return t('common.noData')
    return formatPercent(qualitySummary.value.coverage_ratio)
  })

  const overviewCards = computed(() => [
    {
      label: t('data.preparedDataset'),
      value: trainingDataset.value?.exists
        ? fmt(trainingDataset.value.rows || 0)
        : t('dashboard.preparedMissing'),
      meta: trainingDataset.value?.exists
        ? trainingDataset.value.relative_path
        : t('dashboard.preparedMissingDetail'),
      tone: trainingDataset.value?.exists ? 'success' : 'warning',
    },
    {
      label: t('data.coverageRatio'),
      value: coverageLabel.value,
      meta:
        qualitySummary.value?.covered_municipalities != null &&
        qualitySummary.value?.canonical_reference_total != null
          ? `${fmt(qualitySummary.value.covered_municipalities)} / ${fmt(qualitySummary.value.canonical_reference_total)}`
          : t('data.referenceCoverageHint'),
      tone:
        qualitySummary.value?.coverage_ratio != null &&
        Number(qualitySummary.value.coverage_ratio) >= 0.98
          ? 'success'
          : 'warning',
    },
    {
      label: t('data.unresolvedRows'),
      value: fmt(qualitySummary.value?.unresolved_rows || 0),
      meta: t('data.qualityHint'),
      tone:
        qualitySummary.value?.unresolved_rows != null &&
        Number(qualitySummary.value.unresolved_rows) === 0
          ? 'success'
          : 'warning',
    },
    {
      label: t('dashboard.modelStatus'),
      value: modelInfo.value ? t('dashboard.modelReady') : t('dashboard.modelMissing'),
      meta: modelInfo.value
        ? `${formatDate(modelInfo.value.trained_at)} · ${fmt(modelInfo.value.rows || 0)} ${t('data.rows')}`
        : t('dashboard.modelMissingDetail'),
      tone: modelInfo.value ? 'success' : 'warning',
    },
    {
      label: t('model.trainingStatus'),
      value: activeTraining.value?.status || t('common.noData'),
      meta: activeTraining.value?.job_id || auth.user?.full_name || t('layout.adminWorkbench'),
      tone: activeTraining.value ? 'primary' : 'neutral',
    },
  ])

  const sections = computed(() => [
    {
      to: '/admin/podatki',
      title: t('nav.data'),
      description: t('layout.page.data'),
      icon: 'i-lucide-database',
      badge: trainingDataset.value?.exists
        ? `${fmt(trainingDataset.value.rows || 0)} ${t('data.rows')}`
        : t('dashboard.preparedMissing'),
    },
    {
      to: '/admin/priprava',
      title: t('nav.prepare'),
      description: t('layout.page.prepare'),
      icon: 'i-lucide-wand-sparkles',
      badge:
        qualitySummary.value?.coverage_ratio != null ? coverageLabel.value : t('common.noData'),
    },
    {
      to: '/admin/model',
      title: t('nav.model'),
      description: t('layout.page.model'),
      icon: 'i-lucide-chart-column-big',
      badge: modelInfo.value ? t('dashboard.modelReady') : t('dashboard.modelMissing'),
    },
    {
      to: '/admin/diagnostika',
      title: t('nav.diagnostics'),
      description: t('layout.page.diagnostics'),
      icon: 'i-lucide-activity',
      badge: modelInfo.value?.version || t('common.noData'),
    },
    {
      to: '/admin/uporabniki',
      title: t('admin.userManagement'),
      description: t('layout.page.adminUsers'),
      icon: 'i-lucide-users',
      badge: auth.user?.role || t('layout.roleAdmin'),
    },
  ])
</script>

<template>
  <div class="page-frame py-6 lg:py-8">
    <div class="grid gap-6">
      <section
        class="relative overflow-hidden rounded-[2rem] border border-[var(--ui-border)] bg-[var(--surface-panel-strong)] p-6 shadow-[var(--shadow-lg)] lg:p-8"
      >
        <div
          class="pointer-events-none absolute inset-x-0 top-0 h-44 bg-[radial-gradient(circle_at_top_left,color-mix(in_srgb,var(--ui-primary)_16%,transparent)_0%,transparent_62%),radial-gradient(circle_at_top_right,color-mix(in_srgb,var(--ui-secondary)_12%,transparent)_0%,transparent_58%)]"
        ></div>

        <div class="relative grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <div class="grid gap-5">
            <div class="flex flex-wrap items-center gap-3">
              <UBadge
                color="primary"
                variant="soft"
                :label="t('layout.adminWorkbench')"
                class="rounded-full"
              />
              <span class="text-sm text-[var(--ui-text-muted)]">
                {{ auth.user?.full_name || t('layout.roleAdmin') }}
              </span>
            </div>

            <div class="space-y-3">
              <h2
                class="max-w-4xl text-3xl font-semibold tracking-tight text-[var(--ui-text)] lg:text-5xl"
              >
                {{ t('layout.adminWorkbenchTitle') }}
              </h2>
              <p class="max-w-3xl text-base leading-7 text-[var(--ui-text-toned)] lg:text-lg">
                {{ t('layout.adminWorkbenchBody') }}
              </p>
            </div>

            <div class="flex flex-wrap gap-3">
              <UButton to="/admin/model" size="xl">
                {{ t('nav.model') }}
              </UButton>
              <UButton to="/admin/podatki" color="neutral" variant="soft" size="xl">
                {{ t('nav.data') }}
              </UButton>
              <UButton to="/" color="neutral" variant="outline" size="xl">
                {{ t('layout.backToMarket') }}
              </UButton>
            </div>
          </div>

          <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-2">
            <UCard
              v-for="card in overviewCards.slice(0, 4)"
              :key="card.label"
              variant="subtle"
              class="rounded-[1.5rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
            >
              <div class="space-y-3">
                <UBadge
                  :color="card.tone"
                  variant="soft"
                  :label="card.label"
                  class="rounded-full"
                />
                <div class="space-y-1">
                  <p class="text-2xl font-semibold tracking-tight text-[var(--ui-text)]">
                    {{ card.value }}
                  </p>
                  <p class="text-sm leading-6 text-[var(--ui-text-muted)]">
                    {{ card.meta }}
                  </p>
                </div>
              </div>
            </UCard>
          </div>
        </div>
      </section>

      <div v-if="workbenchLoading" class="grid gap-4 lg:grid-cols-2 xl:grid-cols-5">
        <USkeleton v-for="index in 5" :key="index" class="h-36 rounded-[1.6rem]" />
      </div>

      <UCard
        v-else-if="pageError"
        variant="subtle"
        class="rounded-[1.75rem] border border-[color-mix(in_srgb,var(--ui-error)_36%,var(--ui-border))] bg-[var(--surface-panel)]"
      >
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div class="space-y-2">
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-circle-alert" class="text-lg text-[var(--ui-error)]" />
              <p class="text-lg font-semibold text-[var(--ui-text)]">{{ t('common.error') }}</p>
            </div>
            <p class="text-sm leading-6 text-[var(--ui-text-muted)]">{{ pageError }}</p>
          </div>

          <UButton color="neutral" variant="soft" @click="refreshWorkbench">
            {{ t('common.retry') }}
          </UButton>
        </div>
      </UCard>

      <template v-else>
        <section class="grid gap-4 lg:grid-cols-2 xl:grid-cols-5">
          <UCard
            v-for="card in overviewCards"
            :key="card.label"
            variant="subtle"
            class="rounded-[1.6rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
          >
            <div class="space-y-3">
              <UBadge :color="card.tone" variant="soft" :label="card.label" class="rounded-full" />
              <div class="space-y-1">
                <p class="text-2xl font-semibold tracking-tight text-[var(--ui-text)]">
                  {{ card.value }}
                </p>
                <p class="text-sm leading-6 text-[var(--ui-text-muted)]">
                  {{ card.meta }}
                </p>
              </div>
            </div>
          </UCard>
        </section>

        <section class="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <div class="grid gap-4 md:grid-cols-2">
            <NuxtLink
              v-for="section in sections"
              :key="section.to"
              :to="section.to"
              class="rounded-[1.75rem] border border-[var(--ui-border)] bg-[var(--surface-panel)] p-5 shadow-[var(--shadow-sm)] transition duration-200 hover:-translate-y-1 hover:border-[color-mix(in_srgb,var(--ui-primary)_24%,var(--ui-border))]"
            >
              <div class="flex items-start justify-between gap-3">
                <span
                  class="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-[var(--ui-border)] bg-[var(--surface-strong)] text-[var(--ui-primary)]"
                >
                  <UIcon :name="section.icon" class="text-lg" />
                </span>
                <UBadge
                  color="neutral"
                  variant="soft"
                  :label="section.badge"
                  class="rounded-full"
                />
              </div>

              <div class="mt-5 space-y-2">
                <h3 class="text-xl font-semibold tracking-tight text-[var(--ui-text)]">
                  {{ section.title }}
                </h3>
                <p class="text-sm leading-6 text-[var(--ui-text-muted)]">
                  {{ section.description }}
                </p>
              </div>
            </NuxtLink>
          </div>

          <UCard
            variant="subtle"
            class="rounded-[1.75rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
          >
            <template #header>
              <div class="space-y-2">
                <p class="eyebrow">{{ t('layout.workflowHint') }}</p>
                <h3 class="text-xl font-semibold tracking-tight text-[var(--ui-text)]">
                  {{ overviewCards[4].value }}
                </h3>
                <p class="text-sm leading-6 text-[var(--ui-text-muted)]">
                  {{ overviewCards[4].meta }}
                </p>
              </div>
            </template>

            <div class="grid gap-3">
              <div
                class="rounded-[1.4rem] border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4"
              >
                <p
                  class="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ui-text-muted)]"
                >
                  {{ t('data.qualitySummary') }}
                </p>
                <p class="mt-3 text-sm leading-6 text-[var(--ui-text-muted)]">
                  {{ t('data.referenceCoverageHint') }}
                </p>
                <div class="mt-4 flex flex-wrap gap-2">
                  <UBadge
                    color="success"
                    variant="soft"
                    :label="coverageLabel"
                    class="rounded-full"
                  />
                  <UBadge
                    color="warning"
                    variant="soft"
                    :label="`${fmt(qualitySummary.unresolved_rows || 0)} ${t('data.unresolvedRows')}`"
                    class="rounded-full"
                  />
                </div>
              </div>

              <div
                class="rounded-[1.4rem] border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4"
              >
                <p
                  class="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ui-text-muted)]"
                >
                  {{ t('dashboard.modelStatus') }}
                </p>
                <p class="mt-3 text-sm leading-6 text-[var(--ui-text-muted)]">
                  {{
                    modelInfo
                      ? `${formatDate(modelInfo.trained_at)} · ${fmt(modelInfo.rows || 0)} ${t('data.rows')}`
                      : t('dashboard.modelMissingDetail')
                  }}
                </p>
              </div>

              <div
                class="rounded-[1.4rem] border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4"
              >
                <p
                  class="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ui-text-muted)]"
                >
                  {{ t('data.preparedDataset') }}
                </p>
                <p class="mt-3 text-sm leading-6 text-[var(--ui-text-muted)]">
                  {{
                    trainingDataset?.exists
                      ? trainingDataset.relative_path
                      : t('dashboard.preparedMissingDetail')
                  }}
                </p>
              </div>
            </div>
          </UCard>
        </section>

        <UCard
          variant="subtle"
          class="rounded-[1.75rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
        >
          <template #header>
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div class="space-y-2">
                <p class="eyebrow">{{ t('nav.model') }}</p>
                <h3 class="text-xl font-semibold tracking-tight text-[var(--ui-text)]">
                  {{ t('model.trainingTitle') }}
                </h3>
              </div>
              <UButton to="/admin/model" color="neutral" variant="soft">
                {{ t('common.open') }}
              </UButton>
            </div>
          </template>

          <div v-if="recentRuns.length" class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div
              v-for="(run, index) in recentRuns"
              :key="run.id || run.version || index"
              class="rounded-[1.4rem] border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4"
            >
              <div class="flex items-center justify-between gap-3">
                <p class="font-semibold text-[var(--ui-text)]">
                  {{ run.version || run.model_version || `#${index + 1}` }}
                </p>
                <UBadge
                  color="neutral"
                  variant="soft"
                  :label="fmt(run.rows || run.row_count || 0)"
                  class="rounded-full"
                />
              </div>

              <div class="mt-4 space-y-2 text-sm text-[var(--ui-text-muted)]">
                <p>{{ formatDate(run.created_at || run.trained_at) }}</p>
                <p>
                  {{ run.source_csv_path || trainingDataset?.relative_path || t('common.noData') }}
                </p>
              </div>
            </div>
          </div>
          <p v-else class="text-sm text-[var(--ui-text-muted)]">{{ t('common.noData') }}</p>
        </UCard>
      </template>
    </div>
  </div>
</template>
