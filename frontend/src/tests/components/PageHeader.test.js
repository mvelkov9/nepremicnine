import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PageHeader from '@/components/PageHeader.vue'

describe('PageHeader', () => {
  it('renders the default title as an h1', () => {
    const wrapper = mount(PageHeader, {
      props: {
        title: 'Workspace title',
      },
    })

    expect(wrapper.find('h1.page-header-title').exists()).toBe(true)
    expect(wrapper.find('h2.page-header-title').exists()).toBe(false)
  })

  it('renders compact titles as h2 headings', () => {
    const wrapper = mount(PageHeader, {
      props: {
        title: 'Section title',
        description: 'Nested section copy',
        compact: true,
      },
    })

    expect(wrapper.find('h1.page-header-title').exists()).toBe(false)
    expect(wrapper.find('h2.page-header-title').text()).toBe('Section title')
    expect(wrapper.text()).toContain('Nested section copy')
  })
})
