import { useDark, useToggle } from '@vueuse/core'
import { watch } from 'vue'

const LIGHT_THEME_COLOR = '#eef4f8'
const DARK_THEME_COLOR = '#08111b'

const isDark = useDark({
  selector: 'html',
  attribute: 'data-theme',
  valueDark: 'dark',
  valueLight: 'light',
  storageKey: 'theme',
})

const toggleDark = useToggle(isDark)

let isThemeModeInitialized = false

function syncThemeMetadata(nextIsDark: boolean) {
  if (typeof document === 'undefined') return

  const themeColor = nextIsDark ? DARK_THEME_COLOR : LIGHT_THEME_COLOR
  const root = document.documentElement
  root.style.colorScheme = nextIsDark ? 'dark' : 'light'

  let themeColorMeta = document.querySelector('meta[name="theme-color"]')
  if (!themeColorMeta) {
    themeColorMeta = document.createElement('meta')
    themeColorMeta.setAttribute('name', 'theme-color')
    document.head.appendChild(themeColorMeta)
  }
  themeColorMeta.setAttribute('content', themeColor)
}

export function initThemeMode() {
  if (isThemeModeInitialized) return
  isThemeModeInitialized = true

  watch(
    isDark,
    (value) => {
      syncThemeMetadata(value)
    },
    { immediate: true },
  )
}

export function useDarkMode() {
  return { isDark, toggleDark }
}
