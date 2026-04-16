<script setup lang="ts">
  import { watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Dialog from 'primevue/dialog'
  import Tag from 'primevue/tag'
  import EmptyState from '../EmptyState.vue'
  import { useUiStore } from '../../stores/ui'
  import { useWorkbenchStore } from '../../stores/workbench'
  import type { ActivityFeedItem } from '../../types/api'
  import {
    activityCategoryLabel,
    activityCategorySeverity,
    activitySummary,
  } from '../../utils/activity'
  import { formatDateTime } from '../../utils/format'

  const { t } = useI18n()
  const router = useRouter()
  const ui = useUiStore()
  const workbench = useWorkbenchStore()

  function canMarkItemRead(item: ActivityFeedItem) {
    return !item.is_read && String(item.id || '').startsWith('event:')
  }

  watch(
    () => ui.activityCenterOpen,
    async (open) => {
      if (!open) return
      await Promise.allSettled([workbench.fetchActivityFeed(), workbench.fetchUnreadCount()])
    },
  )

  async function openItem(item: ActivityFeedItem) {
    const shouldMarkRead = canMarkItemRead(item)
    if (shouldMarkRead) {
      await workbench.markActivityRead(item.id)
    }
    if (item.link) {
      await router.push(item.link)
      ui.toggleActivityCenter(false)
      return
    }
  }

  function itemActionLabel(item: ActivityFeedItem) {
    if (item.link) return t('common.open')
    if (canMarkItemRead(item)) return t('workbench.markRead')
    return t('workbench.read')
  }

  function itemActionIcon(item: ActivityFeedItem) {
    if (item.link) return 'pi pi-arrow-right'
    if (canMarkItemRead(item)) return 'pi pi-check'
    return 'pi pi-check-circle'
  }
</script>

<template>
  <Dialog
    v-model:visible="ui.activityCenterOpen"
    modal
    :header="t('workbench.activityCenter')"
    :style="{ width: 'min(92vw, 720px)' }"
  >
    <div class="activity-center">
      <article v-for="item in workbench.activityFeed" :key="item.id" class="activity-card">
        <div class="activity-card-main">
          <div class="activity-card-head">
            <strong>{{ item.title }}</strong>
            <div class="activity-card-tags">
              <Tag
                :value="activityCategoryLabel(item.category, t)"
                :severity="activityCategorySeverity(item.category)"
              />
              <Tag
                :value="item.is_read ? t('workbench.read') : t('workbench.unread')"
                :severity="item.is_read ? 'secondary' : 'contrast'"
              />
            </div>
          </div>
          <p>{{ activitySummary(item, t) }}</p>
          <small>{{ formatDateTime(item.created_at) }}</small>
        </div>

        <Button
          size="small"
          severity="secondary"
          text
          :icon="itemActionIcon(item)"
          :label="itemActionLabel(item)"
          :disabled="!item.link && !canMarkItemRead(item)"
          @click="openItem(item)"
        />
      </article>

      <EmptyState
        v-if="!workbench.activityFeed.length"
        icon="pi pi-compass"
        :message="t('workbench.noActivity')"
      />
    </div>
  </Dialog>
</template>

<style scoped>
  .activity-center {
    display: grid;
    gap: 0.95rem;
  }

  .activity-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1rem 1.05rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 95%, transparent),
        transparent 120%
      ),
      var(--surface-subtle);
    box-shadow: var(--shadow-sm);
  }

  .activity-card-main {
    display: grid;
    gap: 0.3rem;
  }

  .activity-card-head {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    flex-wrap: wrap;
  }

  .activity-card-tags {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    flex-wrap: wrap;
  }

  .activity-card p,
  .activity-card small {
    margin: 0;
    color: var(--text-muted);
  }

  .activity-card strong {
    font-size: 0.97rem;
  }

  @media (max-width: 720px) {
    .activity-card {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
