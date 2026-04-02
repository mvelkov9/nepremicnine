<script setup lang="ts">
  import { watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Dialog from 'primevue/dialog'
  import Tag from 'primevue/tag'
  import { useUiStore } from '../../stores/ui'
  import { useWorkbenchStore } from '../../stores/workbench'
  import { formatDateTime } from '../../utils/format'

  const { t } = useI18n()
  const router = useRouter()
  const ui = useUiStore()
  const workbench = useWorkbenchStore()

  watch(
    () => ui.activityCenterOpen,
    async (open) => {
      if (!open) return
      await Promise.allSettled([workbench.fetchActivityFeed(), workbench.fetchUnreadCount()])
    },
  )

  async function openItem(item: any) {
    if (!item.is_read && item.id.startsWith('event:')) {
      await workbench.markActivityRead(item.id)
    }
    if (item.link) {
      await router.push(item.link)
    }
    ui.toggleActivityCenter(false)
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
            <Tag
              :value="item.is_read ? t('workbench.read') : t('workbench.unread')"
              :severity="item.is_read ? 'secondary' : 'contrast'"
            />
          </div>
          <p>{{ item.body || item.category }}</p>
          <small>{{ formatDateTime(item.created_at) }}</small>
        </div>

        <Button
          size="small"
          severity="secondary"
          text
          icon="pi pi-arrow-right"
          :label="t('common.open')"
          @click="openItem(item)"
        />
      </article>

      <p v-if="!workbench.activityFeed.length" class="muted">
        {{ t('workbench.noActivity') }}
      </p>
    </div>
  </Dialog>
</template>

<style scoped>
  .activity-center {
    display: grid;
    gap: 0.9rem;
  }

  .activity-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.9rem 1rem;
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-soft)) 86%,
      transparent
    );
  }

  .activity-card-main {
    display: grid;
    gap: 0.25rem;
  }

  .activity-card-head {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    flex-wrap: wrap;
  }

  .activity-card p,
  .activity-card small {
    margin: 0;
    color: var(--text-muted);
  }

  @media (max-width: 720px) {
    .activity-card {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
