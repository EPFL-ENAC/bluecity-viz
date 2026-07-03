import marimo

__generated_with = "0.23.13"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 02 — What is actually in the Swiss Post data?

    Before comparing anything, we characterize every input file: what quantity the
    travel-time matrix holds (empirically, not by trusting documentation), what the
    shipments and their time windows look like, and which assumptions the
    [EPFL-ENAC/pdptw](https://github.com/EPFL-ENAC/pdptw) extraction code makes —
    including two outright bugs that we demonstrate on the raw data.

    **Outputs**: `outputs/summary_characterization.json` (consumed by notebook 05).
    """)
    return


@app.cell
def _():
    import json

    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from sppdptw import config, extraction, io, matrixtools

    config.OUTPUTS_DIR.mkdir(exist_ok=True)

    instance, sol, M, index_mapping = io.load_all()
    nodes = extraction.build_nodes_df(instance, index_mapping)
    print(f"matrix {M.shape}, {len(nodes)} locations, "
          f"{len(instance['instance']['delivery_areas'])} delivery areas")
    return (
        M,
        config,
        extraction,
        instance,
        io,
        json,
        matrixtools,
        nodes,
        np,
        plt,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. The locations

    82 locations across 10 delivery areas around Bern (note the longitudes ~7.5–7.9:
    this is **not** Lausanne — any OSM graph used for comparison must cover this
    area). Locations can be hubs, depots, and customers at once; the pdptw project
    studies area **340070**.
    """)
    return


@app.cell
def _(config, nodes, np, plt):
    in_area = nodes['in_areas'].apply(lambda a: config.AREA_ID in a)
    area_nodes = nodes[in_area].reset_index(drop=True)
    print(f'area {config.AREA_ID}: {len(area_nodes)} locations, {area_nodes.is_hub.sum()} hub(s), {area_nodes.is_depot.sum()} depot flags')
    summary_locations = {
        'n_locations': len(nodes),
        'n_area_locations': len(area_nodes),
    }

    _fig, _ax = plt.subplots(figsize=(8, 7))
    _ax.scatter(nodes.lon[~in_area], nodes.lat[~in_area], c='lightgray', s=30, label='other areas')
    _ax.scatter(nodes.lon[in_area], nodes.lat[in_area], c='tab:blue', s=45, label=f'area {config.AREA_ID}')
    hubs = nodes[nodes.is_hub]
    _ax.scatter(hubs.lon, hubs.lat, marker='s', c='black', s=70, label='hubs')
    _ax.set_xlabel('longitude')
    _ax.set_ylabel('latitude')
    _ax.set_title('Swiss Post locations (Bern region)')
    _ax.legend()
    _ax.set_aspect(1 / np.cos(np.radians(nodes.lat.mean())))
    plt.tight_layout()
    _fig
    return (summary_locations,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. The travel-time matrix — trust, but verify

    The file name says nothing, and the demonstration notebook *asks itself* whether
    the values are meters or seconds. We answer empirically: for every pair, compute
    the great-circle (haversine) distance and look at the implied ratio
    `haversine / value`. Each unit hypothesis predicts a plausible range for that
    ratio (e.g. seconds → 3–20 m/s, an urban driving speed).
    """)
    return


@app.cell
def _(M, matrixtools, nodes):
    hav = matrixtools.haversine_matrix(nodes.lat.values, nodes.lon.values)
    sniff = matrixtools.sniff_units(M, hav)
    print(sniff.to_string(index=False))
    best = sniff.iloc[0]
    print(f"\n=> the matrix is almost certainly in {best.hypothesis.upper()} "
          f"(score {best.score:.1%}, median implied speed {best.median_ratio:.1f} m/s "
          f"= {best.median_ratio * 3.6:.0f} km/h)")
    summary_units = {
        "matrix_units": best.hypothesis,
        "median_implied_speed_kmh": best.median_ratio * 3.6,
    }
    return hav, summary_units


@app.cell
def _(M, hav, np, plt):
    # Implied speed vs distance: short legs are slow (city streets), long legs
    # approach main-road speeds — the signature of a real routing engine, not a
    # constant-speed approximation.
    mask = ~np.eye(len(M), dtype=bool) & (M > 0)
    _fig, _ax = plt.subplots(figsize=(7, 4.5))
    _ax.scatter(hav[mask] / 1000, hav[mask] / M[mask] * 3.6, s=4, alpha=0.25)
    _ax.set_xlabel('great-circle distance (km)')
    _ax.set_ylabel('implied speed (km/h)')
    _ax.set_title('Implied speed per OD pair (straight-line distance / travel time)')
    plt.tight_layout()
    _fig
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Structural properties
    """)
    return


