<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Dialog from 'primevue/dialog'
  import InputText from 'primevue/inputtext'
  import ToggleSwitch from 'primevue/toggleswitch'
  import { buildWorkspaceRoute } from '../../constants/workbench'
  import { useWorkbenchStore } from '../../stores/workbench'
  import type { TableViewState } from '../../types/api'
  import { formatDateTime } from '../../utils/format'

  const props = defineProps<{
    page: string
    state: TableViewState
    buttonLabel?: string
  }>()

  const { t } = useI18n()
  const router = useRouter()
  const workbench = useWorkbenchStore()

  const visible = ref(false)
  const workspaceName = ref('')
  const pinned = ref(false)

  const pageWorkspaces = computed(() =>
    workbench.workspaces
      .filter((item) => item.page === props.page)
      .slice()
      .sort((left, right) => {
        if (left.pinned !== right.pinned) return Number(right.pinned) - Number(left.pinned)
        return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
      }),
  )

  watch(visible, async (nextVisible) => {
    if (!nextVisible) return
    await workbench.fetchWorkspaces(props.page)
  })

  async function saveCurrentWorkspace() {
    if (!workspaceName.value.trim()) return
    await workbench.saveWorkspace({
      name: workspaceName.value.trim(),
      page: props.page,
      filters: props.state.filters || {},
      tab: props.state.tab || null,
      sort: props.state.sort || null,
      columns: props.state.columns || [],
      pinned: pinned.value,
    })
    workspaceName.value = ''
    pinned.value = false
  }

  function openWorkspace(item: any) {
    const query = {
      ...(item.filters || {}),
      ...(item.tab ? { tab: item.tab } : {}),
      ...(item.sort ? { sort: item.sort } : {}),
    }
    void router.push(buildWorkspaceRoute(item.page, query))
    visible.value = false
  }

  async function togglePinned(item: any) {
    await workbench.updateWorkspace(item.id, { pinned: !item.pinned })
  }

  async function removeWorkspace(item: any) {
    await workbench.deleteWorkspace(item.id)
  }
</script>

<template>
  <div class="saved-workspace-menu">
    <Button
      severity="secondary"
      outlined
      icon="pi pi-bookmark"
      :label="buttonLabel || t('workbench.saveView')"
      @click="visible = true"
    />

    <Dialog
      v-model:visible="visible"
      modal
      :header="t('workbench.savedViews')"
      :style="{ width: 'min(92vw, 720px)' }"
    >
      <div class="workspace-dialog">
        <section class="workspace-creator">
          <div class="workspace-creator-main">
            <label class="field">
              <span>{{ t('workbench.workspaceName') }}</span>
              <InputText
                v-model="workspaceName"
                :placeholder="t('workbench.workspaceNamePlaceholder')"
              />
            </label>

            <label class="toggle-row">
              <ToggleSwitch v-model="pinned" />
              <span>{{ t('workbench.pinToDashboard') }}</span>
            </label>
          </div>

          <Button
            icon="pi pi-plus"
            :label="t('workbench.saveCurrentView')"
            :disabled="!workspaceName.trim()"
            @click="saveCurrentWorkspace"
          />
        </section>

        <section class="workspace-list">
          <article v-for="item in pageWorkspaces" :key="item.id" class="workspace-card">
            <div class="workspace-card-main">
              <strong>{{ item.name }}</strong>
              <small>{{ formatDateTime(item.updated_at) }}</small>
            </div>

            <div class="workspace-card-actions">
              <Button
                size="small"
                severity="secondary"
                text
                icon="pi pi-external-link"
                :label="t('common.open')"
                @click="openWorkspace(item)"
              />
              <Button
                size="small"
                severity="secondary"
                text
                :icon="item.pinned ? 'pi pi-star-fill' : 'pi pi-star'"
                :label="item.pinned ? t('workbench.unpin') : t('workbench.pin')"
                @click="togglePinned(item)"
              />
              <Button
                size="small"
                severity="danger"
                text
                icon="pi pi-trash"
                :label="t('common.delete')"
                @click="removeWorkspace(item)"
              />
            </div>
          </article>

          <p v-if="!pageWorkspaces.length" class="muted">
            {{ t('workbench.noSavedViews') }}
          </p>
        </section>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
  .workspace-dialog,
  .workspace-creator,
  .workspace-creator-main,
  .workspace-list {
    display: grid;
    gap: 1rem;
  }

  .workspace-creator {
    padding: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    border-radius: var(--radius-md);
    background: var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .workspace-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.95rem 1rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-subtle);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .workspace-card-main {
    display: grid;
    gap: 0.25rem;
  }

  .workspace-card-main strong {
    font-size: 0.96rem;
  }

  .workspace-card-main small {
    color: var(--text-muted);
  }

  .workspace-card-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .field {
    display: grid;
    gap: 0.35rem;
  }

  .field span,
  .toggle-row span {
    color: var(--text-muted);
    font-size: var(--text-sm);
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .toggle-row {
    display: inline-flex;
    align-items: center;
    gap: 0.65rem;
  }

  @media (max-width: 720px) {
    .workspace-card {
      flex-direction: column;
      align-items: stretch;
    }

    .workspace-card-actions {
      display: grid;
      grid-template-columns: 1fr;
    }
  }
</style>
