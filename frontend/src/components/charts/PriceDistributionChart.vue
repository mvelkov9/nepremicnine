<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { Bar } from 'vue-chartjs'
  import { useChartColors } from '../../composables/useChartColors'

  const props = defineProps<{
    bins: number[]
    counts: number[]
    binLabels: string[]
  }>()

  const { colors } = useChartColors()
  const chartKey = ref(0)

  watch(colors, () => {
    chartKey.value++
  })

  const chartData = computed(() => {
    const c = colors.value
    return {
      labels: props.binLabels,
      datasets: [
        {
          data: props.counts,
          backgroundColor: `${c.primary}66`,
          borderColor: c.primary,
          borderWidth: 1,
          borderRadius: 4,
          hoverBackgroundColor: `${c.primary}99`,
        },
      ],
    }
  })

  const chartOptions = computed(() => {
    const c = colors.value
    return {
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
          grid: { display: false },
          ticks: {
            color: c.textSoft,
            maxRotation: 45,
            font: { size: 11 },
          },
        },
        y: {
          grid: { color: c.border },
          ticks: { color: c.textSoft },
          beginAtZero: true,
        },
      },
    }
  })
</script>

<template>
  <div class="distribution-chart-wrap">
    <Bar :key="chartKey" :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
  .distribution-chart-wrap {
    position: relative;
    min-height: 20rem;
  }
</style>
