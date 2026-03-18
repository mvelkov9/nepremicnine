import { createI18n } from 'vue-i18n'
import { useLocalStorage } from '@vueuse/core'
import sl from './locales/sl.json'
import en from './locales/en.json'

// Module-level reactive ref backed by localStorage — safe to call outside setup()
const storedLocale = useLocalStorage('locale', 'sl')

export const i18n = createI18n({
  legacy: false,
  locale: storedLocale.value,
  fallbackLocale: 'en',
  messages: { sl, en },
})

export function setLocale(nextLocale) {
  i18n.global.locale.value = nextLocale
  storedLocale.value = nextLocale
}
