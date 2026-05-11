<script setup lang="ts">
  import { computed } from 'vue'
  import { RouterLink, useRoute } from 'vue-router'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import AppIcon from '../AppIcon.vue'
  import type { AdminWorkspaceLink } from '../../constants/adminWorkspace'

  interface HeroMetric {
    label: string
    value: string | number
    meta?: string
    tone?: 'default' | 'success' | 'warning'
  }

  const props = withDefaults(
    defineProps<{
      eyebrow: string
      title: string
      description: string
      links?: AdminWorkspaceLink[]
      metrics?: HeroMetric[]
      status?: string
      statusSeverity?: string
      compact?: boolean
    }>(),
    {
      links: () => [],
      metrics: () => [],
      status: '',
      statusSeverity: 'secondary',
      compact: false,
    },
  )

  const route = useRoute()
  const { t } = useI18n()

  const hasLinks = computed(() => props.links.length > 0)
  const hasMetrics = computed(() => props.metrics.length > 0)

  function isActive(link: AdminWorkspaceLink) {
    if (link.to === '/admin') return route.path === link.to
    return route.path === link.to || route.path.startsWith(`${link.to}/`)
  }
</script>

<template>
  <section class="admin-workspace-hero" :class="{ compact }">
    <div class="hero-shell">
      <div class="hero-copy">
        <div class="hero-eyebrow-row">
          <span class="eyebrow">{{ eyebrow }}</span>
          <Tag v-if="status" :severity="statusSeverity" :value="status" rounded />
        </div>
        <h1>{{ title }}</h1>
        <p>{{ description }}</p>
      </div>

      <div v-if="$slots.actions" class="hero-actions">
        <slot name="actions" />
      </div>
    </div>

    <div v-if="hasMetrics" class="hero-metrics">
      <article
        v-for="metric in metrics"
        :key="metric.label"
        class="metric-pill"
        :class="metric.tone ? `tone-${metric.tone}` : 'tone-default'"
      >
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <small>{{ metric.meta || t('common.noData') }}</small>
      </article>
    </div>

    <div v-if="hasLinks" class="hero-nav">
      <RouterLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        class="hero-nav-card"
        :class="{ active: isActive(link) }"
      >
        <span class="hero-nav-icon">
          <AppIcon :name="link.icon" :size="16" />
        </span>
        <div class="hero-nav-copy">
          <strong>{{ t(link.label) }}</strong>
          <small>{{ t(link.description) }}</small>
        </div>
        <span class="hero-nav-arrow">
          <i class="pi pi-arrow-right" aria-hidden="true"></i>
        </span>
      </RouterLink>
    </div>
  </section>
</template>

<style scoped>
  .admin-workspace-hero,
  .hero-metrics,
  .hero-nav {
    display: grid;
    gap: 0.9rem;
  }

  .admin-workspace-hero {
    padding: 1.25rem;
    border: 1px solid color-mix(in srgb, var(--primary-border) 36%, var(--border) 64%);
    border-radius: var(--radius-lg);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 18%, transparent),
        transparent 30%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 95%, transparent),
        transparent 120%
      ),
      var(--surface-hero, var(--surface-soft));
    box-shadow: var(--hero-shadow);
  }

  .hero-shell {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
  }

  .hero-copy {
    display: grid;
    gap: 0.45rem;
    max-width: 62ch;
  }

  .hero-copy h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.6rem, 2.75vw, 2.3rem);
    line-height: 0.98;
  }

  .hero-copy p {
    margin: 0;
    color: var(--text-soft);
    font-size: 0.98rem;
    line-height: 1.55;
  }

  .hero-eyebrow-row {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    flex-wrap: wrap;
  }

  .eyebrow {
    display: inline-flex;
    color: var(--primary-strong);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }

  .hero-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .hero-metrics {
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  }

  .metric-pill {
    display: grid;
    gap: 0.28rem;
    padding: 0.85rem 0.95rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 98%, transparent),
        transparent 120%
      ),
      var(--surface-subtle);
    box-shadow: var(--shadow-sm);
  }

  .metric-pill span,
  .metric-pill small {
    color: var(--text-muted);
  }

  .metric-pill span {
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .metric-pill strong {
    font-size: 1.1rem;
    line-height: 1.1;
  }

  .metric-pill small {
    font-size: var(--text-sm);
  }

  .metric-pill.tone-success {
    background: color-mix(in srgb, var(--surface-subtle) 88%, var(--success) 12%);
  }

  .metric-pill.tone-warning {
    background: color-mix(in srgb, var(--surface-subtle) 88%, var(--warning) 12%);
  }

  .hero-nav {
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .hero-nav-card {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.8rem;
    align-items: start;
    padding: 0.85rem 0.95rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 94%, transparent),
        transparent 120%
      ),
      var(--surface-subtle);
    text-decoration: none;
    color: inherit;
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease;
  }

  .hero-nav-card:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 42%, transparent);
    box-shadow: var(--accent-shadow);
  }

  .hero-nav-card.active {
    background:
      linear-gradient(135deg, color-mix(in srgb, var(--primary) 14%, transparent), transparent 40%),
      color-mix(in srgb, var(--surface-subtle) 84%, var(--primary) 16%);
    border-color: color-mix(in srgb, var(--primary) 56%, transparent);
  }

  .hero-nav-icon {
    width: 2rem;
    height: 2rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 0.85rem;
    background: linear-gradient(145deg, var(--primary), var(--secondary));
    color: var(--primary-contrast);
  }

  .hero-nav-copy {
    display: grid;
    gap: 0.2rem;
  }

  .hero-nav-copy strong {
    font-size: 0.98rem;
  }

  .hero-nav-copy small {
    color: var(--text-soft);
    line-height: 1.35;
  }

  .hero-nav-arrow {
    align-self: center;
    color: var(--text-soft);
  }

  .compact .hero-copy h1 {
    font-size: clamp(1.45rem, 2.5vw, 2rem);
  }

  @media (max-width: 860px) {
    .hero-shell {
      align-items: stretch;
      flex-direction: column;
    }
  }

  @media (max-width: 640px) {
    .admin-workspace-hero {
      padding: 1rem;
    }

    .hero-actions {
      width: 100%;
      flex-direction: column;
      align-items: stretch;
    }

    .hero-actions :deep(.p-button),
    .hero-actions :deep(.p-select),
    .hero-actions :deep(.p-inputtext) {
      width: 100%;
    }

    .hero-nav-card {
      grid-template-columns: auto 1fr;
    }

    .hero-nav-arrow {
      display: none;
    }
  }
</style>
