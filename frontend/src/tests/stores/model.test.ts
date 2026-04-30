import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import api from '@/composables/useApi'
import { useModelStore } from '@/stores/model'

vi.mock('@/composables/useApi', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('model store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('reuses cached model info responses across quick repeated fetches', async () => {
    const modelStore = useModelStore()
    vi.mocked(api.get).mockResolvedValueOnce({
      data: { version: 'v1', trained_at: '2026-04-30T08:00:00Z' },
    } as never)

    const first = await modelStore.fetchInfo()
    const second = await modelStore.fetchInfo()

    expect(api.get).toHaveBeenCalledTimes(1)
    expect(first).toEqual({ version: 'v1', trained_at: '2026-04-30T08:00:00Z' })
    expect(second).toEqual(first)
  })

  it('bypasses the model info cache when force refresh is requested', async () => {
    const modelStore = useModelStore()
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: { version: 'v1' } } as never)
      .mockResolvedValueOnce({ data: { version: 'v2' } } as never)

    await modelStore.fetchInfo()
    const refreshed = await modelStore.fetchInfo(true)

    expect(api.get).toHaveBeenCalledTimes(2)
    expect(refreshed).toEqual({ version: 'v2' })
  })

  it('reuses cached active training responses across quick repeated fetches', async () => {
    const modelStore = useModelStore()
    vi.mocked(api.get).mockResolvedValueOnce({
      data: { job_id: 'train-1', status: 'running', progress: 42 },
    } as never)

    const first = await modelStore.fetchActiveTraining()
    const second = await modelStore.fetchActiveTraining()

    expect(api.get).toHaveBeenCalledTimes(1)
    expect(first).toEqual({ job_id: 'train-1', status: 'running', progress: 42 })
    expect(second).toEqual(first)
  })

  it('reuses cached training job history responses across quick repeated fetches', async () => {
    const modelStore = useModelStore()
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        items: [{ job_id: 'train-1', status: 'running' }],
      },
    } as never)

    const first = await modelStore.fetchJobs()
    const second = await modelStore.fetchJobs()

    expect(api.get).toHaveBeenCalledTimes(1)
    expect(first).toEqual({ items: [{ job_id: 'train-1', status: 'running' }] })
    expect(second).toEqual(first)
  })
})
