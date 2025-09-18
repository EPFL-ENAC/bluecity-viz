import type { CustomSourceSpecification, MapLayerConfig } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'
import type {
  ColorSpecification,
  DataDrivenPropertyValueSpecification,
  LayerSpecification
} from 'maplibre-gl'

const localCorrColorScale: DataDrivenPropertyValueSpecification<ColorSpecification> = [
  'interpolate',
  ['linear'],
  ['to-number', ['get', 'local_corr']],
  -1,
  '#d53e4f', // Strong negative correlation (dark red)
  -0.66,
  '#fc8d59', // Medium negative correlation (orange-red)
  -0.33,
  '#fee08b', // Slight negative correlation (yellow-orange)
  0,
  '#ffffbf', // No correlation (light yellow)
  0.33,
  '#e6f598', // Slight positive correlation (light green)
  0.66,
  '#99d594', // Medium positive correlation (medium green)
  1,
  '#3288bd' // Strong positive correlation (dark blue)
]

const similarityColorScale: DataDrivenPropertyValueSpecification<ColorSpecification> = [
  'interpolate',
  ['linear'],
  ['to-number', ['get', 'similarity']],
  0,
  '#002051', // Very dissimilar (dark blue)
  0.2,
  '#1f3e6e', // Strongly dissimilar (medium blue)
  0.4,
  '#575c6e', // Moderately dissimilar (blue-gray)
  0.5,
  '#7f7c75', // Neutral similarity (gray)
  0.6,
  '#a49d78', // Moderately similar (tan)
  0.8,
  '#d5c164', // Strongly similar (gold)
  1,
  '#fdea45' // Very similar (bright yellow)
]

// Accessibility attributes used in filenames and for filtering
const accessAttributes = [
  'access_nearest_k_time_return_walk_poi_shop_short',
  'access_nearest_k_time_return_walk_poi_recreation_indoors',
  'access_nearest_time_return_bike_e25_poi_education_school',
  'access_nearest_time_return_drive_peak_poi_education_school',
  'ar_schools_ebike_bike',
  'ar_schools_ebike_car',
  'access_gravity_time_return_bike_e25_employment_total',
  'access_gravity_time_return_transit_employment_total',
  'access_gravity_time_return_drive_peak_employment_total',
  'ar_jobs_transit_car'
]

// Human-readable labels for accessibility attributes
const accessLabels = [
  'Walking access to shops',
  'Walking access to recreation',
  'E-bike access to schools',
  'Car access to schools',
  'School access ratio (E-bike vs Bike)',
  'School access ratio (E-bike vs Car)',
  'E-bike access to jobs',
  'Transit access to jobs',
  'Car access to jobs',
  'Job access ratio (Transit vs Car)'
]

// Shared source configurations for correlation data
const wastePopCorrelationSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'corr_waste_pop',
  label: 'Population & Waste Correlation Data',
  url: `pmtiles://${baseUrl}/lausanne_corr_waste_pop.pmtiles`
}

const popAccessCorrelationSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'corr_pop_access',
  label: 'Population & Accessibility Correlation Data',
  url: `pmtiles://${baseUrl}/lausanne_corr_pop_access.pmtiles`
}

const wasteAccessCorrelationSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'corr_waste_access',
  label: 'Waste & Accessibility Correlation Data',
  url: `pmtiles://${baseUrl}/lausanne_corr_waste_access.pmtiles`
}

export const correlationSources: CustomSourceSpecification[] = [
  wastePopCorrelationSource,
  popAccessCorrelationSource,
  wasteAccessCorrelationSource
]

// Generate correlation layers - Population & Waste
export const wastePopCorrelationLayers: MapLayerConfig[] = [
  // Local Correlation (Pearson)
  {
    id: 'waste_pop_localcorr',
    label: 'Population & Waste (Local Correlation)',
    unit: 'correlation (-1 to 1)',
    info: 'Local Pearson correlation between population density and waste collection routes. Blue = negative correlation, Red = positive correlation.',
    source: wastePopCorrelationSource,
    layer: {
      id: 'waste_pop_localcorr-layer',
      type: 'fill',
      source: 'waste_pop_localcorr',
      'source-layer': 'corr_waste_pop',
      filter: ['==', ['get', 'measure_type'], 'localcorr'],
      paint: {
        'fill-color': localCorrColorScale,
        'fill-opacity': 0.8,
        'fill-outline-color': 'rgba(0,0,0,0.1)'
      }
    } as LayerSpecification
  },
  // Similarity
  {
    id: 'waste_pop_similarity',
    label: 'Population & Waste (Similarity)',
    unit: 'similarity (0-1)',
    info: 'Similarity between population density and waste collection routes. Blue = different, Red = similar.',
    source: wastePopCorrelationSource,
    layer: {
      id: 'waste_pop_similarity-layer',
      type: 'fill',
      source: 'waste_pop_similarity',
      'source-layer': 'corr_waste_pop',
      filter: ['==', ['get', 'measure_type'], 'similarity'],
      paint: {
        'fill-color': similarityColorScale,
        'fill-opacity': 0.8,
        'fill-outline-color': 'rgba(0,0,0,0.1)'
      }
    } as LayerSpecification
  }
]

