<script setup lang="ts">
  import { computed } from 'vue'
  import { RouterLink } from 'vue-router'
  import Button from 'primevue/button'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../EmptyState.vue'
  import LoadingSpinner from '../LoadingSpinner.vue'
  import type { ActivityFeedItem } from '../../types/api'
  import {
    activityCategoryLabel,
    activityCategorySeverity,
    activitySummary,
  } from '../../utils/activity'
  import { formatDateTime } from '../../utils/format'

  const props = defineProps<{
    eyebrow: string
    title: string
    description?: string
    items: ActivityFeedItem[]
    loading?: boolean
    error?: string
  }>()

  const emit = defineEmits<{
    retry: []
  }>()

  const { t } = useI18n()

  const featuredItem = computed(() => props.items[0] || null)
  const secondaryItems = computed(() => props.items.slice(1, 5))

  function itemLink(item: ActivityFeedItem) {
    return item.link || null
  }

  function itemActionLabel(item: ActivityFeedItem) {
    return item.link ? t('common.open') : t('workbench.read')
  }
</script>

<template>
  <section class="admin-home-feed">
    <div class="feed-head">
      <div class="feed-copy">
        <p class="eyebrow subtle">{{ eyebrow }}</p>
        <h2>{{ title }}</h2>
        <p v-if="description" class="feed-description">{{ description }}</p>
      </div>

      <Button
        severity="secondary"
        outlined
        icon="pi pi-refresh"
        :label="t('common.retry')"
        :disabled="loading"
        @click="emit('retry')"
      />
    </div>

    <LoadingSpinner v-if="loading" :label="t('common.loading')" />

    <div v-else-if="error" class="feed-state" role="alert">
      <EmptyState icon="pi pi-exclamation-triangle" :message="error" />
      <Button
        severity="secondary"
        outlined
        icon="pi pi-refresh"
        :label="t('common.retry')"
        @click="emit('retry')"
      />
    </div>

    <template v-else-if="featuredItem">
      <component
        :is="itemLink(featuredItem) ? RouterLink : 'article'"
        :to="itemLink(featuredItem) || undefined"
        class="featured-activity"
        :class="{ 'featured-activity--link': Boolean(itemLink(featuredItem)) }"
      >
        <div class="featured-activity-copy">
          <div class="featured-activity-topline">
            <Tag
              :severity="activityCategorySeverity(featuredItem.category)"
              :value="activityCategoryLabel(featuredItem.category, t)"
            />
            <Tag
              :severity="featuredItem.is_read ? 'secondary' : 'contrast'"
              :value="featuredItem.is_read ? t('workbench.read') : t('workbench.unread')"
            />
          </div>
          <h3>{{ featuredItem.title }}</h3>
          <p>{{ activitySummary(featuredItem, t) }}</p>
        </div>

        <div class="featured-activity-meta">
          <small>{{ formatDateTime(featuredItem.created_at) }}</small>
          <span v-if="itemLink(featuredItem)" class="featured-activity-action">
            <span>{{ itemActionLabel(featuredItem) }}</span>
            <i class="pi pi-arrow-right" aria-hidden="true"></i>
          </span>
        </div>
      </component>

      <div v-if="secondaryItems.length" class="secondary-activity-grid">
        <component
          :is="itemLink(item) ? RouterLink : 'article'"
          v-for="item in secondaryItems"
          :key="item.id"
          :to="itemLink(item) || undefined"
          class="secondary-activity"
          :class="{ 'secondary-activity--link': Boolean(itemLink(item)) }"
        >
          <div class="secondary-activity-head">
            <Tag
              :severity="activityCategorySeverity(item.category)"
              :value="activityCategoryLabel(item.category, t)"
            />
            <small>{{ formatDateTime(item.created_at) }}</small>
          </div>
          <strong>{{ item.title }}</strong>
          <p>{{ activitySummary(item, t) }}</p>
          <span v-if="itemLink(item)" class="secondary-activity-action">
            <span>{{ itemActionLabel(item) }}</span>
            <i class="pi pi-arrow-right" aria-hidden="true"></i>
          </span>
        </component>
      </div>
    </template>

    <EmptyState v-else icon="pi pi-compass" :message="t('workbench.noActivity')" />
  </section>
</template>

<style scoped>
  .admin-home-feed {
    display: grid;
    gap: 1rem;
    padding: 1.3rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 16%, transparent),
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

  .feed-head,
  .featured-activity,
  .featured-activity-meta,
  .secondary-activity,
  .secondary-activity-head,
  .secondary-activity-action,
  .featured-activity-action {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .feed-head {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .feed-copy {
    display: grid;
    gap: 0.35rem;
    min-width: 0;
    max-width: 58ch;
  }

  .feed-copy h2,
  .featured-activity h3 {
    margin: 0;
    font-family: var(--font-display);
    text-wrap: balance;
  }

  .feed-copy h2 {
    font-size: clamp(1.25rem, 2vw, 1.55rem);
    line-height: 1.04;
  }

  .feed-description {
    margin: 0;
    color: var(--text-soft);
    line-height: 1.55;
    text-wrap: pretty;
  }

  .feed-state {
    display: grid;
    gap: 0.85rem;
  }

  .featured-activity,
  .secondary-activity {
    text-decoration: none;
    color: inherit;
    border: 1px solid color-mix(in srgb, var(--border) 74%, var(--primary) 26%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-subtle);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 12px 28px color-mix(in srgb, var(--shadow-color) 10%, transparent);
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease;
  }

  .featured-activity--link,
  .secondary-activity--link {
    cursor: pointer;
  }

  .featured-activity:hover,
  .secondary-activity:hover,
  .featured-activity:focus-visible,
  .secondary-activity:focus-visible {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 46%, transparent);
    box-shadow: var(--accent-shadow);
  }

  .featured-activity {
    display: grid;
    gap: 1rem;
    padding: 1.15rem 1.15rem 1rem;
    border-radius: var(--radius-md);
  }

  .featured-activity-copy {
    display: grid;
    gap: 0.55rem;
    min-width: 0;
  }

  .featured-activity-topline {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .featured-activity h3 {
    font-size: clamp(1.08rem, 1.7vw, 1.35rem);
    line-height: 1.05;
  }

  .featured-activity p,
  .secondary-activity p,
  .featured-activity small,
  .secondary-activity small {
    margin: 0;
    color: var(--text-soft);
  }

  .featured-activity p {
    line-height: 1.58;
    max-width: 66ch;
  }

  .featured-activity-meta {
    align-items: end;
  }

  .featured-activity-action,
  .secondary-activity-action {
    color: var(--primary-strong);
    font-weight: 800;
  }

  .secondary-activity-grid {
    display: grid;
    gap: 0.8rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .secondary-activity {
    display: grid;
    align-content: start;
    gap: 0.45rem;
    padding: 0.95rem 1rem;
    border-radius: var(--radius-sm);
  }

  .secondary-activity-head {
    align-items: center;
    flex-wrap: wrap;
  }

  .secondary-activity strong {
    font-size: 0.98rem;
    line-height: 1.3;
    text-wrap: balance;
  }

  .secondary-activity p {
    font-size: 0.92rem;
    line-height: 1.5;
  }

  .secondary-activity-action {
    margin-top: 0.15rem;
    font-size: 0.92rem;
  }

  @media (max-width: 740px) {
    .secondary-activity-grid {
      grid-template-columns: 1fr;
    }

    .featured-activity-meta,
    .secondary-activity-head {
      align-items: flex-start;
    }
  }
</style>
