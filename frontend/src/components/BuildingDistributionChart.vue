<script setup lang="ts">
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { LegendComponent, TooltipComponent, TitleComponent } from 'echarts/components'
import { ref, onMounted, watch, computed } from 'vue'
import * as echarts from 'echarts/core'
import { useBuildingsStore } from '@/stores/buildings'

// Register necessary ECharts components
use([CanvasRenderer, PieChart, LegendComponent, TooltipComponent, TitleComponent])

// Use the buildings store
const buildingsStore = useBuildingsStore()

const chartContainer = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

// Get chart data from the store
const chartData = computed(() => buildingsStore.buildingDistribution)
const chartTitle = computed(() => `Buildings by ${buildingsStore.selectedBuildingAttribute}`)

onMounted(() => {
  if (chartContainer.value) {
    chart = echarts.init(chartContainer.value)
    renderChart()
  }
})

// Update the chart when the window resizes
window.addEventListener('resize', () => {
  chart?.resize()
})

// Watch for changes in the chart data or selected attribute
watch(
  [chartData, chartTitle],
  () => {
    console.log(chartData)
    renderChart()
  },
  { deep: true }
)

function renderChart() {
  if (!chart) return

  const option = {
    title: {
      text: chartTitle.value,
      left: 'center'
    },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      type: 'scroll',
      maxHeight: 150
    },
    series: [
      {
        name: buildingsStore.selectedBuildingAttribute,
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 12,
            fontWeight: 'bold'
          }
        },
        labelLine: {
          show: false
        },
        data: chartData.value
      }
    ]
  }

  chart.setOption(option)
}
</script>

<template>
  <div class="chart-container">
    <div ref="chartContainer" style="width: 100%; height: 100%"></div>
  </div>
</template>

<style scoped>
.chart-container {
  width: 100%;
  height: 100%;
  min-height: 250px;
}
</style>
