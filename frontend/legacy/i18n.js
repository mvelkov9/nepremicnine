import { createI18n } from 'vue-i18n'
import { useStorage } from '@vueuse/core'
import sl from './locales/sl.json'
import en from './locales/en.json'

const localeStorage = typeof window !== 'undefined' ? useStorage('locale', 'sl') : null
const initialLocale = localeStorage?.value || 'sl'

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale,
  fallbackLocale: 'en',
  messages: { sl, en },
})

export function setLocale(nextLocale) {
  i18n.global.locale.value = nextLocale
  if (localeStorage) {
    localeStorage.value = nextLocale
  }
  if (typeof document !== 'undefined') {
    document.documentElement.lang = nextLocale
    document.cookie = `locale=${nextLocale}; path=/; max-age=31536000; samesite=lax`
  }
}
