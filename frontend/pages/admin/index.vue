<script setup lang="ts">
  definePageMeta({ middleware: ['admin'] })

  const { t } = useI18n()
  const api = useApi()

  interface AdminStats {
    model_status: string
    model_version: string | null
    last_training: string | null
    dataset_count: number
    user_count: number
  }

  const stats = ref<AdminStats>({
    model_status: '—',
    model_version: null,
    last_training: null,
    dataset_count: 0,
    user_count: 0,
  })
  async function loadStats() {
    try {
      const [modelRes, usersRes] = await Promise.allSettled([
        api.get<any>('/api/model/info'),
        api.get<any>('/api/admin/users', { params: { per_page: 1 } }),
      ])

      if (modelRes.status === 'fulfilled') {
        const d = modelRes.value.data
        stats.value.model_status = d?.version ? 'ready' : '—'
        stats.value.model_version = d?.version ?? null
        stats.value.last_training = d?.trained_at ?? null
        stats.value.dataset_count = d?.rows ?? 0
      }
      if (usersRes.status === 'fulfilled') {
        stats.value.user_count = usersRes.value.data?.total ?? 0
      }
    } finally {
      /* loaded */
    }
  }

  const { pending: loading } = useAsyncData('admin-stats', loadStats)

  const statusColor = computed(() => {
    const s = stats.value.model_status.toLowerCase()
    if (s === 'ready' || s === 'trained') return 'success'
    if (s === 'training') return 'warning'
    if (s === 'error' || s === 'failed') return 'error'
    return 'neutral'
  })

  const statCards = computed(() => [
    {
      label: t('admin.modelStatus') || 'Model Status',
      value: stats.value.model_status,
      meta: stats.value.model_version ? `v${stats.value.model_version}` : '—',
      icon: 'i-lucide-cpu',
      colorClass: 'stat-primary',
    },
    {
      label: t('admin.datasetCount') || 'Datasets',
      value: formatNumber(stats.value.dataset_count),
      meta: t('admin.datasetsAvailable') || 'available',
      icon: 'i-lucide-database',
      colorClass: 'stat-blue',
    },
    {
      label: t('admin.userCount') || 'Users',
      value: formatNumber(stats.value.user_count),
      meta: t('admin.registeredUsers') || 'registered',
      icon: 'i-lucide-users',
      colorClass: 'stat-green',
    },
    {
      label: t('admin.lastTraining') || 'Last Training',
      value: stats.value.last_training ? formatDate(stats.value.last_training) : '—',
      meta: stats.value.last_training
        ? t('admin.trainingCompleted') || 'completed'
        : t('admin.noTraining') || 'never run',
      icon: 'i-lucide-clock',
      colorClass: 'stat-gray',
    },
  ])

  const adminLinks = [
    {
      to: '/admin/podatki',
      label: t('admin.data') || 'Data',
      description: t('admin.dataDescription') || 'Manage raw transaction datasets',
      icon: 'i-lucide-database',
      colorClass: 'link-blue',
    },
    {
      to: '/admin/priprava',
      label: t('admin.prepare') || 'Prepare',
      description: t('admin.prepareDescription') || 'Process and clean data for training',
      icon: 'i-lucide-wrench',
      colorClass: 'link-amber',
    },
    {
      to: '/admin/model',
      label: t('admin.model') || 'Model',
      description: t('admin.modelDescription') || 'Train, evaluate and deploy models',
      icon: 'i-lucide-cpu',
      colorClass: 'link-primary',
    },
    {
      to: '/admin/diagnostika',
      label: t('admin.diagnostics') || 'Diagnostics',
      description: t('admin.diagnosticsDescription') || 'System health and performance',
      icon: 'i-lucide-activity',
      colorClass: 'link-green',
    },
    {
      to: '/admin/uporabniki',
      label: t('admin.users') || 'Users',
      description: t('admin.usersDescription') || 'Manage user accounts and roles',
      icon: 'i-lucide-users',
      colorClass: 'link-purple',
    },
  ]
</script>

