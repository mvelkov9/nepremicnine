import { ref, watch } from 'vue'

const isDark = ref(false)

function applyTheme(dark) {
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
  localStorage.setItem('theme', dark ? 'dark' : 'light')
}

function initTheme() {
  const stored = localStorage.getItem('theme')
  if (stored) {
    isDark.value = stored === 'dark'
  } else {
    isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
  }
  applyTheme(isDark.value)
}

function toggleDark() {
  isDark.value = !isDark.value
}

watch(isDark, (val) => applyTheme(val))

initTheme()

export function useDarkMode() {
  return { isDark, toggleDark }
}
