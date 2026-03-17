import { createI18n } from 'vue-i18n'
import sl from './locales/sl.json'
import en from './locales/en.json'

const initialLocale = typeof localStorage !== 'undefined' ? localStorage.getItem('locale') || 'sl' : 'sl'

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale,
  fallbackLocale: 'en',
  messages: { sl, en },
})

export function setLocale(nextLocale) {
  i18n.global.locale.value = nextLocale
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('locale', nextLocale)
  }
  if (typeof document !== 'undefined') {
    document.documentElement.lang = nextLocale
    document.cookie = `locale=${nextLocale}; path=/; max-age=31536000; samesite=lax`
  }
}
