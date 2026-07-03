# %% [markdown]
# # 01 — How the PDPTW model works
#
# This notebook explains, from the ground up, the methodology used in the
# [EPFL-ENAC/pdptw](https://github.com/EPFL-ENAC/pdptw) project to plan Swiss Post
# tours. No prior knowledge of vehicle routing is assumed.
#
# **Contents**
# 1. The vehicle-routing problem family (TSP → CVRP → VRPTW → PDPTW)
# 2. The exact model used in the pdptw project (the Gurobi MILP), explained piece by piece
# 3. What the solver guarantees — exact vs heuristic (Gurobi vs PyVRP)
# 4. A toy PDPTW solved by brute force, so every mechanism is visible
# 5. **The key subtlety for our divergence question**: with time windows, a uniform
#    error in the travel-time matrix does *not* just shift the result proportionally

# %%
import itertools

import matplotlib.pyplot as plt
import numpy as np

rng = np.random.default_rng(42)

# %% [markdown]
# ## 1. The problem family
#
# All routing problems below take a set of locations and a **travel-time (or distance)
# matrix** `T[i][j]` and ask for an ordering of visits minimizing total cost:
#
# | Problem | Adds | Question it answers |
# |---|---|---|
# | **TSP** | — | Shortest tour through all points |
# | **CVRP** | vehicle **C**apacity, several vehicles | Which vehicle visits what, in what order |
# | **VRPTW** | **T**ime **W**indows per stop | ...while arriving inside each stop's allowed interval |
# | **PDPTW** | **P**ickup–**D**elivery pairing | ...when goods move *between* customers, not just from a depot |
#
# In the Swiss Post case:
# - **hub-based shipments** (636 in the instance) are "depot → customer" or
#   "customer → depot" tasks — VRPTW-like;
# - **transport shipments** (128) are "customer A → customer B" tasks — this is what
#   makes it a true PDPTW: the same vehicle must do the pickup *before* the delivery.
#
# Two structural facts drive everything else:
# 1. The problem is **NP-hard**: no algorithm is known that finds the optimum in
#    polynomial time. Exact solvers enumerate cleverly (branch & bound); heuristics
#    search cleverly (genetic/local search). Both rely *entirely* on the matrix `T`.
# 2. The matrix is the **only** notion of geography the solver has. Coordinates are
#    used for plotting only. If the matrix is wrong, everything downstream is wrong
#    in exactly the way the matrix is wrong.

# %% [markdown]
# ## 2. The pdptw project's model, piece by piece
#
# The project (file `pdptw/models.py`, function `single_day_pdptw`) builds a
# **pickup-and-delivery graph** `G_pd` per day, then a **MILP** (Mixed-Integer Linear
# Program) solved by Gurobi. Here is the complete anatomy.
#
# ### The graph `G_pd`
# For a day with $n$ requests, the graph has $2n + 2$ nodes:
#
# - node $0$: tour **start** (the vehicle's starting location — the hub);
# - node $2i+1$: **pickup** of request $i$ (labelled $P_i$);
# - node $2i+2$: **delivery** of request $i$ (labelled $D_i$);
# - node $2n+1$: tour **end**.
#
# Every arc $(i, j)$ carries the travel time between the *physical* locations of
# tasks $i$ and $j$, looked up in the matrix: `travel_time_matrix[phy(i), phy(j)]`.
# Impossible arcs are excluded (into Start, out of End, Start→any delivery, ...).
#
# ### Decision variables
# | Variable | Type | Meaning |
# |---|---|---|
# | $x_{ij}$ | binary | 1 if the vehicle drives arc $(i,j)$ |
# | $t_i$ | continuous | time of day (minutes) at which task $i$ is served |
# | $qv_i, qw_i$ | continuous | volume / weight on board right after task $i$ |
# | $y_i$ | binary | 1 if task $i$ is served at all (0 = shipment skipped) |
#
# ### Constraints (each maps to a few lines of `models.py`)
# 1. **Flow**: each served task has exactly one predecessor and one successor
#    ($\sum_i x_{ij} = y_j$, $\sum_j x_{ij} = y_i$).
# 2. **Time propagation** (big-M): if the vehicle drives $i \to j$ then
#    $t_j \ge t_i + s + T_{ij} - M(1 - x_{ij})$, where $s$ is the service time
#    (**assumed a uniform 5 min for every stop** — we will question that in
#    notebook 05) and $M$ a large constant that deactivates the constraint when
#    the arc is not used.
# 3. **Time windows**: $a_i \le t_i \le b_i$ per task.
# 4. **Pairing**: pickup before delivery ($t_{D_i} \ge t_{P_i} + s$) and
#    "skip pickup ⇔ skip delivery" ($y_{D_i} = y_{P_i}$).
# 5. **Capacity**: load propagation along used arcs, bounded by vehicle capacity
#    (both volume and weight).
# 6. **Boundary**: $t_0 = 420$ (07:00) and — noteworthy — $t_{end} = 1020$ (17:00)
#    is **fixed**, so the model's "tour" formally always spans 10 h; the real
#    optimization signal is the travel-time objective below.
#
# ### Objective (two phases)
# **Phase 1** minimizes
# $$\sum_{(i,j)} T_{ij}\, x_{ij} \;+\; \alpha \, W \sum_i (1 - y_i)$$
# — total driving time plus a penalty per skipped shipment, with $W$ chosen so
# large that serving everything is always preferred when feasible ($\alpha \in [0,1]$
# tunes how bad skipping is). **Phase 2** re-optimizes the same solution to make
# it "human-like" (fewer zig-zags) without degrading Phase 1's objective.
#
# > **What to remember:** the model minimizes *driving time*, treats service time
# > as a constant 5 min per stop, and reports "Travel time" — which is **not** the
# > same quantity as a Swiss Post tour *duration* (drive + service + wait).
# > Comparing the two directly is already a category error; notebook 03 constructs
# > the correct comparison.

