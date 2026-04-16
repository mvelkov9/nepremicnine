<script setup lang="ts">
  import Tag from 'primevue/tag'
  import EmptyState from '../../components/EmptyState.vue'

  export type RegionInsightStat = {
    label: string
    value: string
    note?: string
  }

  defineProps<{
    eyebrow: string
    title: string
    description?: string
    tagLabel?: string
    stats: RegionInsightStat[]
    emptyMessage: string
    busy?: boolean
  }>()
</script>

<template>
  <section class="region-insight-panel panel" :aria-busy="busy || undefined">
    <div class="region-insight-panel__head">
      <div class="region-insight-panel__copy">
        <p class="eyebrow subtle">{{ eyebrow }}</p>
        <h2>{{ title }}</h2>
      </div>
      <Tag v-if="tagLabel" severity="secondary" :value="tagLabel" />
    </div>

    <p v-if="description" class="region-insight-panel__description">
      {{ description }}
    </p>

    <div v-if="stats.length" class="region-insight-panel__stats">
      <article v-for="stat in stats" :key="stat.label" class="region-insight-panel__stat">
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
        <small v-if="stat.note">{{ stat.note }}</small>
      </article>
    </div>
    <EmptyState v-else :message="emptyMessage" />

    <div v-if="$slots.actions" class="region-insight-panel__actions">
      <slot name="actions" />
    </div>
  </section>
</template>

<style scoped>
  .region-insight-panel {
    gap: 0.95rem;
    align-content: start;
    border-color: color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 10%, transparent),
        transparent 32%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 94%, var(--primary) 6%),
        var(--surface-panel)
      );
  }

  .region-insight-panel__head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.85rem;
  }

  .region-insight-panel__copy {
    display: grid;
    gap: 0.3rem;
    min-width: 0;
  }

  .region-insight-panel__copy h2 {
    margin: 0;
    text-wrap: balance;
  }

  .region-insight-panel__description {
    margin: 0;
    max-width: 58ch;
    color: var(--text-soft);
    line-height: 1.6;
  }

  .region-insight-panel__stats {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .region-insight-panel__stat {
    display: grid;
    gap: 0.18rem;
    min-width: 0;
    padding: 0.95rem 1rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 70%, var(--content-border-strong) 30%);
    background: var(--surface-soft-muted);
  }

  .region-insight-panel__stat span {
    color: var(--text-soft);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .region-insight-panel__stat strong {
    font-size: 1.1rem;
    line-height: 1.15;
  }

  .region-insight-panel__stat small {
    color: var(--text-muted);
    line-height: 1.45;
  }

  .region-insight-panel__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.7rem;
    align-items: center;
  }

  @media (max-width: 960px) {
    .region-insight-panel__stats {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .region-insight-panel__head {
      flex-direction: column;
      align-items: stretch;
    }

    .region-insight-panel__actions :deep(.p-button) {
      width: 100%;
    }
  }
</style>
