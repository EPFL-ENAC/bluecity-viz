# %% [markdown]
# # 04 — OSM vs Swiss Post: is the matrix gap a constant factor, or structural?
#
# This is the core diagnostic. We compare an OpenStreetMap-derived travel-time
# matrix against Swiss Post's provided matrix, element by element, and test the
# hypothesis:
#
# > $T^{SP}_{ij} \approx k \cdot T^{OSM}_{ij}$ for a single scalar $k$
# > (e.g. "our free-flow graph is ~15% optimistic because it ignores congestion").
#
# If that holds, the methodology is sound and $k$ is a calibration constant. If it
# doesn't — if the bias depends on distance, direction or geography — a scalar
# correction is *wrong*, and notebook 01 §5 showed why time windows amplify even a
# *uniform* error into structural route changes.
#
# **Outputs**: `outputs/summary_od_comparison.json` (k̂ used by notebook 05).

# %%
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sppdptw import config, extraction, io, matrixtools, osm

config.OUTPUTS_DIR.mkdir(exist_ok=True)
instance, sol, M_SP, index_mapping = io.load_all()
nodes = extraction.build_nodes_df(instance, index_mapping)

# %% [markdown]
# ## 1. Getting the OSM matrix
#
# Priority order:
# 1. **your own matrix** — set `OSM_MATRIX_PATH` below (`.npy` 82×82 in matrix-index
#    order, or wide/long CSV — see `data/README.md`);
# 2. a **previously built** matrix in `data/cache/`;
# 3. **build now** from OSMnx (downloads the Bern drive network once — needs
#    internet, a few minutes);
# 4. fallback: a **DEMO matrix** with *known planted effects* (global factor 1.15,
#    a +25% congested center, 2% corrupted pairs) so the whole notebook runs
#    end-to-end and demonstrably *recovers* what was planted. Every figure is
#    labeled DEMO in that case — conclusions about the real question need source
#    1, 2 or 3.

# %%
OSM_MATRIX_PATH = None  # <-- point this at your matrix file to use it


def load_user_matrix(path) -> np.ndarray:
    path = str(path)
    if path.endswith(".npy"):
        m = np.load(path)
    else:
        df = pd.read_csv(path)
        if {"from_index", "to_index", "value"} <= set(df.columns):  # long format
            n = int(max(df.from_index.max(), df.to_index.max())) + 1
            m = np.full((n, n), np.nan)
            m[df.from_index, df.to_index] = df.value
        else:  # wide format, first column = index
            m = df.set_index(df.columns[0]).to_numpy(dtype=float)
    assert m.shape == M_SP.shape, f"expected {M_SP.shape}, got {m.shape}"
    return m


snaps, truth = None, None
if OSM_MATRIX_PATH:
    M_OSM, source = load_user_matrix(OSM_MATRIX_PATH), "user file"
elif osm.MATRIX_CACHE.exists():
    M_OSM, snaps = osm.build_osm_matrix(nodes)
    source = "cached OSMnx build"
else:
    try:
        M_OSM, snaps = osm.build_osm_matrix(nodes)
        source = "fresh OSMnx build"
    except Exception as exc:  # no network — run in demo mode
        print(f"OSMnx build unavailable ({type(exc).__name__}: {exc})")
        M_OSM, truth = osm.demo_matrix(M_SP, nodes)
        source = "DEMO (synthetic, planted effects)"

DEMO = source.startswith("DEMO")
tag = " [DEMO]" if DEMO else ""
print(f"OSM matrix source: {source}")

# %% [markdown]
# ### Units sanity check
#
# Whatever the source, verify both matrices measure the same quantity before
# comparing (notebook 02's sniffing logic). Comparing seconds against meters is
# the single fastest way to get a huge, meaningless "divergence".

