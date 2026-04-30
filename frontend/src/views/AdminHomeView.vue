<script setup lang="ts">
  import { computed, onMounted, reactive, ref } from 'vue'
  import { RouterLink } from 'vue-router'
  import Button from 'primevue/button'
  import { useI18n } from 'vue-i18n'
  import AdminWorkspaceHero from '../components/admin/AdminWorkspaceHero.vue'
  import AdminHomeActivityFeed from '../components/adminHome/AdminHomeActivityFeed.vue'
  import AdminHomeRunList from '../components/adminHome/AdminHomeRunList.vue'
  import { adminWorkspaceLinks } from '../constants/adminWorkspace'
  import api from '../composables/useApi'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import { useUiStore } from '../stores/ui'
  import { useWorkbenchStore } from '../stores/workbench'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatDateTime, formatNumber } from '../utils/format'

  const { t } = useI18n()
  const dataStore = useDataStore()
  const modelStore = useModelStore()
  const ui = useUiStore()
  const workbench = useWorkbenchStore()

  const heroError = ref('')
  const statsLoading = ref(false)
  const statsError = ref('')
  const adminStats = ref<{ total_users?: number } | null>(null)
  const activityLoading = ref(false)
  const activityError = ref('')
  const prepareLoading = ref(false)
  const prepareError = ref('')
  const trainingLoading = ref(false)
  const trainingError = ref('')
  const heroAvailability = reactive({
    trainingDataset: false,
    modelInfo: false,
  })

  const visibleTrainingDataset = computed(() =>
    heroAvailability.trainingDataset ? dataStore.trainingDataset : null,
  )
  const visibleModelInfo = computed(() => (heroAvailability.modelInfo ? modelStore.info : null))

  const summaryCards = computed(() => [
    {
      label: t('nav.data'),
      value: visibleTrainingDataset.value?.exists
        ? formatNumber(visibleTrainingDataset.value.rows || 0)
        : t('common.noData'),
      meta: visibleTrainingDataset.value?.exists
        ? visibleTrainingDataset.value.relative_path
        : t('data.noPreparedDataset'),
      tone: (visibleTrainingDataset.value?.exists ? 'success' : 'warning') as 'success' | 'warning',
    },
    {
      label: t('nav.model'),
      value: visibleModelInfo.value ? t('model.modelReady') : t('model.modelMissing'),
      meta: visibleModelInfo.value?.trained_at
        ? formatDateTime(visibleModelInfo.value.trained_at)
        : t('model.noModel'),
      tone: (visibleModelInfo.value ? 'success' : 'warning') as 'success' | 'warning',
    },
    {
      label: t('nav.diagnostics'),
      value: visibleModelInfo.value ? t('common.open') : t('common.noData'),
      meta:
        visibleModelInfo.value?.global_metrics?.r2 != null
          ? `R2 ${visibleModelInfo.value.global_metrics.r2.toFixed(3)}`
          : t('layout.page.diagnostics'),
    },
    {
      label: t('admin.userManagement'),
      value:
        adminStats.value?.total_users != null
          ? formatNumber(adminStats.value.total_users)
          : t('common.noData'),
      meta: t('admin.totalUsers', { count: adminStats.value?.total_users ?? 0 }),
    },
  ])

  const activityItems = computed(() => workbench.adminActivity.slice(0, 5))
  const prepareRuns = computed(() => workbench.prepareRuns.slice(0, 5))
  const trainingRuns = computed(() => workbench.trainingRuns.slice(0, 5))

  const heroStatus = computed(() => {
    if (heroError.value || statsError.value) return t('common.error')
    if (statsLoading.value) return t('common.loading')
    return t('admin.active')
  })

  const heroStatusSeverity = computed(() => {
    if (heroError.value || statsError.value) return 'danger'
    if (statsLoading.value) return 'secondary'
    return 'success'
  })

  async function loadHero() {
    heroError.value = ''
    statsError.value = ''
    statsLoading.value = true
    const heroRequests = await Promise.allSettled([
      dataStore.fetchTrainingDataset(),
      modelStore.fetchInfo(),
      api.get('/api/admin/stats'),
    ])
    const heroSections = [
      { key: 'trainingDataset' as const, label: t('nav.data') },
      { key: 'modelInfo' as const, label: t('nav.model') },
    ]
    const failedSections: string[] = []
    let firstFailure: unknown = null

    heroRequests.slice(0, heroSections.length).forEach((result, index) => {
      const section = heroSections[index]
      const succeeded = result.status === 'fulfilled'
      heroAvailability[section.key] = succeeded

      if (!succeeded) {
        failedSections.push(section.label)
        if (firstFailure == null) {
          firstFailure = result.reason
        }
      }
    })
    const statsResult = heroRequests[2]

    if (statsResult.status === 'fulfilled') {
      adminStats.value = statsResult.value.data
    } else {
      adminStats.value = null
      statsError.value = getApiErrorMessage(statsResult.reason, t)
    }

    if (failedSections.length) {
      const message = firstFailure ? getApiErrorMessage(firstFailure, t) : t('common.error')
      heroError.value =
        failedSections.length === 1
          ? `${failedSections[0]}: ${message}`
          : `${message} (${failedSections.join(', ')})`
    }
    statsLoading.value = false
  }

  async function loadActivity(force = false) {
    activityLoading.value = true
    activityError.value = ''
    try {
      await workbench.fetchAdminActivity(force)
    } catch (error) {
      activityError.value = getApiErrorMessage(error, t)
    } finally {
      activityLoading.value = false
    }
  }

  async function loadPrepareRuns(force = false) {
    prepareLoading.value = true
    prepareError.value = ''
    try {
      await workbench.fetchPrepareRuns(force)
    } catch (error) {
      prepareError.value = getApiErrorMessage(error, t)
    } finally {
      prepareLoading.value = false
    }
  }

  async function loadTrainingRuns(force = false) {
    trainingLoading.value = true
    trainingError.value = ''
    try {
      await workbench.fetchTrainingRuns(force)
    } catch (error) {
      trainingError.value = getApiErrorMessage(error, t)
    } finally {
      trainingLoading.value = false
    }
  }

  async function reloadAdminHome() {
    void loadActivity()
    void loadPrepareRuns()
    void loadTrainingRuns()
    await loadHero()
  }

  function openActivityCenter() {
    ui.toggleActivityCenter(true)
  }

  onMounted(async () => {
    await reloadAdminHome()
  })
