<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { Line } from 'vue-chartjs'
  import { useChartColors } from '../../composables/useChartColors'
  import { useI18n } from 'vue-i18n'

  interface TrendPoint {
    year: number | string
    count?: number
    avg_price?: number
    median_price?: number
    avg_price_per_m2?: number
    median_price_per_m2?: number
    by_type?: Record<string, { count?: number; avg_price?: number; median_price?: number }>
  }

  const props = withDefaults(
    defineProps<{
      data: TrendPoint[]
      metric?: 'median_price' | 'avg_price' | 'avg_price_per_m2' | 'count'
      compact?: boolean
      showByType?: boolean
    }>(),
    {
      metric: 'median_price',
      compact: false,
      showByType: false,
    },
  )

  const { t } = useI18n()
  const { colors, palette } = useChartColors()
  const chartKey = ref(0)

  watch(colors, () => {
    chartKey.value++
  })

  const chartData = computed(() => {
    const labels = props.data.map((p) => String(p.year))
    const c = colors.value

    if (props.showByType && props.data.some((p) => p.by_type)) {
      const typeKeys = new Set<string>()
      props.data.forEach((p) => {
        if (p.by_type) Object.keys(p.by_type).forEach((k) => typeKeys.add(k))
      })
      const datasets = [...typeKeys].map((type, i) => ({
        label: type,
        data: props.data.map((p) => {
          const entry = p.by_type?.[type]
          if (!entry) return null
          if (props.metric === 'count') return entry.count ?? null
          if (props.metric === 'avg_price') return entry.avg_price ?? null
          return entry.median_price ?? null
        }),
        borderColor: palette.value[i % palette.value.length],
        backgroundColor: 'transparent',
        tension: 0.3,
        pointRadius: props.compact ? 0 : 3,
        borderWidth: 2,
      }))
      return { labels, datasets }
    }

    const values = props.data.map((p) => {
      if (props.metric === 'count') return p.count ?? null
      if (props.metric === 'avg_price') return p.avg_price ?? null
      if (props.metric === 'avg_price_per_m2') return p.avg_price_per_m2 ?? null
      return p.median_price ?? null
    })

    return {
      labels,
      datasets: [
        {
          label: t(`market.metric_${props.metric}`),
          data: values,
          borderColor: c.primary,
          backgroundColor: props.compact ? 'transparent' : `${c.primary}18`,
          fill: !props.compact,
          tension: 0.3,
          pointRadius: props.compact ? 0 : 4,
          pointHoverRadius: props.compact ? 4 : 6,
          borderWidth: props.compact ? 2 : 2.5,
        },
      ],
    }
  })

  const chartOptions = computed(() => {
    const c = colors.value
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: 'index' as const,
      },
      plugins: {
        legend: {
          display: !props.compact && props.showByType,
          labels: { color: c.text, usePointStyle: true, pointStyle: 'circle' },
        },
        tooltip: {
          enabled: true,
          backgroundColor: c.surface,
          titleColor: c.text,
          bodyColor: c.textSoft,
          borderColor: c.border,
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
        },
      },
      scales: {
        x: {
          display: !props.compact,
          grid: { color: `${c.border}` },
          ticks: { color: c.textSoft },
        },
        y: {
          display: !props.compact,
          grid: { color: `${c.border}` },
          ticks: { color: c.textSoft },
          beginAtZero: false,
        },
      },
    }
  })
</script>

<template>
  <div :class="['trend-chart-wrap', { compact }]">
    <Line :key="chartKey" :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
  .trend-chart-wrap {
    position: relative;
    min-height: 20rem;
  }

  .trend-chart-wrap.compact {
    min-height: 8rem;
  }
</style>