# %% [markdown]
# ## 3. What the solver guarantees
#
# **Gurobi (used by the pdptw project)** is an *exact* solver: branch & bound
# explores the space of integer solutions, keeping a lower bound (LP relaxation)
# and an upper bound (best solution found). The gap between them is the
# **optimality gap**. Run long enough, the gap hits 0 and the solution is *provably
# optimal*. Stopped early (`time_limit`, `sufficient_gap`), you get a feasible
# solution plus a certificate: "at most X% worse than the optimum".
#
# **PyVRP (used in this repo's backend, and in notebook 05)** is a
# *metaheuristic* — hybrid genetic search: a population of solutions, crossover,
# and local-search "education" of offspring. It scales to thousands of stops and
# is usually excellent, but it gives **no bound**: you never know how far from
# optimal you are, and the result depends on the random seed and the runtime.
#
# Consequence for our divergence question: when comparing our results with Swiss
# Post's, part of the difference can simply be **solver noise / optimality gap**
# — from either side (Swiss Post's own solver is also a heuristic under a time
# budget). Notebook 05 measures this noise band so we can tell it apart from
# systematic effects.

# %% [markdown]
# ## 4. A toy PDPTW, solved by brute force
#
# Small enough to enumerate *every* feasible tour — so we can see exactly what the
# solver "thinks about". Three requests, six tasks, one vehicle of capacity 10.

# %%
# --- Toy world -------------------------------------------------------------
# Physical locations on a plane; travel time = euclidean distance in minutes.
locations = {
    "hub": (0.0, 0.0),
    "A": (2.0, 8.0),
    "B": (7.0, 6.0),
    "C": (8.0, 1.0),
    "D": (3.0, 3.0),
}
# Requests: (pickup_location, delivery_location, size)
requests = [
    ("hub", "A", 4),  # hub-based: bring a parcel from the hub to A
    ("B", "C", 6),    # transport: move goods from B to C
    ("hub", "D", 3),  # hub-based
]
CAPACITY = 10
SERVICE_MIN = 2.0
START_MIN = 0.0

# Time windows per task (None = always open). Try changing these!
time_windows = {
    ("P", 0): None, ("D", 0): None,
    ("P", 1): None, ("D", 1): None,
    ("P", 2): None, ("D", 2): None,
}


def travel(a: str, b: str) -> float:
    (x1, y1), (x2, y2) = locations[a], locations[b]
    return float(np.hypot(x2 - x1, y2 - y1))


def phy(task) -> str:
    kind, i = task
    return requests[i][0] if kind == "P" else requests[i][1]


def simulate(order) -> dict | None:
    """Drive the task sequence; return costs, or None if infeasible."""
    t, load, drive = START_MIN, 0.0, 0.0
    pos = "hub"
    for task in order:
        leg = travel(pos, phy(task))
        drive += leg
        t += leg
        tw = time_windows[task]
        if tw is not None:
            if t > tw[1]:
                return None          # arrived after the window closed
            t = max(t, tw[0])        # arrived early -> wait
        t += SERVICE_MIN
        load += requests[task[1]][2] * (1 if task[0] == "P" else -1)
        if load > CAPACITY:
            return None              # overloaded
        pos = phy(task)
    leg = travel(pos, "hub")
    return {"drive": drive + leg, "end_time": t + leg}


def all_feasible_orders():
    """All task permutations with each pickup before its delivery."""
    tasks = [("P", i) for i in range(len(requests))] + [
        ("D", i) for i in range(len(requests))
    ]
    for perm in itertools.permutations(tasks):
        if all(perm.index(("P", i)) < perm.index(("D", i)) for i in range(len(requests))):
            yield perm


results = []
for order in all_feasible_orders():
    sim = simulate(order)
    if sim is not None:
        results.append((sim["drive"], order))
results.sort(key=lambda r: r[0])

