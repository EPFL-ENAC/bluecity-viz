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
`speed_kph` describe the same drive.

**Where the network comes from.** Every area is cut from one store of the
Swiss road graph (`backend/data/swiss_graph`), the default one too: a 6 km
circle around 6.633 / 46.52, built and pinned at startup (`default_area_*` in
`config.py`). The climb `elev_gain` comes from swissALTIRegio at 40 m. Before,
the default was the Lausanne GraphML: the city outline, 4,771 nodes, with
swissALTI3D at 2 m. So the numbers on the default area changed with it. The
GraphML is still loaded for the waste tool, it routes nothing here.

**Streets and edges.** A two-way street is two directed edges. OSM also splits
one street into several parallel edges between the same two junctions. The
model computes on directed edges and groups them back into (u, v) *streets*
for the API and the map, because a street is what a user clicks. Everything
the API returns is per street, both directions summed by the frontend.

**A scenario never changes the network.** Closing a street means writing `+inf`
into *this request's copy* of the travel-time array (`modifications.py`).
Nothing is written back, so concurrent requests cannot see each other and
there is nothing to roll back.

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

Each junction carries two weights: how likely a trip is to start there
(`w_o`) and how likely it is to end there (`w_d`). Apart from uniform, both
come from one score, with a share `a` for the residents:

```
score(a) = max(1, 100 · (a · rank(residents) + (1 − a) · rank(jobs)))
```

| weighting | API id | origin `w_o` | destination `w_d` |
|---|---|---|---|
| Uniform | `uniform` | 1 | 1 |
| Daily average | `population` | `score(0.5)` | `score(0.5)` |
| Weekday morning | `weekday_morning` | `score(1)`, residents | `score(0)`, jobs |
| Weekday evening | `weekday_evening` | `score(0)`, jobs | `score(1)`, residents |

- **Daily average** weighs both ends the same, so a junction at the 75th
  percentile of residents and the 85th of jobs scores 80 at both ends. Its id
  stays `population`, the name it had before the weekday ones.
- **Weekday morning** goes from home to work: trips start where people live
  and end where they work. **Weekday evening** is the way back. The daily
  average is the mean of the two ranks.

