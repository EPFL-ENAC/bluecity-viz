import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useBuildingsStore = defineStore('buildings', () => {
  // Store the building feature data
  const renderedBuildingFeatures = ref<any[]>([])
  const selectedBuildingAttribute = ref<string>('Archetype')
  const showBuildingChart = ref<boolean>(false)

  // Computed property to generate the building distribution data
  const buildingDistribution = computed(() => {
    if (!renderedBuildingFeatures.value.length) {
      return []
    }

    // Count buildings by attribute
    const attributeKey = selectedBuildingAttribute.value
    const distribution: Record<string, number> = {}

    renderedBuildingFeatures.value.forEach((feature) => {
      const value = feature.properties?.[attributeKey] || 'Unknown'
      distribution[value] = (distribution[value] || 0) + 1
    })

    // Format data for the chart
    return Object.entries(distribution)
      .sort((a, b) => b[1] - a[1]) // Sort by count, descending
      .map(([name, count]) => ({
        name,
        value: count
      }))
  })

  // Function to update rendered building features
  function updateRenderedBuildings(features: any[]) {
    renderedBuildingFeatures.value = features
  }

  // Function to change the selected attribute
  function setSelectedAttribute(attribute: string) {
    selectedBuildingAttribute.value = attribute
  }

  // Function to toggle chart visibility
  function toggleBuildingChart() {
    showBuildingChart.value = !showBuildingChart.value
  }

  return {
    renderedBuildingFeatures,
    selectedBuildingAttribute,
    showBuildingChart,
    buildingDistribution,
    updateRenderedBuildings,
    setSelectedAttribute,
    toggleBuildingChart
  }
})
