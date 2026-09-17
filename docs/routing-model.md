# The routing model

What the traffic tool computes, and what it does not.

The tool answers one question: **what happens to the road network when you
close a street or change its speed limit?** It cannot observe that, so it
simulates it. A fixed set of car trips is routed twice, once on the real
network and once on the one you modified, and every number on the map is the
difference between the two runs.

That design decides what the results mean. They are a *comparison between two
versions of the same model*, not a prediction of traffic. "This street carries
40 % more traffic" is a statement about the model; "this street will carry
4,000 more cars tomorrow" is not one the tool can make.

Everything below lives in `backend/app/services/`.

---

## 1. The network

`graph_mirror.py` turns the OpenStreetMap road graph into the form the model
works on: an igraph topology for shortest paths, plus one numpy array per
quantity, indexed by directed edge.

Every edge carries:

| | |
|---|---|
| `length` | metres |
| `speed_kph` | free-flow speed: the OSM speed limit; failing that, what the recorded travel time implies; failing that, 30 km/h |
| `travel_time` | free-flow seconds, always `length / (speed_kph / 3.6)` |
| `lanes` | lane count, 2 when untagged |
| `elev_gain` | metres of climb, 0 going down or flat |

Speed and time are derived together, so the three of them are one consistent
triple: a route that sums `travel_time` and an emission model that reads
`speed_kph` describe the same drive. (Until recently they did not: an
untagged street was driven at 30 km/h by the router and 40 km/h by the CO₂
model.)

**Streets and edges.** A two-way street is two directed edges. OSM also splits
one street into several parallel edges between the same two junctions. The
model computes on directed edges and groups them back into (u, v) *streets*
for the API and the map, because a street is what a user clicks. Everything
the API returns is per street, both directions summed by the frontend.

**A scenario never changes the network.** Closing a street means writing `+inf`
into *this request's copy* of the travel-time array, which igraph reads as
"never use this edge" (`modifications.py`). Nothing is written back, so
concurrent requests cannot see each other and there is nothing to roll back.

---

## 2. The demand: which trips

The tool has no traffic counts, so it invents a plausible population of trips
and reuses it for every scenario. Two scenarios are comparable because they
move **the same trips** over a different network.

`sampling/` draws them, once at startup, in five steps.

**Step 1 — the junctions.** Nodes with three streets or more, which excludes
dead ends and the nodes OSM leaves in the middle of a street. Capped at
`n_nodes_preprocess` (1,000) because step 4 is quadratic. The cap is drawn
uniformly, whatever the weighting: the pool only decides which junctions are
*considered*, the weight is applied once later.

Each junction carries a weight, how likely a trip is to start or end there:

- **uniform** — every junction alike.
- **population** — `100 · (rank(residents) + rank(jobs)) / 2`, so a junction
  at the 75th percentile of residents and the 85th of jobs scores 80. The
  ranks are over this area only: the score says "busy for this town", not
  "busy for Switzerland". A junction with nobody scores 1 rather than 0, so
  the edge of a village stays possible but rare.

**Step 2 — betweenness.** How much traffic the *shape* of the network puts on
each street (section 5), in veh/day.

**Step 3 — the network under load.** Those flows are pushed through the
congestion formula (section 4) to get travel times that already include
congestion. This matters: people do not choose destinations as if the city
were empty.

**Step 4 — the travel-time matrix.** Shortest time from every pool junction to
every other, on those congested times.

**Step 5 — the draw.**

```
origin      ~ w(o)
destination ~ w(d) · lognorm.pdf(t_od ; sigma, exp(mu))
```

Origins are drawn **with replacement**, so a heavy junction gets more trips;
drawn twice, it gets twice as many destinations. Each origin then draws
`n_destinations_per_origin` (200) destinations, weighted both by how
attractive the destination is and by how plausible a trip of that length is.

The trip-length term is a lognormal over travel time, fitted to the Swiss
Mobility and Transport Microcensus. With `mu = 6.85`, `sigma = 0.83`:

| | |
|---|---|
| most likely trip | 474 s, about **8 min** |
| median trip | 944 s, about 16 min |
| mean trip | 1,332 s, about 22 min |

The mean sits well past the peak because the tail is long. Relative weight by
trip length: 2 min 0.25, 5 min 0.86, **8 min 1.00**, 15 min 0.74, 30 min 0.27,
60 min 0.05. Very short trips are rare because people walk them, very long
ones because few people commute an hour by car within one city.

**Nested sizes.** The startup draw is `OD_PAIRS_MAX` (76,400) pairs. A request
asking for N gets the **first N**. The origin draws are in random order, so a
prefix is itself a fair sample, and a run at 20,000 pairs is a *subset* of the
one at 76,400 rather than a different experiment. The default is 20,000: per
street frequency correlates 0.96 with the full set and shares 85 of the top
100 streets, for a run about four times faster.

Each node weighting has its own sample and its own baseline. Switching
weighting changes the trips, so the numbers are not comparable across the two.

