import { defineComponent, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import { useViewerQueryState } from '@/composables/useViewerQueryState'

function buildHarness(initialQuery: Record<string, string> = {}) {
  const TestHarness = defineComponent({
    setup() {
      return useViewerQueryState({
        tab: 'overview',
        region: '',
        municipality: '',
        search: '',
      })
    },
    template: '<div />',
  })

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: TestHarness }],
  })

  return { TestHarness, router, initialQuery }
}

async function mountHarness(initialQuery: Record<string, string> = {}) {
  const { TestHarness, router } = buildHarness(initialQuery)
  await router.push({ path: '/', query: initialQuery })
  await router.isReady()

  const wrapper = mount(TestHarness, {
    global: {
      plugins: [router],
    },
  })

  return { wrapper, router }
}

describe('useViewerQueryState', () => {
  it('hydrates state from the current route query', async () => {
    const { wrapper } = await mountHarness({
      tab: 'transactions',
      region: 'Gorenjska',
      search: 'Kranj',
    })

    expect((wrapper.vm as any).state.tab).toBe('transactions')
    expect((wrapper.vm as any).state.region).toBe('Gorenjska')
    expect((wrapper.vm as any).state.search).toBe('Kranj')
  })

  it('writes non-default state back into the route query', async () => {
    const { wrapper, router } = await mountHarness()

    await (wrapper.vm as any).patchState({
      region: 'Osrednjeslovenska',
      municipality: 'Ljubljana',
    })

    await nextTick()
    await flushPromises()

    expect(router.currentRoute.value.query).toMatchObject({
      region: 'Osrednjeslovenska',
      municipality: 'Ljubljana',
    })
  })

  it('counts only active filters and ignores tab/view state', async () => {
    const { wrapper } = await mountHarness({
      tab: 'rankings',
      region: 'Gorenjska',
      search: 'Kranj',
    })

    expect((wrapper.vm as any).activeFilterCount).toBe(2)
    ;(wrapper.vm as any).patchState({
      municipality: 'Škofja Loka',
    })

    await nextTick()

    expect((wrapper.vm as any).activeFilterCount).toBe(3)
  })

  it('removes query params when state resets to defaults', async () => {
    const { wrapper, router } = await mountHarness({
      region: 'Gorenjska',
      municipality: 'Kranj',
    })

    await (wrapper.vm as any).resetState()

    await nextTick()
    await flushPromises()

    expect(router.currentRoute.value.query).toEqual({})
  })
})
