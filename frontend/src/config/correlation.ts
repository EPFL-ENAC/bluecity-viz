import type { FilterSpecification } from 'maplibre-gl'
import { defineGroup, defineLayer } from '@/config/defineLayer'
import type {
  CustomSourceSpecification,
  MapLayerConfig,
  SequentialEncoding
} from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

// Local Pearson correlation, red is negative, blue is positive.
const LOCAL_CORR_ENCODING: SequentialEncoding = {
  kind: 'sequential',
  property: 'local_corr',
  domain: [-1, -0.66, -0.33, 0, 0.33, 0.66, 1],
  scheme: ['#d53e4f', '#fc8d59', '#fee08b', '#ffffbf', '#e6f598', '#99d594', '#3288bd']
}

// Similarity, dark blue is very different, yellow is very similar.
const SIMILARITY_ENCODING: SequentialEncoding = {
  kind: 'sequential',
  property: 'similarity',
  domain: [0, 0.2, 0.4, 0.5, 0.6, 0.8, 1],
  scheme: ['#002051', '#1f3e6e', '#575c6e', '#7f7c75', '#a49d78', '#d5c164', '#fdea45']
}

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

/** The two measures every correlation file holds, one layer each. */
type Measure = 'localcorr' | 'similarity'

const MEASURES = {
  localcorr: {
    title: 'Local Correlation',
    unit: 'correlation (-1 to 1)',
    encoding: LOCAL_CORR_ENCODING,
    info: (left: string, right: string) =>
      `Local Pearson correlation between ${left} and ${right}. Blue = negative correlation, Red = positive correlation.`
  },
  similarity: {
    title: 'Similarity',
    unit: 'similarity (0-1)',
    encoding: SIMILARITY_ENCODING,
    info: (left: string, right: string) =>
      `Similarity between ${left} and ${right}. Blue = different, Red = similar.`
  }
} as const

/** All correlation layers share the same fill, only the filter changes. */
function correlationLayer(options: {
  id: string
  measure: Measure
  source: CustomSourceSpecification
  sourceLayer: string
  /** Names in the label, "Population & Waste (Similarity)". */
  left: string
  right: string
  /** Names in the sentence, "between population density and ...". */
  leftPhrase: string
  rightPhrase: string
  /** Layers of a whole file filter on the measure only. */
  attribute?: string
}): MapLayerConfig {
  const measure = MEASURES[options.measure]
  const measureFilter: FilterSpecification = ['==', ['get', 'measure_type'], options.measure]

  return defineLayer({
    id: options.id,
    label: `${options.left} & ${options.right} (${measure.title})`,
    unit: measure.unit,
    info: measure.info(options.leftPhrase, options.rightPhrase),
    source: options.source,
    encoding: measure.encoding,
    layer: {
      type: 'fill',
      'source-layer': options.sourceLayer,
      filter: options.attribute
        ? ['all', measureFilter, ['==', ['get', 'access_attr'], options.attribute]]
        : measureFilter,
      paint: {
        'fill-opacity': 0.8,
        'fill-outline-color': 'rgba(0,0,0,0.1)'
      }
    }
  })
}

/** One layer per accessibility attribute, for one measure. */
function accessCorrelationLayers(options: {
  prefix: string
  measure: Measure
  source: CustomSourceSpecification
  sourceLayer: string
  left: string
  leftPhrase: string
}): MapLayerConfig[] {
  return accessAttributes.map((attribute, index) =>
    correlationLayer({
      id: `${options.prefix}_${options.measure}_${index}`,
      measure: options.measure,
      source: options.source,
      sourceLayer: options.sourceLayer,
      left: options.left,
      right: accessLabels[index],
      leftPhrase: options.leftPhrase,
      rightPhrase: accessLabels[index].toLowerCase(),
      attribute
    })
  )
}

export const wastePopCorrelationGroup = defineGroup({
  id: 'correlation_waste_pop',
  label: 'Population & Waste Correlation',
  multiple: false,
  layers: (['localcorr', 'similarity'] as Measure[]).map((measure) =>
    correlationLayer({
      id: `waste_pop_${measure}`,
      measure,
      source: wastePopCorrelationSource,
      sourceLayer: 'corr_waste_pop',
      left: 'Population',
      right: 'Waste',
      leftPhrase: 'population density',
      rightPhrase: 'waste collection routes'
    })
  )
})

export const popAccessCorrelationGroup = defineGroup({
  id: 'correlation_pop_access',
  label: 'Population & Accessibility Correlation',
  multiple: false,
  layers: [
    ...accessCorrelationLayers({
      prefix: 'pop_access',
      measure: 'localcorr',
      source: popAccessCorrelationSource,
      sourceLayer: 'corr_pop_access',
      left: 'Population',
      leftPhrase: 'population density'
    }),
    ...accessCorrelationLayers({
      prefix: 'pop_access',
      measure: 'similarity',
      source: popAccessCorrelationSource,
      sourceLayer: 'corr_pop_access',
      left: 'Population',
      leftPhrase: 'population density'
    })
  ]
})

export const wasteAccessCorrelationGroup = defineGroup({
  id: 'correlation_waste_access',
  label: 'Waste & Accessibility Correlation',
  multiple: false,
  layers: [
    ...accessCorrelationLayers({
      prefix: 'waste_access',
      measure: 'localcorr',
      source: wasteAccessCorrelationSource,
      sourceLayer: 'corr_waste_access',
      left: 'Waste',
      leftPhrase: 'waste collection density'
    }),
    ...accessCorrelationLayers({
      prefix: 'waste_access',
      measure: 'similarity',
      source: wasteAccessCorrelationSource,
      sourceLayer: 'corr_waste_access',
      left: 'Waste',
      leftPhrase: 'waste collection density'
    })
  ]
})

export const correlationLayerGroups = [
  wastePopCorrelationGroup,
  popAccessCorrelationGroup,
  wasteAccessCorrelationGroup
]

export const wastePopCorrelationLayers = wastePopCorrelationGroup.layers
export const popAccessCorrelationLayers = popAccessCorrelationGroup.layers
export const wasteAccessCorrelationLayers = wasteAccessCorrelationGroup.layers

export const allCorrelationLayers: MapLayerConfig[] = [
  ...wastePopCorrelationLayers,
  ...popAccessCorrelationLayers,
  ...wasteAccessCorrelationLayers
]
