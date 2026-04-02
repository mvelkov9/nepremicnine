<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { Bar } from 'vue-chartjs'
  import { useChartColors } from '../../composables/useChartColors'

  interface FeatureItem {
    feature: string
    label: string
    importance: number
  }

  const props = withDefaults(
    defineProps<{
      features: FeatureItem[]
      limit?: number
    }>(),
    {
      limit: 15,
    },
  )

  const { colors } = useChartColors()
  const chartKey = ref(0)

  watch(colors, () => {
    chartKey.value++
  })

  const topFeatures = computed(() =>
    [...props.features].sort((a, b) => b.importance - a.importance).slice(0, props.limit),
  )

  const chartData = computed(() => {
    const c = colors.value
    return {
      labels: topFeatures.value.map((f) => f.label || f.feature),
      datasets: [
        {
          data: topFeatures.value.map((f) => f.importance),
          backgroundColor: `${c.secondary}88`,
          borderColor: c.secondary,
          borderWidth: 1,
          borderRadius: 4,
          hoverBackgroundColor: `${c.secondary}bb`,
        },
      ],
    }
  })

  const chartOptions = computed(() => {
    const c = colors.value
    return {
      indexAxis: 'y' as const,
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
          callbacks: {
            label(ctx: any) {
              return ` ${(ctx.raw * 100).toFixed(1)}%`
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: c.border },
          ticks: {
            color: c.textSoft,
            callback(value: number) {
              return `${(value * 100).toFixed(0)}%`
            },
          },
          beginAtZero: true,
        },
        y: {
          grid: { display: false },
          ticks: { color: c.textSoft, font: { size: 11 } },
        },
      },
    }
  })
</script>

<template>
  <div class="importance-chart-wrap">
    <Bar :key="chartKey" :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
  .importance-chart-wrap {
    position: relative;
    min-height: 24rem;
  }
</style>
