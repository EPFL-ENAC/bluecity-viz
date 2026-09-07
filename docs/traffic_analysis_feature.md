# Traffic analysis

The traffic tool answers one question: what happens to the road network when
you close a street or drop its speed limit. It re-routes a fixed set of
origin-destination pairs on the modified graph and compares the result with
the untouched one.

## 1. Open the tool

Sidebar, "Analytics tools" section, click **Traffic analysis**. The row is
marked `active` while the tool is open and the dock opens on the right of the
map.

Opening it loads the graph edges as a grey base layer and the pre-generated
OD pairs. The backend samples 500 pairs at startup, weighted by betweenness
centrality with a lognormal distance distribution, so the same pairs are used
for every scenario and two runs stay comparable.

## 2. Modify edges

Click an edge on the map. Each click cycles through the four actions and back
to none:

```
none → remove → 50 km/h → 30 km/h → 10 km/h → none
```

Modified edges are listed in the dock under **Modified edges**, each with a
badge (`×` for a removal, otherwise the speed limit) and an arrow showing
whether the edge is one-way (`→`) or both ways (`↔`). Remove one with the `×`
button on its row, or clear the list with **Clear**.

The cycle order lives in `MODIFICATION_CYCLE` in
`frontend/src/stores/trafficAnalysis.ts`.

## 3. Choose the routing model

Two options above the calculate button.

**Iterative model (BPR congestion)**, off by default. When it is off, the
betweenness centrality is computed once on the modified graph to derive
congested travel times (`duration_bc`), then the affected routes are re-run
with those weights. Roads that structurally attract flow look slower, which
spreads the traffic without any iteration.

When it is on, the simulated route volumes are counted, normalised to daily
vehicle-km and fed into the BPR speed reduction formula. The routes are re-run
with the new weights, for the number of iterations you pick with the slider
(1 to 5, count about 10 seconds each). More iterations converge toward a
Wardrop user equilibrium.

**Elastic demand**, off by default. When it is on, trip destinations are
resampled, because travellers adapt to the new travel times. Closing a major
road then shifts trips to closer destinations instead of inflating the total
travel time. Origins never change, only the destination choice.

## 4. Calculate

**Calculate routes** posts the modification list to
`POST /api/v1/routes/recalculate`. The backend applies the modifications,
re-routes every OD pair with igraph Dijkstra, computes CO₂ and betweenness
centrality, then restores the graph. The response carries per-edge usage
statistics, which the store turns into the D3 colour scales.

A first run with no modification gives you the baseline.

## 5. Read the map

The **Visualisation** section lists the modes available for the current
result. A mode only appears when the data supports it, so a run without
modifications only offers the first two.

| Mode | Shows | Scale |
|---|---|---|
| Edge usage frequency | How much each edge is used | Viridis |
| CO₂ emissions | Grams of CO₂ per edge | Viridis |
| Traffic change (Δ) | Vehicle count difference | RdBu, diverging |
| Traffic change (Δ, relative %) | The same, as a percentage | RdBu, diverging |
| CO₂ emissions change | Gram difference | RdBu, diverging |
| Betweenness centrality | Structural importance of the edge | Viridis |
| Betweenness change | Difference in centrality | RdBu, diverging |

The legend follows the selected mode. All modes read the same response, so
switching between them costs nothing and the scales are kept.

**Clip to bus routes** restricts the display to edges carrying a bus line,
which is the useful view when the question is about public transport.

## 6. Impact statistics

Once a scenario has run, the impact panel appears under the visualisation
list. It compares the modified network with the baseline: how many routes
were affected and how many failed outright, the total extra distance, time
and CO₂, the average detour per affected route with the percentage increases,
and the worst single route.

With elastic demand on, the panel says so, because the numbers then mix a
routing effect with a demand effect and are not comparable with a fixed
demand run.

## Where the code is

| Part | File |
|---|---|
| State, scales, cycle order | `frontend/src/stores/trafficAnalysis.ts` |
| Dock UI | `frontend/src/components/dock/TrafficDock.vue` |
| Map layers | `frontend/src/composables/useDeckGLTrafficAnalysis.ts` |
| HTTP client | `frontend/src/services/trafficAnalysis.ts` |
| Routing, CO₂, BPR | `backend/app/services/` |