print(f"feasible orders: {len(results)}")
best_drive, best_order = results[0]
labels = [f"{k}{i}" for k, i in best_order]
print(f"optimal order : hub -> {' -> '.join(labels)} -> hub")
print(f"optimal drive : {best_drive:.2f} min")
print(f"worst feasible: {results[-1][0]:.2f} min  (x{results[-1][0] / best_drive:.2f})")

# %% [markdown]
# Even with 3 requests there are 90 precedence-valid orders (of which 54 survive
# the capacity constraint here), and the worst feasible tour is nearly twice as
# long as the best — *the ordering is where all the optimization value lives*.
# At Swiss Post scale (dozens of stops), enumeration is impossible
# ($2n$ tasks → $(2n)!/2^n$ orders), hence MILP or metaheuristics.

# %%
# --- Plot the optimal toy tour ---------------------------------------------
fig, ax = plt.subplots(figsize=(6, 5))
for name, (x, y) in locations.items():
    ax.scatter(x, y, s=180 if name == "hub" else 90,
               c="black" if name == "hub" else "tab:blue",
               marker="s" if name == "hub" else "o", zorder=3)
    ax.annotate(name, (x, y), textcoords="offset points", xytext=(8, 6))

path = ["hub"] + [phy(t) for t in best_order] + ["hub"]
xs = [locations[p][0] for p in path]
ys = [locations[p][1] for p in path]
ax.plot(xs, ys, "-", c="tab:orange", lw=2, zorder=2)
for a, b in zip(path[:-1], path[1:]):
    ax.annotate("", xy=locations[b], xytext=locations[a],
                arrowprops=dict(arrowstyle="->", color="tab:orange", lw=2))
ax.set_title(f"Optimal toy PDPTW tour — drive {best_drive:.1f} min")
ax.set_aspect("equal")
plt.tight_layout()
plt.show()

# %% [markdown]
# ## 5. The key subtlety: uniform matrix errors × time windows
#
# The central hypothesis we want to test in this notebook series is:
#
# > *"our OSM matrix is a roughly constant factor faster than Swiss Post's
# > matrix (no congestion), so our methodology is fine — results just need a
# > scalar correction."*
#
# **Without time windows this would be exactly true.** Multiplying every entry of
# the matrix by $k > 0$ multiplies the total drive of *every* tour by $k$, so the
# *ranking* of tours is unchanged: the optimal ordering is identical, the objective
# just scales. (Proof: $\sum T'_{ij} x_{ij} = k \sum T_{ij} x_{ij}$ for any $x$.)
#
# **With time windows, this breaks.** Windows anchor *absolute* times: if all
# legs get 15% slower, a tour that used to slip inside an 08:00–08:30 delivery
# window may no longer fit — the optimizer must then *reorder*, *wait*, or *skip*.
# A uniform matrix error can therefore produce **structurally different routes**,
# not just a scaled objective. Let's demonstrate on the toy problem:

# %%
# Give request 1's delivery a window that is comfortable at speed x1.0
time_windows[("D", 1)] = (14.0, 20.0)

def solve(scale: float):
    """Brute-force the toy PDPTW with all travel times scaled by `scale`."""
    global locations
    original = dict(locations)
    # scaling all coordinates scales all euclidean travel times
    locations = {n: (x * scale, y * scale) for n, (x, y) in locations.items()}
    try:
        res = []
        for order in all_feasible_orders():
            sim = simulate(order)
            if sim is not None:
                res.append((sim["drive"], order))
        if not res:
            return None, None
        return min(res, key=lambda r: r[0])
    finally:
        locations = original


for scale in (1.0, 1.15, 1.4):
    drive, order = solve(scale)
    if order is None:
        print(f"scale x{scale:>4}: INFEASIBLE — no order satisfies the windows")
    else:
        seq = " -> ".join(f"{k}{i}" for k, i in order)
        print(f"scale x{scale:>4}: drive {drive:6.2f} min | order {seq}")

# %% [markdown]
# Three regimes appear as the matrix gets uniformly slower:
#
# 1. **×1.0** — the window already forces a detour (drive 40.0 instead of the
#    unconstrained optimum 27.9): time windows shape routes even before any
#    matrix error.
# 2. **×1.15** — the optimizer *reorders the tasks* (a structurally different
#    route). Here the cost still lands near 1.15× by luck, but the route is no
#    longer the same one — route-level comparisons (overlap of stop sequences)
#    would already show divergence.
# 3. **×1.4** — the instance becomes **infeasible**; in the real model the `y`
#    variables kick in and shipments get **skipped**, changing the reported
#    travel time discontinuously.
#
# **Consequences for the diagnosis** (tested on real data in notebooks 04–05):
# 1. Comparing the *matrices* element-wise (notebook 04) is the clean test of the
#    "constant factor" hypothesis — it is not confounded by the optimizer.
# 2. Comparing *tour totals* mixes matrix error, time-window interactions,
#    service-time assumptions, and solver noise. Notebook 05 uses
#    **fixed-sequence re-evaluation** (re-cost Swiss Post's own stop sequences
#    under our assumptions) to unmix them.
#
# Continue with **02 — data characterization**.
