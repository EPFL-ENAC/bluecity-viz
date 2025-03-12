import { baseUrlOptions, type MapLayerConfig } from '@/config/layerTypes'
import { sp0MigrationLayers } from './sp0_migration'
// Uncomment when you create these files
// import { sp2ExampleLayers } from './sp2_example'
// import { sp3ExampleLayers } from './sp3_example'

export const mapConfig = {
  // Map layers with their associated sources
  baseUrl: baseUrlOptions,
  layers: [
    // Include SP0 migration layers
    ...sp0MigrationLayers

    // Uncomment when you create these files
    // Include SP2 example layers
    // ...sp2ExampleLayers,

    // Include SP3 example layers
    // ...sp3ExampleLayers

    // Add any other standalone layers here
  ] as MapLayerConfig[]
}
