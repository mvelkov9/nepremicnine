<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { Doughnut } from 'vue-chartjs'
  import { useI18n } from 'vue-i18n'
  import { useChartColors } from '../../composables/useChartColors'
  import { useFormat } from '../../composables/useFormat'

  interface TypeItem {
    property_type: string
    count: number
    share: number
  }

  const props = defineProps<{
    items: TypeItem[]
  }>()

  const { t } = useI18n()
  const { formatType } = useFormat()
  const { colors, palette } = useChartColors()
  const chartKey = ref(0)

  watch(colors, () => {
    chartKey.value++
  })

  const chartData = computed(() => {
    return {
      labels: props.items.map((i) => formatType(i.property_type)),
      datasets: [
        {
          data: props.items.map((i) => i.count),
          backgroundColor: props.items.map(
            (_, idx) => `${palette.value[idx % palette.value.length]}cc`,
          ),
          borderColor: props.items.map((_, idx) => palette.value[idx % palette.value.length]),
          borderWidth: 2,
          hoverOffset: 6,
        },
      ],
    }
  })

  const chartOptions = computed(() => {
    const c = colors.value
    return {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '55%',
      plugins: {
        legend: {
          position: 'right' as const,
          labels: {
            color: c.text,
            usePointStyle: true,
            pointStyle: 'circle',
            padding: 14,
            font: { size: 12 },
          },
        },
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
              const item = props.items[ctx.dataIndex]
              return ` ${ctx.label}: ${item.count.toLocaleString()} (${(item.share * 100).toFixed(1)}%)`
            },
          },
        },
      },
    }
  })
</script>

<template>
  <div class="pie-chart-wrap">
    <Doughnut :key="chartKey" :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
  .pie-chart-wrap {
    position: relative;
    min-height: 18rem;
  }
</style>
