import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MetricCard from '@/components/MetricCard.vue'

describe('MetricCard', () => {
  it('renders label and value', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'Average Price', value: '€250,000' },
    })
    expect(wrapper.text()).toContain('Average Price')
    expect(wrapper.text()).toContain('€250,000')
  })

  it('does not render meta element when meta is not provided', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'Price', value: '€100' },
    })
    expect(wrapper.find('small').exists()).toBe(false)
  })

  it('renders meta element when meta is provided', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'Price', value: '€100', meta: 'last 30 days' },
    })
    expect(wrapper.find('small').text()).toBe('last 30 days')
  })

  it('applies the default tone class', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'Price', value: '€100' },
    })
    expect(wrapper.find('article').classes()).toContain('tone-default')
  })

  it('applies a custom tone class', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'Price', value: '€100', tone: 'success' },
    })
    expect(wrapper.find('article').classes()).toContain('tone-success')
  })

  it('applies warning tone class', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'Price', value: '€100', tone: 'warning' },
    })
    expect(wrapper.find('article').classes()).toContain('tone-warning')
  })

  it('renders the value in a strong element', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'Price', value: '€100' },
    })
    expect(wrapper.find('strong').text()).toBe('€100')
  })
})
