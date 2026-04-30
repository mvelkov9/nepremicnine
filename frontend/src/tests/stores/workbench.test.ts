import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useWorkbenchStore } from '@/stores/workbench'
import api from '@/composables/useApi'

vi.mock('@/composables/useApi', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('workbench store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('deduplicates compare tray entries by id', () => {
    const workbench = useWorkbenchStore()

    workbench.addCompareItem({
      id: 'municipality:ljubljana',
      entity_type: 'municipality',
      label: 'Ljubljana',
      slug: 'ljubljana',
      region: 'Osrednjeslovenska',
    })
    workbench.addCompareItem({
      id: 'municipality:ljubljana',
      entity_type: 'municipality',
      label: 'Ljubljana',
      slug: 'ljubljana',
      region: 'Osrednjeslovenska',
    })

    expect(workbench.compareTray).toHaveLength(1)
  })

  it('keeps distinct route state while deduplicating exact recent-route matches', () => {
    const workbench = useWorkbenchStore()

    workbench.rememberRoute({ label: 'Dashboard', path: '/' })
    workbench.rememberRoute({ label: 'Market', path: '/trg', query: { tab: 'transactions' } })
    workbench.rememberRoute({ label: 'Dashboard refreshed', path: '/', query: { year: '2024' } })
    workbench.rememberRoute({
      label: 'Market updated',
      path: '/trg',
      query: { tab: 'transactions' },
    })

    expect(workbench.recentRoutes).toHaveLength(3)
    expect(workbench.recentRoutes[0]).toMatchObject({
      label: 'Market updated',
      path: '/trg',
      query: { tab: 'transactions' },
    })
  })

  it('exposes only pinned workspaces in pinnedWorkspaces', () => {
    const workbench = useWorkbenchStore()

    workbench.workspaces = [
      {
        id: 1,
        name: 'Pinned market',
        scope: 'private',
        page: 'market',
        filters: {},
        tab: 'overview',
        sort: null,
        columns: [],
        pinned: true,
        created_at: '2026-04-02T08:00:00Z',
        updated_at: '2026-04-02T08:00:00Z',
      },
      {
        id: 2,
        name: 'Unpinned map',
        scope: 'private',
        page: 'map',
        filters: {},
        tab: null,
        sort: null,
        columns: [],
        pinned: false,
        created_at: '2026-04-02T08:00:00Z',
        updated_at: '2026-04-02T08:00:00Z',
      },
    ]

    expect(workbench.pinnedWorkspaces).toHaveLength(1)
    expect(workbench.pinnedWorkspaces[0].name).toBe('Pinned market')
  })

  it('reuses cached admin activity responses across quick repeated fetches', async () => {
    const workbench = useWorkbenchStore()
    vi.mocked(api.get).mockResolvedValueOnce({
      data: [{ id: 'event:1', title: 'Test event' }],
    } as never)

    const first = await workbench.fetchAdminActivity()
    const second = await workbench.fetchAdminActivity()

    expect(api.get).toHaveBeenCalledTimes(1)
    expect(first).toEqual([{ id: 'event:1', title: 'Test event' }])
    expect(second).toEqual(first)
  })

  it('reuses cached training run summaries across quick repeated fetches', async () => {
    const workbench = useWorkbenchStore()
    vi.mocked(api.get).mockResolvedValueOnce({
      data: [{ id: 'run-1', status: 'completed' }],
    } as never)

    const first = await workbench.fetchTrainingRuns()
    const second = await workbench.fetchTrainingRuns()

    expect(api.get).toHaveBeenCalledTimes(1)
    expect(first).toEqual([{ id: 'run-1', status: 'completed' }])
    expect(second).toEqual(first)
  })
})
