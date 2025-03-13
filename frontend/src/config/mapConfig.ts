import { baseUrlOptions, type MapLayerConfig } from '@/config/layerTypes'
import { sp0MigrationLayers } from '@/config/sp0_migration'
import { sp2MobilityLayers } from '@/config/sp2_mobility'
import { sp3NatureLayers } from '@/config/sp3_nature'
import { sp4WasteLayers } from '@/config/sp4_waste'
import { sp6MaterialsLayers } from '@/config/sp6_materials'

export const mapConfig = {
  baseUrl: baseUrlOptions,
  layers: [
    ...sp0MigrationLayers,
    ...sp2MobilityLayers,
    ...sp3NatureLayers,
    ...sp4WasteLayers,
    ...sp6MaterialsLayers
  ] as MapLayerConfig[]
}

export const layerGroups = [
  {
    id: 'sp0_migration',
    label: 'SP0 Migration',
    expanded: false,
    layers: sp0MigrationLayers
  },
  {
    id: 'sp2_mobility',
    label: 'SP2 Mobility',
    expanded: false,
    layers: sp2MobilityLayers
  },
  {
    id: 'sp3_nature',
    label: 'SP3 Nature',
    expanded: false,
    layers: sp3NatureLayers
  },
  { id: 'sp4_waste', label: 'SP4 Waste', expanded: false, layers: sp4WasteLayers },
  { id: 'sp6_materials', label: 'SP6 Materials', expanded: false, layers: sp6MaterialsLayers }
  // Add other groups as needed
]
