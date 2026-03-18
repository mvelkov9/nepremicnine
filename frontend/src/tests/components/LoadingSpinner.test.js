import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LoadingSpinner from '@/components/LoadingSpinner.vue'

describe('LoadingSpinner', () => {
  it('renders the spinner element', () => {
    const wrapper = mount(LoadingSpinner)
    expect(wrapper.find('.loading-spinner').exists()).toBe(true)
  })

  it('has a role of status for accessibility', () => {
    const wrapper = mount(LoadingSpinner)
    expect(wrapper.attributes('role')).toBe('status')
  })

  it('has default aria-label when no label prop', () => {
    const wrapper = mount(LoadingSpinner)
    expect(wrapper.attributes('aria-label')).toBe('Loading')
  })

  it('uses label prop as aria-label', () => {
    const wrapper = mount(LoadingSpinner, {
      props: { label: 'Loading data...' },
    })
    expect(wrapper.attributes('aria-label')).toBe('Loading data...')
  })

  it('does not render label text when label is empty', () => {
    const wrapper = mount(LoadingSpinner)
    expect(wrapper.find('.spinner-label').exists()).toBe(false)
  })

  it('renders label text when label prop is provided', () => {
    const wrapper = mount(LoadingSpinner, {
      props: { label: 'Please wait' },
    })
    expect(wrapper.find('.spinner-label').text()).toBe('Please wait')
  })
})