@app.cell
def _(M, matrixtools, np):
    asym = matrixtools.asymmetry_stats(M)
    tri = matrixtools.triangle_violations(M)
    props = {
        "diagonal_all_zero": bool((np.diag(M) == 0).all()),
        "any_negative": bool((M < 0).any()),
        "any_missing": bool(np.isnan(M).any()),
        "max_seconds": float(M.max()),
        **{f"asymmetry_{k}": v for k, v in asym.items()},
        **{f"triangle_{k}": v for k, v in tri.items()},
    }
    for k, v in props.items():
        print(f"{k:35s} {v}")
    return (props,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Interpretation:

    - **Asymmetric but mildly** (mean ≈ 0.9%, isolated pairs up to ~70%): consistent
      with one-way streets and turn restrictions in a directed road network. A
      *perfectly symmetric* OSM matrix would therefore already deviate structurally.
    - **Triangle inequality virtually holds** (violations ≈ 0.02%, worst 127 s):
      the values are genuine shortest-path travel times, not schedule times or
      post-processed averages.
    - `uint16` storage caps values at 65535 s — irrelevant here (max ≈ 3600 s).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. The shipments

    Two kinds, extracted with the **corrected** extraction code
    (`sppdptw.extraction`, see notebook 05 for the bug quantification):
    - `hub`: parcel between the area hub and a customer (91% deliveries);
    - `transport`: parcel between two customers — the true pickup–delivery pairs.
    """)
    return


@app.cell
def _(extraction, instance, nodes, plt):
    ship = extraction.build_shipments_df(instance, nodes)
    print(ship.kind.value_counts().to_string())
    print(f'\ndates: {ship.date.min()} .. {ship.date.max()} ({ship.date.nunique()} unique)')
    summary_ship = {'n_shipments': len(ship)}
    per_day = ship.groupby('date').size()
    _fig, _ax = plt.subplots(figsize=(9, 3.5))
    per_day.plot(kind='bar', ax=_ax, width=0.9)
    _ax.set_title('shipments per day')
    _ax.set_xticks(_ax.get_xticks()[::5])
    plt.tight_layout()
    _fig
    return ship, summary_ship


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. Time windows: what the data says vs what the code assumed

    Two findings from reading the raw JSON against the extraction code in
    `pdptw_demonstration.ipynb`:

    **(a) The drop-off window bug.** The upstream code builds
    ```python
    drop_off_TW = (request['drop_off']['time_window']['start'],
                   request['drop_off']['time_window']['start'])   # 'start' twice!
    ```
    collapsing every transport drop-off window to zero width — the vehicle is
    forced to arrive at an *exact* minute. The data has real windows:
    """)
    return