# %%
hav = matrixtools.haversine_matrix(nodes.lat.values, nodes.lon.values)
for name, m in [("SwissPost", M_SP), ("OSM", M_OSM)]:
    best = matrixtools.sniff_units(np.nan_to_num(m), hav).iloc[0]
    print(f"{name:10s} -> {best.hypothesis:22s} (score {best.score:.1%})")
    assert "time" in best.hypothesis, f"{name} does not look like travel TIMES"

# %% [markdown]
# ## 2. Element-wise comparison

# %%
n = len(M_SP)
off_diag = ~np.eye(n, dtype=bool)
valid = off_diag & np.isfinite(M_OSM) & (M_OSM > 0) & (M_SP > 0)
x = M_OSM[valid]  # OSM seconds
y = M_SP[valid]  # Swiss Post seconds
ratio = y / x
print(f"comparable OD pairs: {valid.sum()} / {off_diag.sum()}")
print(f"ratio SP/OSM: median {np.median(ratio):.3f}, "
      f"geometric mean {np.exp(np.mean(np.log(ratio))):.3f}, "
      f"5–95% [{np.quantile(ratio, 0.05):.2f}, {np.quantile(ratio, 0.95):.2f}]")

fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
axes[0].scatter(x / 60, y / 60, s=6, alpha=0.3)
lim = max(x.max(), y.max()) / 60 * 1.02
axes[0].plot([0, lim], [0, lim], "k--", lw=1, label="y = x")
axes[0].plot([0, lim], [0, lim * np.median(ratio)], "r-", lw=1,
             label=f"y = {np.median(ratio):.2f}·x (median ratio)")
axes[0].set_xlabel("OSM (min)"); axes[0].set_ylabel("Swiss Post (min)")
axes[0].set_title(f"OD travel times{tag}"); axes[0].legend()

axes[1].hist(ratio, bins=60)
axes[1].axvline(1, c="k", ls="--", lw=1)
axes[1].axvline(np.median(ratio), c="r", lw=1)
axes[1].set_xlabel("ratio SP / OSM"); axes[1].set_title(f"Ratio distribution{tag}")
plt.tight_layout(); plt.show()

# %% [markdown]
# ## 3. The constant-factor hypothesis, formally
#
# Three nested fits distinguish the possible error shapes:
#
# | Fit | If it wins, the story is |
# |---|---|
# | $y = k\,x$ (through origin) | pure multiplicative shift — **apply factor $k$, methodology OK** |
# | $y = k\,x + c$, $c > 0$ | multiplicative + **fixed per-trip overhead** (parking, access…) |
# | $\log y = a + b \log x$, $b \ne 1$ | **distance-dependent** bias — no scalar fixes it |
#
# plus a Breusch–Pagan test: even with a good mean fit, *heteroscedastic*
# residuals mean the correction's reliability varies across pairs.

# %%
fo = matrixtools.fit_through_origin(x, y)
af = matrixtools.fit_affine(x, y)
ll = matrixtools.fit_loglog(x, y)
bp = matrixtools.breusch_pagan(x, y)

print(f"through-origin : k = {fo['k']:.3f}                     R² = {fo['r2']:.4f}")
print(f"affine         : k = {af['k']:.3f} ± {af['k_se']:.3f}, "
      f"c = {af['c']:.1f} ± {af['c_se']:.1f} s   R² = {af['r2']:.4f}")
print(f"log-log        : b = {ll['slope_b']:.3f} ± {ll['slope_se']:.3f}, "
      f"implied k = {ll['implied_k']:.3f}    R² = {ll['r2']:.4f}")
print(f"Breusch–Pagan  : p = {bp['p_value']:.2e} "
      f"({'heteroscedastic' if bp['p_value'] < 0.01 else 'homoscedastic'})")

k_hat = fo["k"]

