import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'
import api from '../composables/useApi'
import { describeRoute } from '../constants/workbench'
import type {
  ActivityFeedItem,
  AdminRunDetail,
  AdminRunSummary,
  CompareTrayItem,
  SavedWorkspace,
  TableViewState,
  WatchlistFeedItem,
  WatchlistItem,
} from '../types/api'

interface RecentRouteItem {
  label: string
  path: string
  query?: Record<string, unknown>
  page?: string
}

interface SaveWorkspacePayload extends TableViewState {
  name: string
}

function recentRouteKey(item: RecentRouteItem) {
  return describeRoute(item.path, item.query || {})
}

export const useWorkbenchStore = defineStore('workbench', () => {
  const workspaces = ref<SavedWorkspace[]>([])
  const watchlists = ref<WatchlistItem[]>([])
  const watchlistFeed = ref<WatchlistFeedItem[]>([])
  const activityFeed = ref<ActivityFeedItem[]>([])
  const unreadCount = ref(0)
  const adminActivity = ref<ActivityFeedItem[]>([])
  const prepareRuns = ref<AdminRunSummary[]>([])
  const trainingRuns = ref<AdminRunSummary[]>([])
  const selectedPrepareRun = ref<AdminRunDetail | null>(null)
  const selectedTrainingRun = ref<AdminRunDetail | null>(null)

  const compareTray = useLocalStorage<CompareTrayItem[]>('workbench_compare_tray', [])
  const recentRoutes = useLocalStorage<RecentRouteItem[]>('workbench_recent_routes', [])
  const recentMunicipalities = useLocalStorage<CompareTrayItem[]>(
    'workbench_recent_municipalities',
    [],
  )

  const pinnedWorkspaces = computed(() => workspaces.value.filter((item) => item.pinned))

  async function fetchWorkspaces(page?: string) {
    const { data } = await api.get<SavedWorkspace[]>('/api/workspaces', {
      params: page ? { page } : undefined,
    })
    if (page) {
      workspaces.value = [...(data || []), ...workspaces.value.filter((item) => item.page !== page)]
    } else {
      workspaces.value = data || []
    }
    return data
  }

  async function saveWorkspace(payload: SaveWorkspacePayload) {
    const { data } = await api.post<SavedWorkspace>('/api/workspaces', {
      name: payload.name,
      scope: 'private',
      page: payload.page,
      filters: payload.filters || {},
      tab: payload.tab || null,
      sort: payload.sort || null,
      columns: payload.columns || [],
      pinned: !!payload.pinned,
    })
    workspaces.value = [data, ...workspaces.value.filter((item) => item.id !== data.id)]
    return data
  }

  async function updateWorkspace(workspaceId: number, payload: Partial<SaveWorkspacePayload>) {
    const { data } = await api.patch<SavedWorkspace>(`/api/workspaces/${workspaceId}`, payload)
    workspaces.value = workspaces.value.map((item) => (item.id === workspaceId ? data : item))
    return data
  }

  async function deleteWorkspace(workspaceId: number) {
    await api.delete(`/api/workspaces/${workspaceId}`)
    workspaces.value = workspaces.value.filter((item) => item.id !== workspaceId)
  }

  async function fetchWatchlists(entityType?: string) {
    const { data } = await api.get<WatchlistItem[]>('/api/watchlists', {
      params: entityType ? { entity_type: entityType } : undefined,
    })
    watchlists.value = data || []
    return data
  }

  async function addWatchlistItem(payload: {
    entity_type: string
    entity_key: string
    display_label: string
    metadata?: Record<string, unknown>
  }) {
    const { data } = await api.post<WatchlistItem>('/api/watchlists', {
      ...payload,
      metadata: payload.metadata || {},
    })
    watchlists.value = [data, ...watchlists.value.filter((item) => item.id !== data.id)]
    return data
  }

  async function removeWatchlistItem(watchlistId: number) {
    await api.delete(`/api/watchlists/${watchlistId}`)
    watchlists.value = watchlists.value.filter((item) => item.id !== watchlistId)
  }

  async function fetchWatchlistFeed() {
    const { data } = await api.get<WatchlistFeedItem[]>('/api/watchlists/feed')
    watchlistFeed.value = data || []
    return data
  }

  async function fetchActivityFeed() {
    const { data } = await api.get<ActivityFeedItem[]>('/api/activity/feed')
    activityFeed.value = data || []
    return data
  }

  async function fetchUnreadCount() {
    const { data } = await api.get<{ unread: number }>('/api/activity/unread')
    unreadCount.value = Number(data?.unread || 0)
    return unreadCount.value
  }

  async function markActivityRead(activityId: string) {
    const numericId = Number(String(activityId).replace('event:', ''))
    if (!Number.isFinite(numericId)) return unreadCount.value
    const { data } = await api.post<{ unread: number }>(`/api/activity/${numericId}/read`)
    unreadCount.value = Number(data?.unread || 0)
    activityFeed.value = activityFeed.value.map((item) =>
      item.id === activityId ? { ...item, is_read: true } : item,
    )
    return unreadCount.value
  }

  async function fetchAdminActivity() {
    const { data } = await api.get<ActivityFeedItem[]>('/api/admin/activity')
    adminActivity.value = data || []
    return data
  }

  async function fetchPrepareRuns() {
    const { data } = await api.get<AdminRunSummary[]>('/api/admin/prepare-runs')
    prepareRuns.value = data || []
    return data
  }

  async function fetchTrainingRuns() {
    const { data } = await api.get<AdminRunSummary[]>('/api/admin/training-runs')
    trainingRuns.value = data || []
    return data
  }

  async function fetchPrepareRunDetail(jobId: string) {
    const { data } = await api.get<AdminRunDetail>(`/api/admin/prepare-runs/${jobId}`)
    selectedPrepareRun.value = data
    return data
  }

  async function fetchTrainingRunDetail(jobId: string) {
    const { data } = await api.get<AdminRunDetail>(`/api/admin/training-runs/${jobId}`)
    selectedTrainingRun.value = data
    return data
  }

  function addCompareItem(item: CompareTrayItem) {
    if (compareTray.value.some((entry) => entry.id === item.id)) return
    compareTray.value = [item, ...compareTray.value].slice(0, 8)
  }

  function removeCompareItem(itemId: string) {
    compareTray.value = compareTray.value.filter((item) => item.id !== itemId)
  }

  function rememberMunicipality(item: CompareTrayItem) {
    recentMunicipalities.value = [
      item,
      ...recentMunicipalities.value.filter((entry) => entry.id !== item.id),
    ].slice(0, 8)
  }

  function rememberRoute(item: RecentRouteItem) {
    const key = recentRouteKey(item)
    recentRoutes.value = [
      item,
      ...recentRoutes.value.filter((entry) => recentRouteKey(entry) !== key),
    ].slice(0, 10)
  }

  return {
    workspaces,
    watchlists,
    watchlistFeed,
    activityFeed,
    unreadCount,
    adminActivity,
    prepareRuns,
    trainingRuns,
    selectedPrepareRun,
    selectedTrainingRun,
    compareTray,
    recentRoutes,
    recentMunicipalities,
    pinnedWorkspaces,
    fetchWorkspaces,
    saveWorkspace,
    updateWorkspace,
    deleteWorkspace,
    fetchWatchlists,
    addWatchlistItem,
    removeWatchlistItem,
    fetchWatchlistFeed,
    fetchActivityFeed,
    fetchUnreadCount,
    markActivityRead,
    fetchAdminActivity,
    fetchPrepareRuns,
    fetchTrainingRuns,
    fetchPrepareRunDetail,
    fetchTrainingRunDetail,
    addCompareItem,
    removeCompareItem,
    rememberMunicipality,
    rememberRoute,
  }
})
