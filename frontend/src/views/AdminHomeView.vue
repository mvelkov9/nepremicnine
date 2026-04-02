<script setup lang="ts">
  import { computed, onMounted, ref } from 'vue'
  import Button from 'primevue/button'
  import { useI18n } from 'vue-i18n'
  import { RouterLink } from 'vue-router'
  import AppIcon from '../components/AppIcon.vue'
  import AdminWorkspaceHero from '../components/admin/AdminWorkspaceHero.vue'
  import { adminWorkspaceLinks } from '../constants/adminWorkspace'
  import api from '../composables/useApi'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import { useWorkbenchStore } from '../stores/workbench'
  import { formatDateTime, formatNumber } from '../utils/format'

  const { t } = useI18n()
  const dataStore = useDataStore()
  const modelStore = useModelStore()
  const workbench = useWorkbenchStore()
  const userCount = ref<number | null>(null)

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
          ? `R² ${modelStore.info.global_metrics.r2.toFixed(3)}`
          : t('layout.page.diagnostics'),
    },
    {
      label: t('admin.userManagement'),
      value: userCount.value != null ? formatNumber(userCount.value) : t('common.noData'),
      meta: t('admin.totalUsers', { count: userCount.value ?? 0 }),
    },
  ])

  const featuredSections = computed(() =>
    adminWorkspaceLinks.filter((item) => item.to !== '/admin'),
  )

  onMounted(async () => {
    await Promise.allSettled([
      dataStore.fetchTrainingDataset(),
      modelStore.fetchInfo(),
      modelStore.fetchDiagnostics(),
      workbench.fetchAdminActivity(),
      workbench.fetchPrepareRuns(),
      workbench.fetchTrainingRuns(),
      api.get('/api/admin/users').then(({ data }) => {
        userCount.value = data.items?.length || 0
      }),
    ])
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
    >
      <template #actions>
        <RouterLink to="/" class="hero-link">
          <Button
            severity="contrast"
            outlined
            icon="pi pi-arrow-left"
            :label="t('layout.backToMarket')"
          />
        </RouterLink>
      </template>
    </AdminWorkspaceHero>

    <section class="admin-grid">
      <article v-for="section in featuredSections" :key="section.to" class="admin-card">
        <div class="admin-card-head">
          <span class="admin-card-icon">
            <AppIcon :name="section.icon" :size="18" />
          </span>
          <div class="admin-card-copy">
            <p class="eyebrow subtle">{{ t('layout.adminWorkbenchShort') }}</p>
            <h2>{{ t(section.label) }}</h2>
          </div>
        </div>

        <p class="muted">{{ t(section.description) }}</p>

        <RouterLink :to="section.to" class="admin-card-link">
          <Button icon="pi pi-arrow-right" :label="t('common.open')" />
        </RouterLink>
      </article>
    </section>

    <section class="admin-grid admin-grid-wide">
      <article class="admin-card timeline-card">
        <div class="admin-card-head">
          <div class="admin-card-copy">
            <p class="eyebrow subtle">{{ t('workbench.activityCenter') }}</p>
            <h2>{{ t('workbench.adminTimeline') }}</h2>
          </div>
        </div>

        <div v-if="workbench.adminActivity.length" class="timeline-list">
          <div
            v-for="item in workbench.adminActivity.slice(0, 6)"
            :key="item.id"
            class="timeline-row"
          >
            <strong>{{ item.title }}</strong>
            <p class="muted">{{ item.body || item.category }}</p>
          </div>
        </div>
        <p v-else class="muted">{{ t('workbench.noActivity') }}</p>
      </article>

      <article class="admin-card timeline-card">
        <div class="admin-card-head">
          <div class="admin-card-copy">
            <p class="eyebrow subtle">{{ t('nav.prepare') }}</p>
            <h2>{{ t('workbench.recentPrepareRuns') }}</h2>
          </div>
        </div>

        <div v-if="workbench.prepareRuns.length" class="timeline-list">
          <div
            v-for="item in workbench.prepareRuns.slice(0, 5)"
            :key="item.id"
            class="timeline-row"
          >
            <strong>{{ item.title }}</strong>
            <p class="muted">{{ item.summary || item.stage || item.status }}</p>
          </div>
        </div>
        <p v-else class="muted">{{ t('common.noData') }}</p>
      </article>

      <article class="admin-card timeline-card">
        <div class="admin-card-head">
          <div class="admin-card-copy">
            <p class="eyebrow subtle">{{ t('nav.model') }}</p>
            <h2>{{ t('workbench.recentTrainingRuns') }}</h2>
          </div>
        </div>

        <div v-if="workbench.trainingRuns.length" class="timeline-list">
          <div
            v-for="item in workbench.trainingRuns.slice(0, 5)"
            :key="item.id"
            class="timeline-row"
          >
            <strong>{{ item.title }}</strong>
            <p class="muted">{{ item.summary || item.stage || item.status }}</p>
          </div>
        </div>
        <p v-else class="muted">{{ t('common.noData') }}</p>
      </article>
    </section>
  </div>
</template>

<style scoped>
  .admin-home {
    display: grid;
    gap: 1.25rem;
  }

  .hero-link {
    text-decoration: none;
  }

  .admin-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1rem;
  }

  .admin-grid-wide {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .admin-card {
    display: grid;
    gap: 1rem;
    padding: 1.2rem;
    border-radius: 1.45rem;
    border: 1px solid var(--border);
    background:
      linear-gradient(180deg, rgb(255 255 255 / 24%), transparent 32%),
      color-mix(in srgb, var(--surface-soft) 86%, var(--primary) 14%);
    box-shadow: var(--shadow-sm);
  }

  .admin-card-head {
    display: flex;
    align-items: flex-start;
    gap: 0.9rem;
  }

  .admin-card-icon {
    width: 2.9rem;
    height: 2.9rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    border-radius: 1rem;
    background: linear-gradient(145deg, var(--primary), var(--secondary));
    color: var(--primary-contrast);
    box-shadow: 0 18px 34px rgb(45 132 121 / 24%);
  }

  .admin-card-copy {
    display: grid;
    gap: 0.35rem;
  }

  .admin-card-copy h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.25rem;
    line-height: 1.05;
  }

  .admin-card-link {
    text-decoration: none;
  }

  .eyebrow.subtle {
    color: var(--text-soft);
  }

  .timeline-list {
    display: grid;
    gap: 0.8rem;
  }

  .timeline-row {
    padding: 0.85rem 0.95rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background: color-mix(in srgb, var(--surface-strong) 84%, transparent);
  }

  .timeline-row p {
    margin: 0.2rem 0 0;
  }
</style>