@app.cell
def _(ship):
    tw_width = ship[ship.kind == "transport"].dropoff_tw.apply(lambda t: t[1] - t[0])
    print("real drop-off window widths (minutes):")
    print(tw_width.describe().round(1).to_string())
    n_zero = (tw_width == 0).sum()
    print(f"\nzero-width windows in the data: {n_zero} / {len(tw_width)}")
    print("=> upstream turns ALL of them into zero-width windows, then patches the")
    print("   degenerate cases it created with make_the_TW_feasible().")
    summary_dropoff = {"dropoff_tw_median_width_min": float(tw_width.median())}
    return (summary_dropoff,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    **(b) The default-window assumption.** Hub shipments almost never carry an
    explicit window; the upstream code substitutes `(420, 720)` = 07:00–12:00 while
    its own comment says *"let's assume we can go up to 5 PM"* (17:00 = 1020).
    Result: 99% of the shipments are constrained to mornings by an assumption, not
    by data.
    """)
    return


@app.cell
def _(instance):
    hs = instance["instance"]["hub_based_shipments"]
    n_explicit = sum(1 for r in hs if "time_window" in r["task"])
    print(f"hub shipments with an explicit time window: {n_explicit} / {len(hs)}")
    summary_hub_tw = {"hub_shipments_with_tw": n_explicit}
    return (summary_hub_tw,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 5. Service times: uniform 5 minutes vs the data

    The model assumes **5 minutes of service at every stop**. The instance carries a
    measured `visit_time` per location (its "realization"):
    """)
    return


@app.cell
def _(nodes, plt):
    vt = nodes.visit_time_s.dropna()
    print(vt.describe().round(0).to_string())
    summary_visit = {
        'visit_time_mean_s': float(vt.mean()),
        'visit_time_max_s': float(vt.max()),
    }
    _fig, _ax = plt.subplots(figsize=(7, 4))
    _ax.hist(vt / 60, bins=40)
    _ax.axvline(5, color='tab:red', ls='--', label='model assumption (5 min)')
    _ax.axvline(vt.mean() / 60, color='tab:green', ls='--', label=f'data mean ({vt.mean() / 60:.1f} min)')
    _ax.set_xlabel('visit time (minutes)')
    _ax.set_ylabel('locations')
    _ax.set_title('Per-location service time in the instance data')
    _ax.legend()
    plt.tight_layout()
    _fig
    return (summary_visit,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The distribution is extremely skewed (median well under 5 min, but a tail up to
    ~94 min — locations where many parcels are handled). A uniform 5 min is wrong in
    *both* directions depending on the tour composition; notebook 05 measures the
    net effect per tour.

    ## 6. Operational limits the model ignores

    The instance also specifies driver availability — which the pdptw model does not
    encode (it fixes the tour span to 07:00–17:00 instead):
    """)
    return


@app.cell
def _(extraction, instance, io):
    lims = extraction.get_driver_limits(instance)
    veh = io.get_area(instance)["vehicle_templates"][0]
    print(f"driver: start {lims['earliest_start_min'] / 60:.0f}h–"
          f"{lims['latest_start_min'] / 60:.0f}h, "
          f"max duration {lims['max_duration_min'] / 60:.0f}h, "
          f"break: {lims['break_type']}")
    print(f"vehicle capacities: weight={veh['capacities'][0]:,} volume={veh['capacities'][1]:,} "
          f"(labels: {instance['instance']['instance_parameters']['capacity_labels']})")
    summary_driver = {"driver_max_duration_min": lims["max_duration_min"]}
    return (summary_driver,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    A 6-hour driver limit with a mandatory 30-min break is a *much* tighter
    constraint than a 10-hour model day. Swiss Post's plans must respect it; a model
    that doesn't will happily build longer tours — another divergence source that
    has nothing to do with the OD matrix.
    """)
    return


@app.cell
def _(
    config,
    json,
    props,
    summary_dropoff,
    summary_driver,
    summary_hub_tw,
    summary_locations,
    summary_ship,
    summary_units,
    summary_visit,
):
    summary = {
        **summary_locations,
        **summary_units,
        **props,
        **summary_ship,
        **summary_dropoff,
        **summary_hub_tw,
        **summary_visit,
        **summary_driver,
    }
    with open(config.OUTPUTS_DIR / "summary_characterization.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("summary written:")
    print(json.dumps(summary, indent=2))
    return


if __name__ == "__main__":
    app.run()