// Generate Population-Access correlation layers
export const popAccessCorrelationLayers: MapLayerConfig[] = [
  // Local Correlation layers
  ...accessAttributes.map((attr, index) => ({
    id: `pop_access_localcorr_${index}`,
    label: `Population & ${accessLabels[index]} (Local Correlation)`,
    unit: 'correlation (-1 to 1)',
    info: `Local Pearson correlation between population density and ${accessLabels[
      index
    ].toLowerCase()}. Blue = negative correlation, Red = positive correlation.`,
    source: popAccessCorrelationSource,
    layer: {
      id: `pop_access_localcorr_${index}-layer`,
      type: 'fill',
      source: `pop_access_localcorr_${index}`,
      'source-layer': 'corr_pop_access',
      filter: [
        'all',
        ['==', ['get', 'measure_type'], 'localcorr'],
        ['==', ['get', 'access_attr'], attr]
      ],
      paint: {
        'fill-color': localCorrColorScale,
        'fill-opacity': 0.8,
        'fill-outline-color': 'rgba(0,0,0,0.1)'
      }
    } as LayerSpecification
  })),
  // Similarity layers
  ...accessAttributes.map((attr, index) => ({
    id: `pop_access_similarity_${index}`,
    label: `Population & ${accessLabels[index]} (Similarity)`,
    unit: 'similarity (0-1)',
    info: `Similarity between population density and ${accessLabels[
      index
    ].toLowerCase()}. Blue = different, Red = similar.`,
    source: popAccessCorrelationSource,
    layer: {
      id: `pop_access_similarity_${index}-layer`,
      type: 'fill',
      source: `pop_access_similarity_${index}`,
      'source-layer': 'corr_pop_access',
      filter: [
        'all',
        ['==', ['get', 'measure_type'], 'similarity'],
        ['==', ['get', 'access_attr'], attr]
      ],
      paint: {
        'fill-color': similarityColorScale,
        'fill-opacity': 0.8,
        'fill-outline-color': 'rgba(0,0,0,0.1)'
      }
    } as LayerSpecification
  }))
]

// Generate Waste-Access correlation layers
export const wasteAccessCorrelationLayers: MapLayerConfig[] = [
  // Local Correlation layers
  ...accessAttributes.map((attr, index) => ({
    id: `waste_access_localcorr_${index}`,
    label: `Waste & ${accessLabels[index]} (Local Correlation)`,
    unit: 'correlation (-1 to 1)',
    info: `Local Pearson correlation between waste collection density and ${accessLabels[
      index
    ].toLowerCase()}. Blue = negative correlation, Red = positive correlation.`,
    source: wasteAccessCorrelationSource,
    layer: {
      id: `waste_access_localcorr_${index}-layer`,
      type: 'fill',
      source: `waste_access_localcorr_${index}`,
      'source-layer': 'corr_waste_access',
      filter: [
        'all',
        ['==', ['get', 'measure_type'], 'localcorr'],
        ['==', ['get', 'access_attr'], attr]
      ],
      paint: {
        'fill-color': localCorrColorScale,
        'fill-opacity': 0.8,
        'fill-outline-color': 'rgba(0,0,0,0.1)'
      }
    } as LayerSpecification
  })),
  // Similarity layers
  ...accessAttributes.map((attr, index) => ({
    id: `waste_access_similarity_${index}`,
    label: `Waste & ${accessLabels[index]} (Similarity)`,
    unit: 'similarity (0-1)',
    info: `Similarity between waste collection density and ${accessLabels[
      index
    ].toLowerCase()}. Blue = different, Red = similar.`,
    source: wasteAccessCorrelationSource,
    layer: {
      id: `waste_access_similarity_${index}-layer`,
      type: 'fill',
      source: `waste_access_similarity_${index}`,
      'source-layer': 'corr_waste_access',
      filter: [
        'all',
        ['==', ['get', 'measure_type'], 'similarity'],
        ['==', ['get', 'access_attr'], attr]
      ],
      paint: {
        'fill-color': similarityColorScale,
        'fill-opacity': 0.8,
        'fill-outline-color': 'rgba(0,0,0,0.1)'
      }
    } as LayerSpecification
  }))
]

// Combine all correlation layers
export const allCorrelationLayers: MapLayerConfig[] = [
  ...wastePopCorrelationLayers,
  ...popAccessCorrelationLayers,
  ...wasteAccessCorrelationLayers
]

// Export layer groups for mapConfig.ts
export const correlationLayerGroups = [
  {
    id: 'correlation_waste_pop',
    label: 'Population & Waste Correlation',
    expanded: false,
    multiple: false,
    layers: wastePopCorrelationLayers
  },
  {
    id: 'correlation_pop_access',
    label: 'Population & Accessibility Correlation',
    expanded: false,
    multiple: false,
    layers: popAccessCorrelationLayers
  },
  {
    id: 'correlation_waste_access',
    label: 'Waste & Accessibility Correlation',
    expanded: false,
    multiple: false,
    layers: wasteAccessCorrelationLayers
  }
]