---

## 3. Routing

`routing_engine.py`. Every trip takes the fastest path by `travel_time`,
igraph Dijkstra, one search per origin serving all its destinations. A trip
whose destination became unreachable is *failed*, and counted apart.

Routes are stored as flat arrays of edge ids rather than objects: at 76,400
trips the objects cost more than the routing.

Per trip the model sums `length`, `travel_time`, `elev_gain` and CO₂ along the
path.

---

## 4. Congestion

`bpr.py`. Traffic slows a street down, in the speed form of the Bureau of
Public Roads curve:

```
speed(flow) = speed_free / (1 + flow / (lanes · k))
```

`k` is `betweenness_to_slowdown`, 50,000 veh/day per lane: the flow per lane
at which a street drops to **half** its free-flow speed. A one-lane street
halves at 50,000 veh/day, a two-lane one at 100,000.

In travel time this is exactly the standard BPR curve:

```
time(flow) = time_free · (1 + flow / (lanes · k))     i.e.  t = t0 · (1 + a·(v/c)^b)
```

with capacity `c = lanes · k`, `a = 1` and **`b = 1`**. Road engineering
normally uses `a = 0.15, b = 4`, a curve that stays flat until capacity and
then explodes. This one is **linear**: it nudges traffic away from busy
streets but never produces a real jam. It is a spreading mechanism, not a
congestion forecast.

**Flow** is in veh/day, and comes from one of two places (section 7). Either
way it is normalised the same way, which is what makes the two
interchangeable inside the formula:

```
flow = counts · daily_km_driven · 1000 / sum(counts · length)
```

so that the network's total vehicle-kilometres equal `daily_km_driven`
(1,250,000 for Lausanne: roughly 250,000 people × 0.5 cars × 10 km/day). An
OD sample of a few tens of thousands of trips is not a day of traffic, so this
rescales it to one. A custom area smaller than Lausanne gets a proportionally
smaller `daily_km_driven`, scaled by road length (`area_builder._scaled_config`).

---

## 5. Betweenness centrality

`betweenness.py`. How much traffic the structure of the network would put on a
street if everybody drove between every pair of junctions. It looks only at
the network, never at the trips, which is why it is computed once per graph
and shared by every OD sample.

```
bc_raw[e] = shortest paths through e, over all (source, target) in the pool
bc[e]     = bc_raw[e] · daily_km_driven · 1000 / sum(bc_raw · length)
```

The pool is the same junction pool the demand uses (section 2), so the map and
the sampler talk about the same network. The normalisation is the same as for
flows, which is what lets betweenness be fed into the BPR formula as a flow:
it is a structural *estimate* of the load, in veh/day.

Computed in chunks of 50 source junctions, with the targets always the whole
pool. Betweenness sums over (source, target) pairs, so chunking sources and
adding gives exactly the same result; the chunking exists only because
python-igraph holds the GIL for the whole call and a single 500 ms call would
freeze every other request.

---

## 6. CO₂

`co2_calculator.py`. A distance-based COPERT-style model for a typical
European petrol car of about 1,500 kg. No engine, no gearbox, no driver: it
says what a fleet average emits at a steady speed on a given slope, which is
the right grain for comparing two versions of a network.

```
co2_per_km(v) = 2400/v + 120 + 0.004·v²
                ───────   ───   ────────
                idling    roll  air drag
```

U-shaped, because a car wastes fuel both crawling and racing:

| speed | g CO₂/km | |
|---|---|---|
| 20 km/h | 241.6 | congested |
| 30 km/h | 203.6 | city, slow |
| 50 km/h | 178.0 | urban |
| **67 km/h** | **173.8** | the minimum |
| 100 km/h | 184.0 | rural |
| 130 km/h | 206.1 | motorway |

Slope adds proportionally to the gradient:

```
co2_uphill = co2_flat · (1 + grade · 5)        grade = elev_gain / length
```

5 % → +25 %, 10 % → +50 %, 20 % → +100 %. A 500 m street at 50 km/h emits
89 g flat and 134 g at a 10 % climb. **Going down costs the same as flat,
never less**: an engine braking downhill still burns fuel, and a discount
would make a route through the hills look cheaper than it is.

**What `co2_g_per_km` on a street means.** It is *not* the emission rate of
one car. It is the CO₂ of all the traffic the model puts on that street, per
kilometre of street:

```
co2_g_per_km = (grams one car emits over the street) · (trips using it) / km
```

So a quiet street and a busy one with the same speed limit have very different
values. Multiplied by the street's length and summed over the network, it
gives back the total CO₂ of all the trips, which is what
`tests/test_edge_co2_totals.py` checks.

---

## 7. The three scenario models

`recalculate.py`. All three route the same trips on the modified network; they
differ in what the traveller is allowed to change.

### Targeted reroute (the default)

