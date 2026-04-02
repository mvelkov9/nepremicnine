<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { Bar } from 'vue-chartjs'
  import { useChartColors } from '../../composables/useChartColors'

  interface RegionStat {
    region: string
    count: number
    avg_price?: number
    median_price?: number
    avg_price_per_m2?: number
    median_price_per_m2?: number
  }

  const props = withDefaults(
    defineProps<{
      regions: RegionStat[]
      metric?: 'median_price_per_m2' | 'median_price' | 'count' | 'avg_price_per_m2'
      horizontal?: boolean
    }>(),
    {
      metric: 'median_price_per_m2',
      horizontal: true,
    },
  )

  const { colors } = useChartColors()
  const chartKey = ref(0)

  watch(colors, () => {
    chartKey.value++
  })

  const sorted = computed(() =>
    [...props.regions].sort((a, b) => {
      const va = (a as any)[props.metric] ?? 0
      const vb = (b as any)[props.metric] ?? 0
      return vb - va
    }),
  )

  const chartData = computed(() => {
    const c = colors.value
    return {
      labels: sorted.value.map((r) => r.region),
      datasets: [
        {
          data: sorted.value.map((r) => (r as any)[props.metric] ?? 0),
          backgroundColor: `${c.primary}88`,
          borderColor: c.primary,
          borderWidth: 1,
          borderRadius: 4,
          hoverBackgroundColor: `${c.primary}bb`,
        },
      ],
    }
  })

  const chartOptions = computed(() => {
    const c = colors.value
    return {
      indexAxis: props.horizontal ? ('y' as const) : ('x' as const),
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
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
          grid: { color: props.horizontal ? c.border : 'transparent' },
          ticks: { color: c.textSoft },
          beginAtZero: true,
        },
        y: {
          grid: { color: props.horizontal ? 'transparent' : c.border },
          ticks: { color: c.textSoft },
        },
      },
    }
  })
</script>

<template>
  <div class="region-chart-wrap">
    <Bar :key="chartKey" :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
  .region-chart-wrap {
    position: relative;
    min-height: 22rem;
  }
</style>
