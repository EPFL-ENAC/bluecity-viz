import { allCorrelationLayers, correlationLayerGroups } from '@/config/correlation'
import { baseUrlOptions, type MapLayerConfig } from '@/config/layerTypes'
import { sp0MigrationLayers } from '@/config/sp0_migration'
import { sp2MobilityLayers } from '@/config/sp2_mobility'
import { sp3NatureLayers } from '@/config/sp3_nature'
import { sp4WasteLayers } from '@/config/sp4_waste'
import { sp6MaterialsLayers } from '@/config/sp6_materials'
import { sp7VehicleLayers } from '@/config/sp7'

export const mapConfig = {
  baseUrl: baseUrlOptions,
  layers: [
    ...sp2MobilityLayers,
    ...sp3NatureLayers,
    ...sp4WasteLayers,
    ...sp6MaterialsLayers,
    ...sp7VehicleLayers,
    ...allCorrelationLayers,
    ...sp0MigrationLayers
  ] as MapLayerConfig[]
}

export const layerGroups = [
  {
    id: 'sp0_migration',
    label: 'SP0 Migration',
    expanded: false,
    multiple: false,
    layers: sp0MigrationLayers
  },
  {
    id: 'sp2_mobility',
    label: 'SP2 Mobility',
    expanded: false,
    multiple: false,
    layers: sp2MobilityLayers
  },
  {
    id: 'sp3_nature',
    label: 'SP3 Nature',
    expanded: false,
    multiple: false,
    layers: sp3NatureLayers
  },
  { id: 'sp4_waste', label: 'SP4 Waste', expanded: false, multiple: true, layers: sp4WasteLayers },
  {
    id: 'sp6_materials',
    label: 'SP6 Materials',
    expanded: false,
    multiple: false,
    layers: sp6MaterialsLayers
  },
  { id: 'sp7', label: 'SP7 Goods', expanded: false, multiple: false, layers: sp7VehicleLayers },
  ...correlationLayerGroups
  // Add other groups as needed
]