</script>

<template>
  <div class="admin-home">
    <AdminWorkspaceHero
      :eyebrow="t('layout.adminWorkbench')"
      :title="t('layout.adminWorkbenchTitle')"
      :description="t('layout.adminWorkbenchBody')"
      :metrics="summaryCards"
      :links="adminWorkspaceLinks"
      :status="heroStatus"
      :status-severity="heroStatusSeverity"
    >
      <template #actions>
        <Button
          severity="secondary"
          outlined
          icon="pi pi-bell"
          :label="t('workbench.activityCenterShort')"
          @click="openActivityCenter"
        />
        <Button
          :as="RouterLink"
          to="/"
          class="hero-link"
          severity="contrast"
          outlined
          icon="pi pi-arrow-left"
          :label="t('layout.backToMarket')"
        />
      </template>
    </AdminWorkspaceHero>

    <section v-if="heroError || statsError" class="admin-banner" role="alert">
      <div>
        <strong>{{ t('common.error') }}</strong>
        <p class="muted">{{ heroError || statsError }}</p>
      </div>
      <Button
        severity="secondary"
        outlined
        icon="pi pi-refresh"
        :label="t('common.retry')"
        @click="reloadAdminHome"
      />
    </section>

    <section class="admin-home-grid">
      <AdminHomeActivityFeed
        :eyebrow="t('workbench.activityCenter')"
        :title="t('workbench.adminTimeline')"
        :items="activityItems"
        :loading="activityLoading"
        :error="activityError"
        @retry="() => void loadActivity(true)"
      />

      <div class="admin-home-rail">
        <AdminHomeRunList
          :eyebrow="t('nav.prepare')"
          :title="t('workbench.recentPrepareRuns')"
          :items="prepareRuns"
          :loading="prepareLoading"
          :error="prepareError"
          to="/admin/priprava"
          run-type="prepare"
          @retry="() => void loadPrepareRuns(true)"
        />

        <AdminHomeRunList
          :eyebrow="t('nav.model')"
          :title="t('workbench.recentTrainingRuns')"
          :items="trainingRuns"
          :loading="trainingLoading"
          :error="trainingError"
          to="/admin/model"
          run-type="training"
          @retry="() => void loadTrainingRuns(true)"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
  .admin-home {
    display: grid;
    gap: 1rem;
    --page-accent: var(--secondary);
    --page-accent-2: var(--accent);
  }

  .hero-link {
    text-decoration: none;
  }

  .admin-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1.1rem 1.15rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--danger) 28%, var(--border) 72%);
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--page-accent-2) 18%, transparent),
        transparent 38%
      ),
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--danger) 12%, transparent),
        transparent 34%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 98%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .admin-banner strong {
    display: block;
    margin-bottom: 0.18rem;
  }

  .admin-banner p {
    margin: 0;
  }

  .admin-home-grid {
    display: grid;
    gap: 1rem;
    align-items: start;
  }

  .admin-home-rail {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
    align-items: start;
  }

  .admin-home-grid :deep(.admin-home-feed) {
    border-color: color-mix(in srgb, var(--border) 56%, var(--page-accent) 44%);
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--page-accent) 13%, transparent),
        transparent 44%
      ),
      var(--surface-panel);
  }

  .admin-home-grid :deep(.admin-home-run-list) {
    border-color: color-mix(in srgb, var(--border) 56%, var(--page-accent-2) 44%);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--page-accent-2) 13%, transparent),
        transparent 44%
      ),
      var(--surface-panel);
  }

  @media (min-width: 1120px) {
    .admin-home-rail {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 860px) {
    .admin-banner {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
