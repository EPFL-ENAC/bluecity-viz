import { biodiversityGroup } from '@/config/biodiversity'
import { correlationLayerGroups } from '@/config/correlation'
import {
  baseUrlOptions,
  type CustomSourceSpecification,
  type LayerGroup,
  type MapLayerConfig
} from '@/config/layerTypes'
import { sp0MigrationGroup } from '@/config/sp0_migration'
import { sp2MobilityGroup } from '@/config/sp2_mobility'
import { sp3NatureGroup } from '@/config/sp3_nature'
import { sp4WasteGroup } from '@/config/sp4_waste'
import { sp6MaterialsGroup } from '@/config/sp6_materials'
import { sp7VehicleGroup } from '@/config/sp7'

/**
 * The whole registry, in one place. The order is the order the layers are
 * drawn in and the order of the datasets panel, so it is not free to change.
 * To add a dataset, add its group here.
 */
const datasets: LayerGroup[] = [
  sp2MobilityGroup,
  sp3NatureGroup,
  sp4WasteGroup,
  sp6MaterialsGroup,
  sp7VehicleGroup,
  ...correlationLayerGroups,
  sp0MigrationGroup,
  biodiversityGroup
]

const layers: MapLayerConfig[] = datasets.flatMap((group) => group.layers)

/** Several layers can read the same file, the source is listed once. */
function uniqueSources(entries: MapLayerConfig[]): CustomSourceSpecification[] {
  const seen = new Set<string>()
  return entries
    .map((entry) => entry.source)
    .filter((source) => {
      if (seen.has(source.id)) return false
      seen.add(source.id)
      return true
    })
}

export const mapConfig = {
  baseUrl: baseUrlOptions,
  layers,
  sources: uniqueSources(layers)
}

export const layerGroups = datasets
