# %% [markdown]
# # 03 — What are "Swiss Post's values", precisely?
#
# Before asking *why our numbers differ from Swiss Post's*, we must pin down what
# Swiss Post's numbers actually are. This notebook dissects the solution file
# (`Mock-n30-d70_solution.json`) and establishes the fact the whole diagnosis
# rests on:
#
# > **Swiss Post's tour values are the output of their solver running on their own
# > travel-time matrix — not GPS-measured driving.** Every driving leg in the
# > solution matches the matrix to the second.
#
# This is excellent news: it means the divergence between our results and theirs
# decomposes *exactly* into (matrix gap) + (modeling gap) + (solver gap), with no
# irreducible "reality noise" term.
#
# **Outputs**: `outputs/benchmark_tours.json` — the per-tour reference table used
# by notebook 05.

# %%
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sppdptw import config, extraction, io, solution

config.OUTPUTS_DIR.mkdir(exist_ok=True)
instance, sol, M, index_mapping = io.load_all()
nodes = extraction.build_nodes_df(instance, index_mapping)
uuid_to_idx = dict(zip(index_mapping["uuid"], index_mapping["index"]))

# %% [markdown]
# ## 1. The solution file's anatomy
#
# Each tour is an *itinerary*: a timestamped event log
# `TourStart → (DrivingStart → DrivingEnd → Arrival → Departure)* → TourEnd`.
# From it we extract every driving leg and every service stop.

# %%
legs = solution.extract_legs(sol, uuid_to_idx)
tours = solution.extract_tours(sol, uuid_to_idx)
print(f"{len(tours)} tours, {len(legs)} driving legs, "
      f"{tours.area_id.nunique()} areas, dates {tours.date.min()}..{tours.date.max()}")

# %% [markdown]
# ## 2. Proof: the solution's driving times ARE the matrix
#
# For every leg, compare the timestamp difference against the matrix entry for
# that (from, to) pair:

# %%
legs["matrix_s"] = [
    M[int(i), int(j)] for i, j in zip(legs.from_idx, legs.to_idx)
]
exact = (legs.seconds == legs.matrix_s).mean()
print(f"legs matching the matrix exactly: {exact:.1%}  "
      f"(n = {len(legs)}, correlation = "
      f"{np.corrcoef(legs.seconds, legs.matrix_s)[0, 1]:.6f})")
assert exact == 1.0, "unexpected: some legs deviate from the matrix"

# %% [markdown]
# 100% — **there is no empirical traffic in the benchmark**. If our OSM matrix
# reproduced Swiss Post's matrix, and our model reproduced their constraints, and
# both solvers reached similar quality, our tour values would match theirs. Each
# of those three "if"s is measured separately in notebooks 04–05.
#
# ## 3. Tour decomposition: total = drive + service + wait
#
# The single most common comparison mistake is holding a *drive-time* number (what
# the pdptw model's objective reports) against a *tour-duration* number. In Swiss
# Post's tours, driving is only ~60% of the duration — service is ~40%:

# %%
d = tours[["drive_min", "service_min", "wait_min"]].sum()
share = d / d.sum()
print(pd.DataFrame({"minutes": d.round(0), "share": (share * 100).round(1)}))

fig, ax = plt.subplots(figsize=(9, 4.5))
t = tours.sort_values("total_min", ignore_index=True)
ax.bar(t.index, t.drive_min, label="drive")
ax.bar(t.index, t.service_min, bottom=t.drive_min, label="service")
ax.bar(t.index, t.wait_min, bottom=t.drive_min + t.service_min, label="wait")
ax.set_xlabel("tour (sorted by duration)"); ax.set_ylabel("minutes")
ax.set_title("All 87 tours: total duration = drive + service + wait")
ax.legend(); plt.tight_layout(); plt.show()

# %% [markdown]
# ## 4. Is the service time in the solution the instance's `visit_time`?
#
# The instance carries a per-location `visit_time`. Check whether the solver used
# it: for each tour, compare observed service minutes against the sum of
# `visit_time` over its stops.