Only the trips that used a modified street pick a new route. Everybody else
keeps theirs, which is exact: their path does not touch anything that changed.

Those trips choose on **congested** travel times, from the betweenness of the
modified network. Without that, every displaced trip would pile onto the one
next-fastest street.

Cheap, because closing a street usually touches a minority of trips.

### Equilibrium (BPR iterations, "Iterative model")

Every trip is re-routed, repeatedly. Congestion moves load across the whole
network, so no trip can be assumed unaffected: a street far from the closure
gets slower because the traffic that left the closure arrived on it.

Pass 1 is free flow: everybody takes the fastest empty-city route, which
overloads the same few streets. Each further pass re-routes on the travel
times the volumes so far imply, moving toward the state where no driver can do
better by switching route (a **Wardrop user equilibrium**). Volumes are
averaged between passes (method of successive averages,
`x_k = x_{k-1} + (y_k - x_{k-1})/k`) so the assignment does not oscillate
between two extremes; two iterations already converge reasonably.

### Elastic demand

Trips keep their origin but draw a **new destination**, with the same rule as
the initial sample, on the modified network's travel times.

Fixed demand assumes a traveller drives to the same place whatever it costs.
Elastic demand lets the destination move, so closing a road shows up as trips
getting shorter rather than as an implausible total travel time.

Because the destinations changed, trip *i* of the new run is not trip *i* of
the old one. No per-trip comparison is meaningful, and the impact panel shows
totals only.

---

## 8. Reading the result

Per street, from `usage_rows.py`:

| field | meaning |
|---|---|
| `count` | trips using the street |
| `frequency` | `count / trips routed` |
| `delta_count`, `delta_frequency` | new minus baseline |
| `co2_g_per_km` | CO₂ of that traffic per km (section 6) |
| `delta_co2_g_per_km` | new minus baseline |
| `betweenness_centrality` | veh/day, structural (section 5) |
| `delta_betweenness` | how the closure changed the structure |

A street used before and not after still gets a row, with a count of 0, or the
deltas would not add up to the real change.

And over the trips, from `impact.py`:

- **affected** — the trip's route changed, *in either direction*. Raising a
  speed limit affects trips just as closing a street does.
- **failed** — the trip had a route and has none now. A failure has no finite
  cost, so it is never added to the totals: it is reported on its own, and one
  failed trip is worse news than any amount of detour.
- **changes** — `new − old` over the affected trips, **signed**. A scenario
  that shortens trips reads negative.
- **max** — the worst single trip, 0 when nothing got worse.

---

## 9. What this model does not do

Read the results with these in mind.

**It is a comparison, not a forecast.** The absolute numbers depend on
`daily_km_driven` and on the synthetic demand. The *differences* between two
scenarios are what the tool is for.

**Congestion is linear.** `b = 1` instead of the usual 4. Traffic is nudged
away from busy streets; it never jams, and the model will understate what
happens when a closure pushes a street past its real capacity.

**The default mode scores routes on free-flow time.** A targeted reroute
*chooses* the new path on congested times but *reports* its duration in
free-flow time. The reported detour is therefore the free-flow cost of a
congestion-aware path, which is slightly pessimistic compared with the fastest
free-flow alternative. Use the equilibrium mode when the travel-time numbers
themselves matter.

**The equilibrium mode reports its last assignment.** The iteration averages
volumes, but the map shows the last pass's routes, one plausible assignment
close to the averaged equilibrium rather than the average itself.

**Elastic demand ignores congestion when redrawing.** Destinations are drawn
on free-flow times of the modified network.

**Only cars.** No buses, bikes, pedestrians or trains; no time of day, no peak
hour; no traffic lights, no junction delay, no turn restrictions beyond what
the OSM graph encodes.

**A street is modified in both its parallel edges at once.** The API names a
street by `(u, v)`; when OSM splits it, all of its edges get the change.

**The demand is synthetic.** It is drawn from a plausible distribution, not
measured. Two OD samples of the same city differ: on Lausanne at 20,000 pairs,
two seeds correlate about 0.87 on per-street frequency and share 67 of their
top 100 streets. That is the noise floor of any single run, and it is worth
remembering before reading much into a small change on one street.

---

## Where the code is

| | |
|---|---|
| The network | `services/graph_mirror.py` |
| A scenario | `services/modifications.py` |
| The demand | `services/sampling/` (`node_pool.py`, `od_sampler.py`, `config.py`) |
| Routing | `services/routing_engine.py` |
| Congestion | `services/bpr.py` |
| Betweenness | `services/betweenness.py` |
| CO₂ | `services/co2_calculator.py` |
| One scenario run | `services/recalculate.py` |
| The comparison | `services/impact.py` |
| The result rows | `services/usage_rows.py` |
| An area and its caches | `services/area_graph.py` |

The settings that change the numbers are in `backend/app/config.py`
(`OD_PAIRS`, `OD_PAIRS_MAX`) and
`backend/app/services/sampling/config.py` (everything else).
