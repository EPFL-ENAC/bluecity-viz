/**
 * Where MapLibre finds its worker.
 *
 * MapLibre 6 splits into two entries, the main one and
 * `maplibre-gl-worker.mjs`, and it builds the worker url at runtime from
 * `import.meta.url`. The bundler never sees that url, so the worker file is
 * not emitted: in production the map asks for `/assets/maplibre-gl-worker.mjs`
 * and gets a 404, no tile is ever decoded and the map stays blank with nothing
 * in the console. Copying the file by hand would not work either, it imports a
 * 500 kB shared chunk that is not emitted either.
 *
 * `?worker&url` is the vite way: it bundles the worker as its own entry, with
 * the shared chunk inlined, gives it a hashed name under /assets and returns
 * that url. `setWorkerUrl` puts it in the MapLibre config, which is read when
 * the first worker is started.
 *
 * Import this module for its side effect before creating a Map. It sits in its
 * own file so the two components that build a map share it, and so the import
 * of `maplibre-gl` stays inside the lazy route chunk: importing it from
 * main.ts would pull the 1 MB maplibre bundle into the entry.
 */
import { setWorkerUrl } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)