<template>
  <div class="admin-home">
    <!-- Header -->
    <section class="admin-hero">
      <div class="admin-hero-copy">
        <p class="eyebrow">{{ t('admin.title') || 'Administration' }}</p>
        <h1>{{ t('admin.homeTitle') || 'Control Panel' }}</h1>
        <p class="muted">
          {{
            t('admin.homeDescription') || 'Manage datasets, models, users and system diagnostics.'
          }}
        </p>
      </div>

      <div class="admin-hero-status">
        <USkeleton v-if="loading" class="h-8 w-32 rounded-full" />
        <UBadge
          v-else
          :label="stats.model_status"
          :color="statusColor"
          variant="soft"
          size="lg"
          icon="i-lucide-cpu"
        />
      </div>
    </section>

    <!-- Stat cards -->
    <section class="admin-stats">
      <template v-if="loading">
        <USkeleton v-for="n in 4" :key="n" class="h-24 w-full rounded-xl" />
      </template>
      <template v-else>
        <KpiCard v-for="card in statCards" :key="card.label" :label="card.label" :value="card.value" :meta="card.meta" :icon="card.icon" :color-class="card.colorClass" />
      </template>
    </section>

    <!-- Navigation cards -->
    <section class="admin-nav-grid">
      <NuxtLink
        v-for="link in adminLinks"
        :key="link.to"
        :to="link.to"
        class="admin-link-card"
        :class="link.colorClass"
      >
        <div class="admin-link-icon">
          <UIcon :name="link.icon" class="w-5 h-5" />
        </div>
        <div class="admin-link-copy">
          <strong>{{ link.label }}</strong>
          <p>{{ link.description }}</p>
        </div>
        <UIcon name="i-lucide-arrow-right" class="admin-link-arrow w-4 h-4" />
      </NuxtLink>
    </section>
  </div>
</template>

<style scoped>
  .admin-home {
    display: grid;
    gap: 1.15rem;
  }

  /* Hero */
  .admin-hero {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
    padding: 1.4rem 1.5rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--primary) 14%, transparent),
        transparent 38%
      ),
      linear-gradient(145deg, var(--surface-strong), var(--surface-soft));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
  }

  .admin-hero-copy h1 {
    margin: 0.3rem 0 0.4rem;
    font-family: var(--font-display);
    font-size: clamp(1.6rem, 1rem + 2vw, 2.4rem);
    line-height: 1.05;
    letter-spacing: -0.04em;
  }

  .admin-hero-copy p {
    margin: 0;
    max-width: 54ch;
    line-height: 1.6;
  }

  .admin-hero-status {
    display: flex;
    align-items: flex-start;
    padding-top: 0.2rem;
  }

  /* Stats grid */
  .admin-stats {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 1rem;
  }

  /* Admin nav cards */
  .admin-nav-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(22rem, 1fr));
    gap: 1rem;
  }

  .admin-link-card {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.2rem 1.3rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    background: var(--surface-panel);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      var(--shadow-sm);
    color: inherit;
    text-decoration: none;
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease,
      background 160ms ease;
  }

  .admin-link-card:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 26%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--primary) 8%, var(--surface-panel)),
      color-mix(in srgb, var(--secondary) 6%, var(--surface-panel))
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 20px 36px rgb(15 23 42 / 10%);
  }

  .admin-link-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 3rem;
    height: 3rem;
    border-radius: 1.1rem;
    border: 1px solid color-mix(in srgb, var(--primary) 18%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--primary) 14%, transparent),
      color-mix(in srgb, var(--secondary) 8%, transparent)
    );
    color: var(--primary);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 10px 18px rgb(15 23 42 / 8%);
    transition:
      transform 160ms ease,
      box-shadow 160ms ease;
  }

  .admin-link-card:hover .admin-link-icon {
    transform: translateY(-1px);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 16%),
      0 14px 24px rgb(15 23 42 / 12%);
  }

  .admin-link-copy {
    flex: 1;
    min-width: 0;
  }

  .admin-link-copy strong {
    display: block;
    font-size: 0.98rem;
    font-weight: 800;
  }

  .admin-link-copy p {
    margin: 0.2rem 0 0;
    color: var(--text-muted);
    font-size: 0.84rem;
    line-height: 1.5;
  }

  .admin-link-arrow {
    color: var(--text-muted);
    flex-shrink: 0;
    transition:
      transform 160ms ease,
      color 160ms ease;
  }

  .admin-link-card:hover .admin-link-arrow {
    transform: translateX(3px);
    color: var(--primary);
  }

  /* Color variants for link cards */
  .link-blue .admin-link-icon {
    color: var(--ui-color-blue-500, var(--primary));
    border-color: color-mix(in srgb, var(--ui-color-blue-500, var(--primary)) 18%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--ui-color-blue-500, var(--primary)) 14%, transparent),
      transparent
    );
  }
  .link-amber .admin-link-icon {
    color: var(--ui-color-amber-500, #f59e0b);
    border-color: color-mix(in srgb, #f59e0b 18%, var(--border));
    background: linear-gradient(145deg, color-mix(in srgb, #f59e0b 14%, transparent), transparent);
  }
  .link-green .admin-link-icon {
    color: var(--success);
    border-color: color-mix(in srgb, var(--success) 18%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--success) 14%, transparent),
      transparent
    );
  }
  .link-purple .admin-link-icon {
    color: var(--ui-color-violet-500, #8b5cf6);
    border-color: color-mix(in srgb, #8b5cf6 18%, var(--border));
    background: linear-gradient(145deg, color-mix(in srgb, #8b5cf6 14%, transparent), transparent);
  }

  @media (max-width: 900px) {
    .admin-stats {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .admin-nav-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 600px) {
    .admin-stats {
      grid-template-columns: 1fr;
    }
  }
</style>
