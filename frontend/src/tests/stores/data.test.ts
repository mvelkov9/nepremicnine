import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import api from '@/composables/useApi'
import { useDataStore } from '@/stores/data'

vi.mock('@/composables/useApi', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('data store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('reuses cached training dataset responses across quick repeated fetches', async () => {
    const dataStore = useDataStore()
    vi.mocked(api.get).mockResolvedValueOnce({
      data: { exists: true, rows: 123 },
    } as never)

    const first = await dataStore.fetchTrainingDataset()
    const second = await dataStore.fetchTrainingDataset()

    expect(api.get).toHaveBeenCalledTimes(1)
    expect(first).toEqual({ exists: true, rows: 123 })
    expect(second).toEqual(first)
  })

  it('bypasses the training dataset cache when force refresh is requested', async () => {
    const dataStore = useDataStore()
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: { exists: true, rows: 123 } } as never)
      .mockResolvedValueOnce({ data: { exists: true, rows: 456 } } as never)

    await dataStore.fetchTrainingDataset()
    const refreshed = await dataStore.fetchTrainingDataset(true)

    expect(api.get).toHaveBeenCalledTimes(2)
    expect(refreshed).toEqual({ exists: true, rows: 456 })
  })
})
