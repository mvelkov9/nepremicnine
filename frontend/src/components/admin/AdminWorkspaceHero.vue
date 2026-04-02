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
    gap: 1rem;
  }

  .admin-workspace-hero {
    padding: 1.2rem;
    border: 1px solid var(--border);
    border-radius: 1.75rem;
    background:
      linear-gradient(
        140deg,
        color-mix(in srgb, var(--surface-strong) 78%, var(--primary) 22%),
        color-mix(in srgb, var(--surface-soft) 86%, transparent)
      ),
      var(--surface-soft);
    box-shadow: var(--shadow-sm);
  }

  .hero-shell {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
  }

  .hero-copy {
    display: grid;
    gap: 0.55rem;
    max-width: 68ch;
  }

  .hero-copy h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.7rem, 3vw, 2.5rem);
    line-height: 1.02;
  }

  .hero-copy p {
    margin: 0;
    color: var(--text-muted);
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
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }

  .hero-actions {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    flex-wrap: wrap;
  }

  .hero-metrics {
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  }

  .metric-pill {
    display: grid;
    gap: 0.28rem;
    padding: 0.95rem 1rem;
    border-radius: 1.15rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background: color-mix(in srgb, var(--surface-strong) 88%, white 12%);
  }

  .metric-pill span,
  .metric-pill small {
    color: var(--text-soft);
  }

  .metric-pill span {
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .metric-pill strong {
    font-size: 1.2rem;
    line-height: 1.1;
  }

  .metric-pill small {
    font-size: 0.82rem;
  }

  .metric-pill.tone-success {
    background: color-mix(in srgb, var(--surface-strong) 80%, var(--success) 20%);
  }

  .metric-pill.tone-warning {
    background: color-mix(in srgb, var(--surface-strong) 84%, var(--warning) 16%);
  }

  .hero-nav {
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .hero-nav-card {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.8rem;
    align-items: start;
    padding: 0.9rem 1rem;
    border-radius: 1.2rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    background: color-mix(in srgb, var(--surface-soft) 90%, white 10%);
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
    box-shadow: 0 16px 28px color-mix(in srgb, var(--shadow-color) 12%, transparent);
  }

  .hero-nav-card.active {
    background: color-mix(in srgb, var(--surface-strong) 78%, var(--primary) 22%);
    border-color: color-mix(in srgb, var(--primary) 56%, transparent);
  }

  .hero-nav-icon {
    width: 2.3rem;
    height: 2.3rem;
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
    color: var(--text-muted);
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
</style>
