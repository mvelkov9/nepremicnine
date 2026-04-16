<script setup lang="ts">
  import { computed, onMounted, ref } from 'vue'
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

  const pageReady = ref(false)
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

  const summaryCards = computed(() => [
    {
      label: t('nav.data'),
      value: dataStore.trainingDataset?.exists
        ? formatNumber(dataStore.trainingDataset.rows || 0)
        : t('common.noData'),
      meta: dataStore.trainingDataset?.exists
        ? dataStore.trainingDataset.relative_path
        : t('data.noPreparedDataset'),
      tone: (dataStore.trainingDataset?.exists ? 'success' : 'warning') as 'success' | 'warning',
    },
    {
      label: t('nav.model'),
      value: modelStore.info ? t('model.modelReady') : t('model.modelMissing'),
      meta: modelStore.info?.trained_at
        ? formatDateTime(modelStore.info.trained_at)
        : t('model.noModel'),
      tone: (modelStore.info ? 'success' : 'warning') as 'success' | 'warning',
    },
    {
      label: t('nav.diagnostics'),
      value: modelStore.diagnostics ? t('common.open') : t('common.noData'),
      meta:
        modelStore.info?.global_metrics?.r2 != null
          ? `R2 ${modelStore.info.global_metrics.r2.toFixed(3)}`
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
    if (statsLoading.value || !pageReady.value) return t('common.loading')
    return t('admin.active')
  })

  const heroStatusSeverity = computed(() => {
    if (heroError.value || statsError.value) return 'danger'
    if (statsLoading.value || !pageReady.value) return 'secondary'
    return 'success'
  })

  async function loadHero() {
    heroError.value = ''
    statsError.value = ''
    statsLoading.value = true
    try {
      await Promise.all([
        dataStore.fetchTrainingDataset(),
        modelStore.fetchInfo(),
        modelStore.fetchDiagnostics(),
      ])
    } catch (error) {
      heroError.value = getApiErrorMessage(error, t)
    } finally {
      statsLoading.value = false
    }

    try {
      const { data } = await api.get('/api/admin/stats')
      adminStats.value = data
    } catch (error) {
      adminStats.value = null
      statsError.value = getApiErrorMessage(error, t)
    }
  }

  async function loadActivity() {
    activityLoading.value = true
    activityError.value = ''
    try {
      await workbench.fetchAdminActivity()
    } catch (error) {
      activityError.value = getApiErrorMessage(error, t)
    } finally {
      activityLoading.value = false
    }
  }

  async function loadPrepareRuns() {
    prepareLoading.value = true
    prepareError.value = ''
    try {
      await workbench.fetchPrepareRuns()
    } catch (error) {
      prepareError.value = getApiErrorMessage(error, t)
    } finally {
      prepareLoading.value = false
    }
  }

  async function loadTrainingRuns() {
    trainingLoading.value = true
    trainingError.value = ''
    try {
      await workbench.fetchTrainingRuns()
    } catch (error) {
      trainingError.value = getApiErrorMessage(error, t)
    } finally {
      trainingLoading.value = false
    }
  }

  async function reloadAdminHome() {
    pageReady.value = false
    await Promise.allSettled([loadHero(), loadActivity(), loadPrepareRuns(), loadTrainingRuns()])
    pageReady.value = true
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
        :loading="!pageReady || activityLoading"
        :error="activityError"
        @retry="loadActivity"
      />

      <div class="admin-home-rail">
        <AdminHomeRunList
          :eyebrow="t('nav.prepare')"
          :title="t('workbench.recentPrepareRuns')"
          :items="prepareRuns"
          :loading="!pageReady || prepareLoading"
          :error="prepareError"
          to="/admin/priprava"
          run-type="prepare"
          @retry="loadPrepareRuns"
        />

        <AdminHomeRunList
          :eyebrow="t('nav.model')"
          :title="t('workbench.recentTrainingRuns')"
          :items="trainingRuns"
          :loading="!pageReady || trainingLoading"
          :error="trainingError"
          to="/admin/model"
          run-type="training"
          @retry="loadTrainingRuns"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
  .admin-home {
    display: grid;
    gap: 1rem;
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
  }

  @media (min-width: 1120px) {
    .admin-home-grid {
      grid-template-columns: minmax(0, 1.35fr) minmax(20rem, 0.95fr);
    }

    .admin-home-rail {
      position: sticky;
      top: 1rem;
    }
  }

  @media (max-width: 860px) {
    .admin-banner {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
