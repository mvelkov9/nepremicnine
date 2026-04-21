<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Dialog from 'primevue/dialog'
  import InputText from 'primevue/inputtext'
  import ToggleSwitch from 'primevue/toggleswitch'
  import EmptyState from '../EmptyState.vue'
  import LoadingSpinner from '../LoadingSpinner.vue'
  import { buildWorkspaceRoute } from '../../constants/workbench'
  import { useWorkbenchStore } from '../../stores/workbench'
  import type { SavedWorkspace, TableViewState } from '../../types/api'
  import { getApiErrorMessage } from '../../utils/apiError'
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
  const listLoading = ref(false)
  const loadError = ref('')
  const actionError = ref('')
  const saveLoading = ref(false)
  const activeWorkspaceAction = ref<{ id: number; type: 'pin' | 'delete' } | null>(null)
  let loadRequestVersion = 0

  const pageWorkspaces = computed(() =>
    workbench.workspaces
      .filter((item) => item.page === props.page)
      .slice()
      .sort((left, right) => {
        if (left.pinned !== right.pinned) return Number(right.pinned) - Number(left.pinned)
        return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
      }),
  )

  const displayedWorkspaces = computed(() => (loadError.value ? [] : pageWorkspaces.value))
  const actionsLocked = computed(() => saveLoading.value || Boolean(activeWorkspaceAction.value))

  watch(visible, async (nextVisible) => {
    if (!nextVisible) {
      loadRequestVersion += 1
      listLoading.value = false
      loadError.value = ''
      actionError.value = ''
      workspaceName.value = ''
      pinned.value = false
      return
    }
    await loadPageWorkspaces()
  })

  async function loadPageWorkspaces() {
    const requestVersion = ++loadRequestVersion
    listLoading.value = true
    loadError.value = ''
    actionError.value = ''
    try {
      await workbench.fetchWorkspaces(props.page)
    } catch (error) {
      if (requestVersion === loadRequestVersion) {
        loadError.value = getApiErrorMessage(error, t)
      }
    } finally {
      if (requestVersion === loadRequestVersion) {
        listLoading.value = false
      }
    }
  }

  async function saveCurrentWorkspace() {
    if (!workspaceName.value.trim() || saveLoading.value) return
    saveLoading.value = true
    actionError.value = ''
    try {
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
      loadError.value = ''
    } catch (error) {
      actionError.value = getApiErrorMessage(error, t)
    } finally {
      saveLoading.value = false
    }
  }

  function openWorkspace(item: SavedWorkspace) {
    const query = {
      ...(item.filters || {}),
      ...(item.tab ? { tab: item.tab } : {}),
      ...(item.sort ? { sort: item.sort } : {}),
    }
    void router.push(buildWorkspaceRoute(item.page, query))
    visible.value = false
  }

  function isWorkspaceAction(itemId: number, type: 'pin' | 'delete') {
    return activeWorkspaceAction.value?.id === itemId && activeWorkspaceAction.value?.type === type
  }

  async function togglePinned(item: SavedWorkspace) {
    activeWorkspaceAction.value = { id: item.id, type: 'pin' }
    actionError.value = ''
    try {
      await workbench.updateWorkspace(item.id, { pinned: !item.pinned })
      loadError.value = ''
    } catch (error) {
      actionError.value = getApiErrorMessage(error, t)
    } finally {
      if (isWorkspaceAction(item.id, 'pin')) {
        activeWorkspaceAction.value = null
      }
    }
  }

  async function removeWorkspace(item: SavedWorkspace) {
    activeWorkspaceAction.value = { id: item.id, type: 'delete' }
    actionError.value = ''
    try {
      await workbench.deleteWorkspace(item.id)
      loadError.value = ''
    } catch (error) {
      actionError.value = getApiErrorMessage(error, t)
    } finally {
      if (isWorkspaceAction(item.id, 'delete')) {
        activeWorkspaceAction.value = null
      }
    }
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
                :disabled="saveLoading"
              />
            </label>

            <label class="toggle-row">
              <ToggleSwitch v-model="pinned" :disabled="saveLoading" />
              <span>{{ t('workbench.pinToDashboard') }}</span>
            </label>
          </div>

          <Button
            icon="pi pi-plus"
            :label="t('workbench.saveCurrentView')"
            :loading="saveLoading"
            :disabled="!workspaceName.trim() || actionsLocked"
            @click="saveCurrentWorkspace"
          />

          <div v-if="actionError" class="workspace-note workspace-note--error" role="alert">
            <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
            <span>{{ actionError }}</span>
          </div>
        </section>

        <section class="workspace-list">
          <div class="workspace-list-head">
            <span>{{ t('workbench.savedViews') }}</span>
            <Button
              size="small"
              severity="secondary"
              outlined
              icon="pi pi-refresh"
              :label="t('common.refresh')"
              :loading="listLoading"
              :disabled="listLoading || actionsLocked"
              @click="loadPageWorkspaces"
            />
          </div>

          <LoadingSpinner
            v-if="listLoading && !displayedWorkspaces.length"
            :label="t('common.loading')"
          />
          <div v-else-if="loadError" class="state-card state-card-stack" role="alert">
            <EmptyState icon="pi pi-exclamation-triangle" :message="loadError" />
            <div class="state-card-actions">
              <Button
                icon="pi pi-refresh"
                severity="secondary"
                outlined
                :label="t('common.retry')"
                @click="loadPageWorkspaces"
              />
            </div>
          </div>
          <template v-else-if="displayedWorkspaces.length">
            <article v-for="item in displayedWorkspaces" :key="item.id" class="workspace-card">
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
                  :disabled="actionsLocked || listLoading"
                  @click="openWorkspace(item)"
                />
                <Button
                  size="small"
                  severity="secondary"
                  text
                  :icon="item.pinned ? 'pi pi-star-fill' : 'pi pi-star'"
                  :label="item.pinned ? t('workbench.unpin') : t('workbench.pin')"
                  :loading="isWorkspaceAction(item.id, 'pin')"
                  :disabled="
                    saveLoading ||
                    listLoading ||
                    Boolean(activeWorkspaceAction && !isWorkspaceAction(item.id, 'pin'))
                  "
                  @click="togglePinned(item)"
                />
                <Button
                  size="small"
                  severity="danger"
                  text
                  icon="pi pi-trash"
                  :label="t('common.delete')"
                  :loading="isWorkspaceAction(item.id, 'delete')"
                  :disabled="
                    saveLoading ||
                    listLoading ||
                    Boolean(activeWorkspaceAction && !isWorkspaceAction(item.id, 'delete'))
                  "
                  @click="removeWorkspace(item)"
                />
              </div>
            </article>
          </template>
          <EmptyState v-else icon="pi pi-bookmark" :message="t('workbench.noSavedViews')" />
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

  .workspace-list-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .workspace-list-head span {
    color: var(--text-muted);
    font-size: var(--text-sm);
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
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

  .workspace-note {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    padding: 0.8rem 0.9rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--danger) 24%, var(--border) 76%);
    background: color-mix(in srgb, var(--danger) 8%, var(--surface-subtle) 92%);
    color: var(--text-soft);
  }

  .workspace-note i {
    margin-top: 0.1rem;
    color: var(--danger);
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

  .state-card-stack {
    display: grid;
    gap: 0.85rem;
  }

  .state-card-actions {
    display: flex;
    justify-content: flex-start;
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

    .workspace-list-head :deep(.p-button) {
      width: 100%;
    }
  }
</style>
