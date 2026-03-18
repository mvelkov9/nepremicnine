import { useDark, useToggle } from '@vueuse/core'

const isDark = useDark({
  selector: 'html',
  attribute: 'data-theme',
  valueDark: 'dark',
  valueLight: 'light',
  storageKey: 'theme',
})

const toggleDark = useToggle(isDark)

export function useDarkMode() {
  return { isDark, toggleDark }
}
