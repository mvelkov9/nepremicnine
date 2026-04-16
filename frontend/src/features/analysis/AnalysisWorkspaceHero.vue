<script setup lang="ts">
  import Button from 'primevue/button'
  import { useI18n } from 'vue-i18n'
  import SavedWorkspaceMenu from '../../components/workbench/SavedWorkspaceMenu.vue'
  import type { AnalysisHeroMetric, AnalysisHeroPill } from './types'

  defineProps<{
    kicker: string
    title: string
    body: string
    noteTitle: string
    noteBody: string
    metrics: AnalysisHeroMetric[]
    pills: AnalysisHeroPill[]
    workspacePage: string
    workspaceState: { page: string; filters: Record<string, unknown> }
  }>()

  const emit = defineEmits<{
    watch: []
    'open-prediction': []
  }>()

  const { t } = useI18n()
</script>

<template>
  <section class="analysis-hero-shell">
    <div class="analysis-hero-copy">
      <p class="eyebrow">{{ kicker }}</p>
      <h1>{{ title }}</h1>
      <p class="analysis-hero-body">{{ body }}</p>

      <article class="analysis-hero-note">
        <strong>{{ noteTitle }}</strong>
        <p>{{ noteBody }}</p>
      </article>
    </div>

    <div class="analysis-hero-side">
      <div class="analysis-hero-metric-stack">
        <article v-for="card in metrics" :key="card.key" class="analysis-hero-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <p>{{ card.body }}</p>
        </article>
      </div>

      <div class="analysis-hero-pill-grid">
        <article v-for="pill in pills" :key="pill.key" class="analysis-hero-pill">
          <span>{{ pill.label }}</span>
          <strong>{{ pill.value }}</strong>
        </article>
      </div>

      <div class="analysis-hero-actions">
        <SavedWorkspaceMenu :page="workspacePage" :state="workspaceState" />
        <Button
          severity="secondary"
          text
          icon="pi pi-bookmark"
          :label="t('workbench.watch')"
          @click="emit('watch')"
        />
        <Button
          severity="secondary"
          text
          icon="pi pi-calculator"
          :label="t('predict.title')"
          @click="emit('open-prediction')"
        />
        <slot name="actions" />
      </div>
    </div>
  </section>
</template>

<style scoped>
  .analysis-hero-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.08fr) minmax(320px, 0.92fr);
    gap: 1.1rem;
    align-items: stretch;
    padding: 1.2rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 70%, var(--primary) 30%);
    background:
      radial-gradient(circle at top right, color-mix(in srgb, var(--secondary) 12%, transparent), transparent 28%),
      radial-gradient(circle at bottom left, color-mix(in srgb, var(--primary) 10%, transparent), transparent 26%),
      var(--surface-hero);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 24px 48px color-mix(in srgb, var(--shadow-color) 12%, transparent);
  }

  .analysis-hero-copy {
    display: grid;
    gap: 0.55rem;
    align-content: start;
  }

  .analysis-hero-copy h1 {
    margin: 0;
    font-family: var(--font-display);
    letter-spacing: -0.04em;
    text-wrap: balance;
  }

  .analysis-hero-body,
  .analysis-hero-note p,
  .analysis-hero-card p {
    margin: 0;
    color: var(--text-soft);
    line-height: 1.6;
  }

  .analysis-hero-note,
  .analysis-hero-card,
  .analysis-hero-pill {
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 92%, var(--primary) 8%);
    box-shadow: var(--shadow-sm);
  }

  .analysis-hero-note {
    display: grid;
    gap: 0.35rem;
    padding: 0.95rem 1rem;
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 92%, var(--warning) 8%);
  }

  .analysis-hero-note strong,
  .analysis-hero-card strong,
  .analysis-hero-pill strong {
    display: block;
    color: var(--text);
  }

  .analysis-hero-side {
    display: grid;
    gap: 0.85rem;
    align-content: space-between;
  }

  .analysis-hero-metric-stack,
  .analysis-hero-pill-grid,
  .analysis-hero-actions {
    display: grid;
    gap: 0.75rem;
  }

  .analysis-hero-card {
    display: grid;
    gap: 0.3rem;
    padding: 0.95rem 1rem;
  }

  .analysis-hero-card span,
  .analysis-hero-pill span {
    color: var(--text-soft);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .analysis-hero-card strong,
  .analysis-hero-pill strong {
    font-size: 1rem;
    line-height: 1.2;
  }

  .analysis-hero-pill-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .analysis-hero-pill {
    padding: 0.9rem 0.95rem;
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 90%, var(--secondary) 10%);
  }

  .analysis-hero-actions {
    grid-template-columns: repeat(auto-fit, minmax(140px, max-content));
    align-items: center;
  }

  @media (max-width: 920px) {
    .analysis-hero-shell {
      grid-template-columns: 1fr;
    }

    .analysis-hero-pill-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 640px) {
    .analysis-hero-shell {
      padding: 1rem;
    }
  }
</style>
