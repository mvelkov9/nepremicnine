import { createI18n } from 'vue-i18n'
import { useLocalStorage } from '@vueuse/core'
import sl from './locales/sl.json'
import en from './locales/en.json'

type Locale = 'sl' | 'en'

// Module-level reactive ref backed by localStorage — safe to call outside setup()
const storedLocale = useLocalStorage<Locale>('locale', 'sl')
const initialLocale: Locale = storedLocale.value === 'en' ? 'en' : 'sl'

function applyDocumentLocale(locale: Locale) {
  if (typeof document === 'undefined') return
  document.documentElement.lang = locale
}

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale,
  fallbackLocale: 'en',
  messages: { sl, en },
})

applyDocumentLocale(initialLocale)

export function setLocale(nextLocale: string) {
  const normalizedLocale: Locale = nextLocale === 'en' ? 'en' : 'sl'
  i18n.global.locale.value = normalizedLocale
  storedLocale.value = normalizedLocale
  applyDocumentLocale(normalizedLocale)
}
