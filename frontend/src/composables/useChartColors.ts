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
      chart1: readCssVar('--chart-1', readCssVar('--primary', '#1d4ed8')),
      chart2: readCssVar('--chart-2', readCssVar('--secondary', '#0f766e')),
      chart3: readCssVar('--chart-3', readCssVar('--success', '#15803d')),
      chart4: readCssVar('--chart-4', readCssVar('--warning', '#b7791f')),
      chart5: readCssVar('--chart-5', readCssVar('--danger', '#dc2626')),
      chart6: readCssVar('--chart-6', '#6e62d8'),
      chart7: readCssVar('--chart-7', '#c46d3f'),
      chart8: readCssVar('--chart-8', '#64748b'),
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
    return [c.chart1, c.chart2, c.chart3, c.chart4, c.chart5, c.chart6, c.chart7, c.chart8]
  })

  return { colors, palette }
}