# %%
# The most readable view: ratio quantile bands vs trip length. A constant factor
# is a flat band; slopes/steps reveal distance dependence.
bins = np.quantile(x, np.linspace(0, 1, 13))
bin_id = np.digitize(x, bins[1:-1])
centers, q10, q50, q90 = [], [], [], []
for b in range(12):
    r = ratio[bin_id == b]
    if len(r) >= 10:
        centers.append(x[bin_id == b].mean() / 60)
        q10.append(np.quantile(r, 0.1)); q50.append(np.quantile(r, 0.5))
        q90.append(np.quantile(r, 0.9))

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.fill_between(centers, q10, q90, alpha=0.25, label="10–90% band")
ax.plot(centers, q50, "-o", label="median ratio")
ax.axhline(k_hat, c="r", ls="--", lw=1, label=f"k̂ = {k_hat:.2f}")
ax.axhline(1, c="k", lw=0.5)
ax.set_xlabel("OSM travel time (min)"); ax.set_ylabel("ratio SP / OSM")
ax.set_title(f"Is the factor constant across trip lengths?{tag}")
ax.legend(); plt.tight_layout(); plt.show()

# %% [markdown]
# ## 4. Where does the residual live? (geography & direction)
#
# If the ratio clusters by *place*, the culprit is spatial (congestion zones,
# snapping errors, missing roads). If it clusters by *direction*
# ($r_{ij} \ne r_{ji}$), suspect one-way handling or time-of-day asymmetries.

# %%
resid_ratio = np.full_like(M_SP, np.nan)
resid_ratio[valid] = (M_SP[valid] / (k_hat * M_OSM[valid]))

per_origin = np.nanmean(resid_ratio, axis=1)
per_dest = np.nanmean(resid_ratio, axis=0)

fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
for ax, vals, ttl in [(axes[0], per_origin, "as origin"),
                      (axes[1], per_dest, "as destination")]:
    sc = ax.scatter(nodes.lon, nodes.lat, c=vals, cmap="coolwarm",
                    vmin=0.8, vmax=1.2, s=60)
    ax.set_title(f"mean ratio / k̂, {ttl}{tag}")
    ax.set_aspect(1 / np.cos(np.radians(nodes.lat.mean())))
fig.colorbar(sc, ax=axes, shrink=0.8, label="ratio relative to k̂ (1 = perfect)")
plt.show()

# %%
# Direction dependence: compare r_ij with r_ji
both = valid & valid.T
with np.errstate(divide="ignore", invalid="ignore"):
    r_full = M_SP / M_OSM
r_fwd = r_full[both]
r_bwd = r_full.T[both]
fig, ax = plt.subplots(figsize=(5, 5))
ax.scatter(r_fwd, r_bwd, s=5, alpha=0.3)
ax.plot([r_fwd.min(), r_fwd.max()], [r_fwd.min(), r_fwd.max()], "k--", lw=1)
ax.set_xlabel("ratio i→j"); ax.set_ylabel("ratio j→i")
ax.set_title(f"Direction dependence of the ratio{tag}")
plt.tight_layout(); plt.show()
dir_corr = float(np.corrcoef(r_fwd, r_bwd)[0, 1])
print(f"corr(r_ij, r_ji) = {dir_corr:.3f} "
      "(high = direction-neutral error; low = direction-dependent)")

# %% [markdown]
# ## 5. Outlier forensics
#
# The 20 worst pairs (largest |log ratio|), with the ingredients to diagnose each:
# straight-line distance, both times, implied speeds — and the endpoint snap
# distances when the matrix was built here (a big snap distance means the OSM
# matrix answered the question for the *wrong point*).

# %%
logr = np.abs(np.log(resid_ratio))
flat = np.argsort(np.nan_to_num(logr, nan=-1).ravel())[::-1][:20]
rows = []
for f in flat:
    i, j = divmod(f, n)
    row = {
        "from": i, "to": j,
        "hav_km": hav[i, j] / 1000,
        "osm_min": M_OSM[i, j] / 60,
        "sp_min": M_SP[i, j] / 60,
        "ratio": M_SP[i, j] / M_OSM[i, j],
    }
    if snaps is not None:
        row["snap_from_m"] = snaps.snap_dist_m.iloc[i]
        row["snap_to_m"] = snaps.snap_dist_m.iloc[j]
    rows.append(row)