# %%
vt = extraction.get_visit_times(nodes)
tours["service_pred_min"] = tours.stops.apply(
    lambda s: sum(vt.get(x, 0) for x in s[1:-1]) / 60
)
fig, ax = plt.subplots(figsize=(5.5, 5))
ax.scatter(tours.service_pred_min, tours.service_min, s=25)
lim = max(tours.service_min.max(), tours.service_pred_min.max()) * 1.05
ax.plot([0, lim], [0, lim], "k--", lw=1, label="y = x")
ax.set_xlabel("Σ visit_time over stops (min)")
ax.set_ylabel("observed service in solution (min)")
ax.set_title("Service time: solution vs instance visit_time")
ax.legend(); plt.tight_layout(); plt.show()

resid = (tours.service_min - tours.service_pred_min).abs()
print(f"median |difference|: {resid.median():.2f} min; "
      f"tours within 1 min: {(resid < 1).mean():.0%}")

# %% [markdown]
# (Deviations above the line are stops visited more than once or per-shipment
# handling time; the instance-level `visit_time` explains the bulk of it. The
# model's uniform "5 min per stop" does not — notebook 05 quantifies the gap.)
#
# ## 5. The benchmark table
#
# This is the reference our results must be compared against — per tour of the
# studied area, with the drive/service/wait split. Everything is written to
# `outputs/benchmark_tours.json`.

# %%
area_tours = tours[tours.area_id == config.AREA_ID].reset_index(drop=True)
bench_cols = ["date", "n_stops", "n_shipments", "drive_min",
              "service_min", "wait_min", "total_min"]
print(f"area {config.AREA_ID}: {len(area_tours)} tours")
print(area_tours[bench_cols].round(1).to_string(index=False))

# %%
# Distribution snapshot over all 87 tours (the solution file only covers the
# studied area 340070 — typically 2 tours per planning period)
fig, axes = plt.subplots(1, 3, figsize=(11, 3.5))
for ax, col in zip(axes, ["total_min", "drive_min", "n_stops"]):
    ax.hist(tours[col], bins=25)
    ax.set_title(col)
plt.suptitle("All tours: statistics")
plt.tight_layout(); plt.show()

# %%
# The studied area's tours on the map
area_nodes = nodes[nodes.in_areas.apply(lambda a: config.AREA_ID in a)]
idx_to_ll = {r["index"]: (r.lat, r.lon) for _, r in area_nodes.iterrows()}

fig, ax = plt.subplots(figsize=(8, 7))
ax.scatter(area_nodes.lon, area_nodes.lat, c="lightgray", s=35, zorder=1)
hub = area_nodes[area_nodes.is_hub].iloc[0]
ax.scatter(hub.lon, hub.lat, marker="s", c="black", s=90, zorder=3, label="hub")
for _, tour in area_tours.head(6).iterrows():
    pts = [idx_to_ll[s] for s in tour.stops if s in idx_to_ll]
    ax.plot([p[1] for p in pts], [p[0] for p in pts],
            "-o", ms=3, lw=1.2, alpha=0.75, zorder=2, label=str(tour.date))
ax.set_title(f"First tours of area {config.AREA_ID} (straight-line rendering)")
ax.legend(fontsize=8)
ax.set_aspect(1 / np.cos(np.radians(area_nodes.lat.mean())))
plt.tight_layout(); plt.show()

# %%
benchmark = {
    "area_id": int(config.AREA_ID),
    "legs_match_matrix_exactly": True,
    "tours": area_tours.assign(
        stops=area_tours.stops.apply(lambda s: [int(x) for x in s])
    ).to_dict(orient="records"),
    "totals": {
        "drive_min": float(tours.drive_min.sum()),
        "service_min": float(tours.service_min.sum()),
        "wait_min": float(tours.wait_min.sum()),
    },
}
with open(config.OUTPUTS_DIR / "benchmark_tours.json", "w") as f:
    json.dump(benchmark, f, indent=2)
print(f"benchmark written: {len(benchmark['tours'])} tours of area {config.AREA_ID}")

# %% [markdown]
# **Takeaways**
#
# 1. Swiss Post's values are solver output on their matrix — a fully decomposable
#    benchmark, not noisy reality.
# 2. Service (+wait) is a large share of tour duration; any comparison that only
#    looks at drive time understates tours massively.
# 3. The solution's service times are explained by the instance's per-location
#    `visit_time`, not by a uniform constant.
#
# Next: **04 — is the OSM ↔ Swiss Post matrix gap a constant factor, or
# structural?**
