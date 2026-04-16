<script setup lang="ts">
  import { RouterLink } from 'vue-router'
  import Button from 'primevue/button'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../../components/EmptyState.vue'
  import LoadingSpinner from '../../components/LoadingSpinner.vue'
  import type { ActivityFeedItem } from '../../types/api'
  import {
    activityCategoryLabel,
    activityCategorySeverity,
    activitySummary,
  } from '../../utils/activity'
  import { formatDate } from '../../utils/format'

  defineProps<{
    eyebrow: string
    title: string
    items: ActivityFeedItem[]
    loading?: boolean
    error?: string
  }>()

  const emit = defineEmits<{
    retry: []
  }>()

  const { t } = useI18n()

  function formatCreatedAt(value: string) {
    return formatDate(value, { dateStyle: 'medium' })
  }

  function activityLink(item: ActivityFeedItem) {
    return item.link || undefined
  }

  function hasActivityLink(item: ActivityFeedItem) {
    return Boolean(item.link)
  }

  function activityRowProps(item: ActivityFeedItem) {
    return hasActivityLink(item) ? { to: activityLink(item) } : {}
  }
</script>

<template>
  <section class="card admin-activity-panel">
    <div class="panel-toolbar">
      <div>
        <p class="eyebrow subtle">{{ eyebrow }}</p>
        <h2>{{ title }}</h2>
      </div>
      <Button
        icon="pi pi-refresh"
        severity="secondary"
        outlined
        :label="t('common.retry')"
        :disabled="loading"
        @click="emit('retry')"
      />
    </div>

    <LoadingSpinner v-if="loading" :label="t('common.loading')" />
    <div v-else-if="error" class="state-card state-card-stack" role="alert">
      <EmptyState icon="pi pi-exclamation-triangle" :message="error" />
      <div class="state-card-actions">
        <Button
          size="small"
          severity="secondary"
          outlined
          icon="pi pi-refresh"
          :label="t('common.retry')"
          @click="emit('retry')"
        />
      </div>
    </div>
    <div v-else-if="items.length" class="activity-list">
      <component
        :is="hasActivityLink(item) ? RouterLink : 'article'"
        v-for="item in items"
        :key="item.id"
        v-bind="activityRowProps(item)"
        :class="['activity-row', { 'activity-row--link': hasActivityLink(item) }]"
      >
        <div class="activity-head">
          <strong>{{ item.title }}</strong>
          <div class="activity-meta">
            <Tag
              :severity="activityCategorySeverity(item.category)"
              :value="activityCategoryLabel(item.category, t)"
            />
            <small class="muted">{{ formatCreatedAt(item.created_at) }}</small>
          </div>
        </div>
        <p class="muted">{{ activitySummary(item, t) }}</p>
      </component>
    </div>
    <EmptyState v-else icon="pi pi-compass" :message="t('workbench.noActivity')" />
  </section>
</template>

<style scoped>
  .admin-activity-panel {
    display: grid;
    gap: 1rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--glass-highlight) 88%, transparent),
        transparent 38%
      ),
      var(--surface-panel);
    box-shadow: var(--accent-shadow, var(--shadow-sm));
    padding: 1.3rem;
    min-width: 0;
  }

  .panel-toolbar {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
    padding-bottom: 0.2rem;
    border-bottom: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
  }

  .panel-toolbar h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.18rem, 1.5vw, 1.42rem);
    line-height: 1.05;
  }

  .state-card-stack {
    display: grid;
    gap: 0.85rem;
  }

  .state-card-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }

  .activity-list {
    display: grid;
    gap: 0.75rem;
  }

  .activity-row {
    display: grid;
    gap: 0.3rem;
    padding: 0.95rem 1rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 62%, var(--primary) 38%);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 84%,
      var(--primary) 16%
    );
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }

  .activity-row--link {
    color: inherit;
    text-decoration: none;
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease;
  }

  .activity-row--link:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 46%, transparent);
    box-shadow: 0 14px 28px color-mix(in srgb, var(--shadow-color) 14%, transparent);
  }

  .activity-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .activity-meta {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.55rem;
    flex-wrap: wrap;
  }

  .activity-row p {
    margin: 0.25rem 0 0;
  }

  @media (max-width: 860px) {
    .panel-toolbar {
      align-items: stretch;
    }
  }
</style>