outliers = pd.DataFrame(rows)
print(outliers.round(2).to_string(index=False))

# %% [markdown]
# Diagnosis guide: `ratio ≫ k̂` with normal snap distances → OSM missing a slow
# segment or congestion pocket; extreme ratio with a large snap distance → wrong
# snap; `ratio < 1` (OSM *slower* than Swiss Post) → missing road/turn in OSM or a
# corrupted pair. In DEMO mode these are exactly the planted corrupted pairs.
#
# ## 6. Permutation sanity check
#
# The bluecity backend's matrix builder (`cvrp_service._create_distance_matrix`)
# computes the OD matrix over `list(set(nodes))` — a Python-set order — but
# consumes it in a *different* order. A matrix built that way has the right value
# *distribution* but wrong per-pair values. Signature: near-zero pairwise
# correlation with a reference despite near-identical sorted distributions.

# %%
perm = matrixtools.permutation_check(np.nan_to_num(M_OSM), M_SP)
print({k: round(v, 3) if isinstance(v, float) else v for k, v in perm.items()})
if perm["suspect_permutation"]:
    print("!! value distributions match but pairs don't — the OSM matrix is "
          "likely PERMUTED (index-ordering bug). Fix the ordering before any "
          "other conclusion.")
else:
    print("no permutation signature — index alignment looks sound.")

# %% [markdown]
# ## 7. Verdict

# %%
if abs(ll["slope_b"] - 1) < 0.05 and fo["r2"] > 0.9:
    shape = "uniform"
    verdict = (
        f"UNIFORM factor: SP ≈ {k_hat:.2f} × OSM explains the gap "
        f"(R²={fo['r2']:.3f}). Methodology sound — apply k, then re-check "
        "time-window feasibility (notebook 01 §5)."
    )
elif af["r2"] > 0.95 and abs(ll["slope_b"] - 1) < 0.1:
    shape = "affine"
    verdict = (
        f"AFFINE, near-uniform: SP ≈ {af['k']:.2f} × OSM + {af['c']:.0f} s "
        f"(R²={af['r2']:.3f}). Methodology sound with a TWO-parameter "
        "calibration: a multiplicative factor (congestion & speed limits) plus "
        "a fixed per-trip overhead (junction/access time). A single scalar "
        "over-corrects long trips and under-corrects short ones."
    )
else:
    shape = "structural"
    verdict = (
        "STRUCTURAL differences beyond a scalar — inspect §3 (distance "
        "dependence), §4 (geography/direction), §5 (snapping) for which kind."
    )
print(f"[{source}] {verdict}")

summary = {
    "source": source,
    "k_through_origin": fo["k"],
    "r2_through_origin": fo["r2"],
    "affine_k": af["k"], "affine_c_s": af["c"],
    "loglog_slope": ll["slope_b"], "loglog_r2": ll["r2"],
    "breusch_pagan_p": bp["p_value"],
    "ratio_median": float(np.median(ratio)),
    "ratio_q05": float(np.quantile(ratio, 0.05)),
    "ratio_q95": float(np.quantile(ratio, 0.95)),
    "direction_corr": dir_corr,
    "permutation_suspect": perm["suspect_permutation"],
    "gap_shape": shape,
    "verdict": verdict,
    "planted_truth": truth,
}
with open(config.OUTPUTS_DIR / "summary_od_comparison.json", "w") as f:
    json.dump(summary, f, indent=2)
print("\nsummary written")

# %% [markdown]
# In **DEMO mode**, sanity-check the machinery against the planted truth: k̂
# should land near 1.15×1.05 (global factor times the average congestion-zone
# effect), the residual maps should light up the synthetic "congested center",
# and the outlier table should be dominated by the corrupted pairs. With a real
# OSM matrix, these same instruments answer the real question.
#
# Next: **05 — how much of the tour-level gap does each cause explain?**
