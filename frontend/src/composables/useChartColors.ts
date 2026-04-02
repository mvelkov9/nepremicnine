import { computed } from 'vue'
import { useDarkMode } from './useDarkMode'

function readCssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

export function useChartColors() {
  const { isDark } = useDarkMode()

  const colors = computed(() => {
    // Force recompute when dark mode changes
    void isDark.value

    return {
      primary: readCssVar('--primary', '#1d4ed8'),
      secondary: readCssVar('--secondary', '#0f766e'),
      success: readCssVar('--success', '#15803d'),
      warning: readCssVar('--warning', '#b7791f'),
      danger: readCssVar('--danger', '#dc2626'),
      textSoft: readCssVar('--text-soft', '#718296'),
      textMuted: readCssVar('--text-muted', '#516277'),
      text: readCssVar('--text', '#0f172a'),
      border: readCssVar('--border', 'rgba(29,78,216,0.1)'),
      surface: readCssVar('--surface-strong', '#ffffff'),
      surfaceSoft: readCssVar('--surface-soft', '#f1f5f9'),
    }
  })

  const palette = computed(() => {
    const c = colors.value
    return [
      c.primary,
      c.secondary,
      c.success,
      c.warning,
      c.danger,
      '#8b5cf6',
      '#ec4899',
      '#f97316',
      '#06b6d4',
      '#84cc16',
    ]
  })

  return { colors, palette }
}