Residents are STATPOP, jobs are full-time equivalents from STATENT, both per
hectare and snapped to the nearest node. The ranks are over this area only:
the score says "busy for this town", not "busy for Switzerland". A count of 0
ranks 0. A junction that scores nothing still weighs 1 rather than 0, so the
edge of a village stays possible but rare; in the morning, a junction with no
resident can still be an origin, about 100 times less often than the busiest
one. The shares live in one table, `RESIDENT_SHARE` in `node_pool.py`.

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
origin      ~ w_o(o)
destination ~ w_d(d) · lognorm.pdf(t_od ; sigma, exp(mu))
```

Origins are drawn **with replacement**, so a heavy junction gets more trips;
drawn twice, it gets twice as many destinations. Each origin then draws
`n_destinations_per_origin` (200) destinations, weighted both by how
attractive the destination is (its destination weight) and by how plausible
a trip of that length is.

The trip-length term is a lognormal over travel time, fitted to the Swiss
Mobility and Transport Microcensus. With `mu = 6.85`, `sigma = 0.83`:

| | |
|---|---|
| most likely trip | 474 s, about **8 min** |
| median trip | 944 s, about 16 min |
| mean trip | 1,332 s, about 22 min |

The mean sits well past the peak because the tail is long: relative weight
0.25 at 2 min, 0.86 at 5, **1.00 at 8**, 0.74 at 15, 0.27 at 30, 0.05 at 60.
Very short trips are rare because people walk them, very long ones because few
people commute an hour by car within one city.

**Nested sizes.** The startup draw is `OD_PAIRS_MAX` (76,400) pairs. A request
asking for N gets the **first N**. The origin draws are in random order, so a
prefix is itself a fair sample, and a run at 20,000 pairs is a *subset* of the
one at 76,400 rather than a different experiment. The default is 20,000: per
street frequency correlates 0.96 with the full set and shares 85 of the top
100 streets, for a run about four times faster.

Each node weighting has its own sample and its own baseline. Switching
weighting changes the trips, so the numbers are not comparable across
weightings. All of them draw from the same junction pool (the cap is drawn
uniformly, with the same seed), so they share the betweenness.

Uniform is drawn with the area. The three others are drawn and routed on the
first request that asks for them, once per area. Measured on areas of the
store at 76,400 pairs, one more weighting costs:

| area | the area, uniform only | one more weighting | first request |
|---|---|---|---|
| Chur, 3 km | 15 MB | +14 MB | 0.5 s |
| Lausanne, 3 km | 19 MB | +17 MB | 0.9 s |
| Zurich, 5 km | 27 MB | +22 MB | 1.5 to 1.9 s |

So an area with all four comes near 100 MB (94 MB for Zurich, 5 km). The area registry counts every
sample in its memory budget.

---

## 3. Routing

`routing_engine.py`. Every trip takes the cheapest path, igraph Dijkstra, one
search per origin serving all its destinations. Routes are stored as flat
arrays of edge ids rather than objects: at 76,400 trips the objects cost more
than the routing. Per trip the model sums `length`, `travel_time`, `elev_gain`
and CO₂ along the path.

**The rule that makes the comparison mean something.** The baseline and the
scenario are built the same way, in every mode: routes are **chosen** on
congested travel times (section 4), distances, durations and CO₂ are
**reported** free flow, and the trips are the same ones (with elastic demand,
the same ones as long as the scenario does not reach them, section 7). So a
scenario that changes nothing changes no number. That was not true before,
when the baseline was routed free flow and a scenario chose on congested times.

**A closed street is a travel time of `+inf`**, and igraph reads that as a very
large cost, not as a missing edge: with no other way through it still hands
back a path down the closed street. So a trip whose path still costs `+inf`
after routing is marked **failed** and its edges are dropped. A trip whose
destination became unreachable has no route; it does not take an impossible
one.

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

Computed in chunks of 50 source junctions, targets always the whole pool.
The sum over (source, target) pairs is the same either way; chunking only
stops one 500 ms igraph call from holding the GIL and freezing the server.

Since it needs no trip, it is the first thing an area has. A new area is built
in two phases (`area_builder.start` and `finish`): the first one cuts the
graph and computes the betweenness, and `POST /api/v1/areas` answers there,
with `ready: false`. The second one draws the trips on the same pool and
routes the baseline, in the background. Meanwhile the map shows the
betweenness from `GET /api/v1/areas/{id}/betweenness`, and a routing request
answers 409 `area_not_ready`. The two phases give the same trips and the same
numbers as a build in one go.

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

## 7. The scenario models

`recalculate.py`. Two choices, and they combine: how the trips are assigned to
the network (targeted or equilibrium), and whether their destinations can move
(elastic demand).

Each set of options has its **Model state**: the same model run on the
untouched network. It is what the Model step of the tool draws, what
`GET /routes/baseline` serves (with `use_congestion` and
`congestion_iterations`), and the left side of every comparison. A scenario
that changes nothing gives it back exactly, whatever the options.

### Targeted reroute (the default)

Only the trips that used a modified street pick a new route. Everybody else
keeps theirs, which is exact: their path does not touch anything that changed.

Those trips choose on **congested** travel times, from the betweenness of the
modified network, which is the rule the baseline was routed with on the
untouched one. Without congestion in the cost, every displaced trip would pile
onto the one next-fastest street.

Cheap, because closing a street usually touches a minority of trips. With
elastic demand, the trips that got a new destination are routed again too.

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

The baseline is **the same MSA run on the untouched network**, not the
free-flow one, cached per (trips, iterations). Otherwise the deltas would
mostly show congestion spreading traffic around, which happens with or without
a scenario: an empty scenario used to report 1,444 trips moving and 70 minutes
of extra driving on Lausanne at 20,000 trips. It costs one extra run, on the
first request at that pair count.

The map gets the **averaged volumes**, the impact table the routes of the last
pass, the only thing a per-trip comparison can be made on. With elastic demand
the loop runs on the redrawn trips.

### Elastic demand

Trips keep their origin, and a trip the scenario touched may draw a **new
destination**, with the rule of the initial sample (section 2, the same
destination weight `w_d`) on the times of the modified network. A destination
behind a closed street is far away now, so the draw moves off it. A weekday
morning trip still goes to a place of work.

Fixed demand assumes a traveller drives to the same place whatever it costs,
so a closure shows up as an implausible total travel time. Here it shows up as
trips getting shorter.

**The redraw is paired with the startup draw.** Two draws with other random
numbers differ even on the same network, so a plain second draw moved traffic
in an empty scenario (+139 km and +52 kg of CO₂ on Lausanne at 20,000 trips).
Instead, each trip has two random numbers of its own, `v0` and `v1`, drawn once
from the area seed. With `p` the probability of its destination `d` on the
times of the startup draw and `p'` the one on the scenario times:

    keep d     when v0 < p'(d) / p(d)
    else draw  from max(p' − p, 0), normalised, with v1

The new destinations follow `p'` exactly, and no other pairing moves fewer
trips. So:

- on the untouched network `p' = p` and nobody moves: the Model state of
  elastic demand is the startup draw itself, the same map as fixed demand;
- an origin whose times did not change keeps every destination;
- a destination made less likely loses trips, one made more likely gains some.

**Which times.** The draw uses the startup traffic estimate with the scenario
on top: the betweenness the startup draw used, plus the scenario's speeds and
closures. Not the betweenness of the modified network: that one moves a little
everywhere (section 9), and a trip across the city would change its
destination for a reason nobody can see on the map. The routes are still
chosen on the modified network, as in the other models.

On Lausanne at 20,000 trips, closing the busiest street (2,165 trips use it)
moves the destination of 192 trips, 5 of which never used it. Fixed demand
reports −1,347 km, +5,118 min and 20 failed trips; elastic demand −2,425 km,
+4,061 min and none, since the trips cut off from their destination go
somewhere else.

A trip that moved is not the same trip any more, so no per-trip comparison
means anything: the impact panel shows totals only, over the trips routed
again that have a route on both sides. Pairs a client sends keep their
destinations, since the redraw needs the pool and the draw they came from.

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

**Routes are chosen on congested time and reported free flow.** Both sides do
it, so the comparison is fair, but a reported detour is the free-flow cost of a
congestion-aware path, not the fastest free-flow path. Use the equilibrium mode
when the travel-time numbers themselves matter.

**A street made faster only draws the trips already on it.** The targeted mode
re-routes the trips that used a modified street and nobody else, so raising a
speed limit shows the gain for its current traffic, never the traffic it would
attract. Run the equilibrium mode for that.

**Closing a street moves the betweenness of every other one**, so in principle
a trip that never used it could prefer another route now. The targeted mode
keeps its route; the equilibrium mode does not make the assumption.

**The equilibrium mode shows two things at once**: the map has the averaged
volumes, the impact table the routes of the last pass. Close, not identical.

**Elastic demand only moves the trips the scenario reaches.** The destinations
are drawn on the startup traffic plus the scenario, not on the traffic of the
modified network, so an origin whose times did not change keeps all its
destinations, even when the closure moved traffic, and so congestion, near
them. This second order effect is left out on purpose: without it, an empty
scenario is exactly zero and a far trip never moves for no visible reason.

**Only cars.** No buses, bikes, pedestrians or trains; no traffic lights, no
junction delay, no turn restrictions beyond what the OSM graph encodes.

**The weekday weightings only move where trips start and end.** They are not
a peak-hour model: the number of trips, `daily_km_driven`, the congestion
curve and the trip-length curve are the same as for the daily average. The
morning is the daily traffic with residents at the start and jobs at the
end, not the traffic of 7 to 9 am.

And the effect is small. Ranks are a soft scale, and the busy junctions of a
town tend to have both residents and jobs. On areas of the store at 76,400
pairs, mean of three seeds, Pearson r of the per-street counts. The noise
floor is the same area built with two seeds, so its junction pool is drawn
again too:

| | Lausanne, 6 km | Chur, 3 km |
|---|---|---|
| daily average, two seeds, one direction per street (noise) | 0.958 | 0.984 |
| daily average, two seeds, both directions summed (noise) | 0.970 | 0.992 |
| morning against evening, one direction per street | 0.960 | 0.953 |
| morning against evening, both directions summed | 0.985 | 0.985 |

In a small town (Chur) the morning and the evening differ by more than the
noise in one direction, so a one-way closure or a speed limit in one direction
reads differently. In a big area (Lausanne, 6 km) the difference is about the
size of the noise. The map sums both directions, and there the two pictures
are nearly the same everywhere.

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
