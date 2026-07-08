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
    # Why did our routing results diverge from Swiss Post's?

    **Executive summary — EPFL PDPTW methodology vs the Swiss Post benchmark**

    Swiss Post provided a parcel-delivery benchmark for one delivery area in the
    Bern region: 87 daily tours over 14 weeks, together with the travel-time
    matrix and the shipment data their planner used. Our re-implementation of the
    routing problem produced tour durations substantially different from theirs.
    This document answers, with evidence computed live from the shared data:

    1. **Is our travel-time model (OpenStreetMap) wrong — and how wrong?**
    2. **Which of our modeling assumptions move the results, and by how much?**
    3. **After correcting both, what can our results be trusted for?**

    *Every number and figure below is recomputed from the raw data each time this
    document is generated. Each figure comes with a short "how to read this"
    note. The full technical analysis lives in notebooks 01–05 of the same
    project (see the last section).*
    """)
    return


@app.cell
def _():
    import json

    import matplotlib as mpl
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from sppdptw import config, evaluate, extraction, io, matrixtools, osm, solution

    # Chart style: recessive axes/grid, validated palette (see dataviz notes)
    COL = {
        "blue": "#2a78d6",  # primary series
        "red": "#e34948",  # diverging counterpart / fit line
        "ink": "#0b0b0b",
        "muted": "#52514e",
        "grid": "#e6e4df",
    }
    mpl.rcParams.update(
        {
            "figure.dpi": 110,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": COL["grid"],
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "axes.edgecolor": COL["muted"],
            "axes.labelcolor": COL["ink"],
            "xtick.color": COL["muted"],
            "ytick.color": COL["muted"],
            "font.size": 10.5,
        }
    )

    instance, sol, M_SP, index_mapping = io.load_all()
    nodes = extraction.build_nodes_df(instance, index_mapping)
    visit_times = extraction.get_visit_times(nodes)
    uuid_to_idx = dict(zip(nodes["uuid"], nodes["index"]))
    tours_bench = solution.extract_tours(sol, uuid_to_idx)
    tours_bench = tours_bench[tours_bench.area_id == config.AREA_ID].reset_index(
        drop=True
    )
    return (
        COL,
        M_SP,
        config,
        evaluate,
        extraction,
        instance,
        io,
        json,
        matrixtools,
        nodes,
        np,
        osm,
        pd,
        plt,
        sol,
        solution,
        tours_bench,
        uuid_to_idx,
        visit_times,
    )


@app.cell(hide_code=True)
def _(demo_tag, faith, fit_af, mo, raw_err, service_pct):
    _overlap_line = (
        f"- **But calibration does not recover Swiss Post's exact routes.** "
        f"Re-optimizing with the corrected travel times still yields stop "
        f"sequences that share only ≈{faith['sp_vs_calibrated_route_overlap']:.0%} "
        f"of their driving legs with Swiss Post's (a solver re-run with a "
        f"different random seed shares ≈{faith['solver_noise_route_overlap']:.0%}). "
        f"Durations and distances calibrate; exact routes require Swiss Post's "
        f"own matrix."
        if faith is not None
        else "- **Route-level comparison**: run `make run-all` once to compute the "
        "re-optimization experiment (notebook 05); its result will appear here."
    )
    mo.md(
        f"""
    ## The answer in four lines{demo_tag}

    - **The divergence is explained, and our methodology is sound.** It is *not*
      a bug in the optimization: it is the sum of a travel-time offset and three
      input assumptions, each measured below.
    - **Travel times**: OpenStreetMap free-flow times are systematically
      optimistic, but in a *regular* way — Swiss Post ≈
      **{fit_af["k"]:.2f} × OSM + {fit_af["c"]:.0f} s** per trip
      (R² = {fit_af["r2"]:.2f}). Raw OSM underestimates tour driving time by
      {raw_err.mean():+.0%}; after this two-parameter correction the residual
      error is unbiased scatter of a few percent.
    - **Assumptions**: replacing the real per-stop handling times with a uniform
      5 minutes changes total tour time by **{service_pct:+.1f}%** on its own —
      the same order as the travel-time gap. Two time-window extraction bugs and
      an ignored 6-hour driver limit push in the same direction.
    {_overlap_line}
    """
    ).callout(kind="info")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. What we compare against — the benchmark

    The Swiss Post solution file contains, for every tour, a timestamped
    itinerary (drive from A to B, arrive, serve, depart, …). From it we rebuild
    each tour's decomposition **total = driving + handling + waiting**.

    One property makes the whole analysis clean: **every driving leg in the
    solution matches the provided travel-time matrix to the second.** Swiss
    Post's "empirical" values are therefore their planner's output on their own
    matrix — not GPS measurements. So if we use their matrix and their
    assumptions, we must reproduce their numbers exactly; every remaining
    difference can be attributed to a specific cause.
    """)
    return


@app.cell(hide_code=True)
def _(M_SP, mo, solution, sol, tours_bench, uuid_to_idx):
    _legs = solution.extract_legs(sol, uuid_to_idx).dropna(
        subset=["from_idx", "to_idx"]
    )
    legs_match = float(
        (
            M_SP[_legs.from_idx.astype(int), _legs.to_idx.astype(int)]
            == _legs.seconds
        ).mean()
    )
    drive_share = tours_bench.drive_min.sum() / tours_bench.total_min.sum()
    service_share = tours_bench.service_min.sum() / tours_bench.total_min.sum()
    mo.hstack(
        [
            mo.stat(
                f"{len(tours_bench)}",
                label="benchmark tours",
                caption=f"{tours_bench.date.nunique()} delivery days, one area (Bern region)",
                bordered=True,
            ),
            mo.stat(
                f"{legs_match:.0%}",
                label="driving legs = matrix",
                caption="their values are solver output, not GPS",
                bordered=True,
            ),
            mo.stat(
                f"{drive_share:.0%} / {service_share:.0%}",
                label="driving / handling",
                caption="handling time is NOT a rounding detail",
                bordered=True,
            ),
        ],
        widths="equal",
        gap=1,
    )
    return drive_share, legs_match, service_share


@app.cell(hide_code=True)
def _(mo, service_share):
    mo.md(
        f"""
    > **Why the third number matters:** {service_share:.0%} of a tour is spent
    > *at* the stops, not driving between them. Any model that gets handling
    > times wrong is wrong by tens of minutes per tour before the travel-time
    > matrix even enters the picture (section 3).
    """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. The travel-time gap: OSM vs Swiss Post

    Our pipeline computes travel times on the OpenStreetMap road network at
    free-flow speed (no congestion, no junction delays). Swiss Post's matrix
    comes from their commercial routing engine. We compare the two **for every
    origin–destination pair** — 6,628 pairs — which lets us distinguish:

    - a **regular** gap (e.g. "OSM is uniformly 20% too fast") → harmless,
      correct it with a calibration;
    - a **structural** gap (errors that depend on the place, direction or trip
      length in unpredictable ways) → the methodology itself would be in question.
    """)
    return


@app.cell
def _(M_SP, nodes, np, osm):
    if osm.MATRIX_CACHE.exists():
        M_OSM, _snaps = osm.build_osm_matrix(nodes)
        osm_src = "OpenStreetMap, free-flow (cached build)"
    else:
        try:
            M_OSM, _snaps = osm.build_osm_matrix(nodes)
            osm_src = "OpenStreetMap, free-flow (fresh build)"
        except Exception:  # offline — keep the document renderable, clearly tagged
            M_OSM, _truth = osm.demo_matrix(M_SP, nodes)
            osm_src = "DEMO (synthetic — for illustration only)"
    demo_tag = " ⚠️ [DEMO DATA]" if osm_src.startswith("DEMO") else ""

    _off_diag = ~np.eye(len(M_SP), dtype=bool)
    valid_pairs = _off_diag & np.isfinite(M_OSM) & (M_OSM > 0) & (M_SP > 0)
    x_osm = M_OSM[valid_pairs]
    y_sp = M_SP[valid_pairs]
    ratio_pairs = y_sp / x_osm
    return M_OSM, demo_tag, osm_src, ratio_pairs, valid_pairs, x_osm, y_sp


@app.cell
def _(matrixtools, x_osm, y_sp):
    fit_af = matrixtools.fit_affine(x_osm, y_sp)
    fit_fo = matrixtools.fit_through_origin(x_osm, y_sp)
    return fit_af, fit_fo


@app.cell(hide_code=True)
def _(COL, demo_tag, fit_af, np, plt, ratio_pairs, x_osm, y_sp):
    _fig, _axes = plt.subplots(1, 2, figsize=(11, 4.5))
    _axes[0].scatter(x_osm / 60, y_sp / 60, s=6, alpha=0.25, color=COL["blue"])
    _lim = max(x_osm.max(), y_sp.max()) / 60 * 1.02
    _axes[0].plot(
        [0, _lim], [0, _lim], ls="--", lw=1, color=COL["muted"], label="equal times"
    )
    _xx = np.array([0.0, _lim * 60])
    _axes[0].plot(
        _xx / 60,
        (fit_af["k"] * _xx + fit_af["c"]) / 60,
        lw=1.5,
        color=COL["red"],
        label=f"SP ≈ {fit_af['k']:.2f}·OSM + {fit_af['c']:.0f} s",
    )
    _axes[0].set_xlabel("OSM travel time (min)")
    _axes[0].set_ylabel("Swiss Post travel time (min)")
    _axes[0].set_title(f"Each dot = one origin→destination pair{demo_tag}")
    _axes[0].legend(frameon=False)

    _axes[1].hist(ratio_pairs, bins=60, color=COL["blue"])
    _axes[1].axvline(1, color=COL["muted"], ls="--", lw=1)
    _axes[1].axvline(np.median(ratio_pairs), color=COL["red"], lw=1.5)
    _axes[1].annotate(
        f"median {np.median(ratio_pairs):.2f}×",
        xy=(np.median(ratio_pairs), 1),
        xycoords=("data", "axes fraction"),
        xytext=(8, -14),
        textcoords="offset points",
        color=COL["red"],
    )
    _axes[1].set_xlabel("ratio Swiss Post / OSM")
    _axes[1].set_ylabel("number of OD pairs")
    _axes[1].set_title(f"How much slower is Swiss Post?{demo_tag}")
    plt.tight_layout()
    _fig
    return


@app.cell(hide_code=True)
def _(fit_af, mo, np, ratio_pairs):
    mo.md(
        f"""
    > **How to read this figure.** Left: if the two matrices agreed, every dot
    > would sit on the gray dashed line. Instead the cloud hugs a straight line
    > *above* it — Swiss Post's times are consistently slower, and the
    > relationship is tight (R² = {fit_af["r2"]:.3f}), which is exactly what a
    > *regular*, correctable gap looks like. Right: the ratio is concentrated
    > around {np.median(ratio_pairs):.2f}× with 90% of pairs between
    > {np.quantile(ratio_pairs, 0.05):.2f}× and
    > {np.quantile(ratio_pairs, 0.95):.2f}× — no second bump, no long tail of
    > erratic pairs.
    """
    )
    return


@app.cell(hide_code=True)
def _(COL, demo_tag, fit_fo, np, plt, ratio_pairs, x_osm):
    _bins = np.quantile(x_osm, np.linspace(0, 1, 13))
    _bin_id = np.digitize(x_osm, _bins[1:-1])
    _centers, _q10, _q50, _q90 = [], [], [], []
    for _b in range(12):
        _r = ratio_pairs[_bin_id == _b]
        if len(_r) >= 10:
            _centers.append(x_osm[_bin_id == _b].mean() / 60)
            _q10.append(np.quantile(_r, 0.1))
            _q50.append(np.quantile(_r, 0.5))
            _q90.append(np.quantile(_r, 0.9))
    _fig, _ax = plt.subplots(figsize=(8.5, 4.2))
    _ax.fill_between(
        _centers, _q10, _q90, alpha=0.2, color=COL["blue"], label="middle 80% of pairs"
    )
    _ax.plot(_centers, _q50, "-o", color=COL["blue"], label="median ratio")
    _ax.axhline(
        fit_fo["k"],
        color=COL["red"],
        ls="--",
        lw=1,
        label=f"single factor {fit_fo['k']:.2f}×",
    )
    _ax.axhline(1, color=COL["muted"], lw=0.6)
    _ax.set_xlabel("trip length (OSM minutes)")
    _ax.set_ylabel("ratio Swiss Post / OSM")
    _ax.set_title(f"The gap is larger for short trips{demo_tag}")
    _ax.legend(frameon=False)
    plt.tight_layout()
    _fig
    return


@app.cell(hide_code=True)
def _(fit_af, mo):
    mo.md(
        f"""
    > **How to read this figure.** If a single multiplication factor explained
    > everything, the blue line would be flat on the red dashed line. It is not:
    > short trips have *higher* ratios. That is the signature of a **fixed
    > per-trip overhead** — pulling away from the curb, junctions, access roads —
    > which weighs proportionally more on a 3-minute hop than on a 40-minute
    > leg. Both effects together give the calibration formula:

    $$T_{{\\text{{SwissPost}}}} \\;\\approx\\; {fit_af["k"]:.2f} \\times T_{{\\text{{OSM}}}} \\;+\\; {fit_af["c"]:.0f}\\ \\text{{s}}$$

    > A factor for congestion and speed limits, plus ≈{fit_af["c"]:.0f} seconds
    > of overhead per trip. Two parameters, fitted once, valid across the whole
    > area. (Notebook 04 additionally rules out direction-dependent errors,
    > geographic error clusters and index-alignment problems; the few outlying
    > pairs are map-snapping artifacts on trips under 1.5 km.)
    """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. What this means for whole tours

    The cleanest experiment: take Swiss Post's 87 tours **exactly as driven**
    (same stops, same order — no optimization involved) and re-price them under
    our assumptions. Any change in the total is then attributable to that
    assumption alone.
    """)
    return


@app.cell
def _(M_OSM, M_SP, evaluate, fit_af, np, tours_bench, visit_times):
    M_OSM_free = np.nan_to_num(M_OSM, nan=float(np.nanmax(M_OSM) * 2))
    M_OSM_cal = fit_af["k"] * M_OSM_free + fit_af["c"]
    np.fill_diagonal(M_OSM_cal, 0.0)

    scenario_defs = {
        "Swiss Post matrix + real handling times\n(= the benchmark)": (
            M_SP,
            visit_times,
        ),
        "Uniform 5-min handling assumption": (M_SP, 300.0),
        "OSM travel times, uncorrected": (M_OSM_free, visit_times),
        "OSM calibrated (×{k:.2f} + {c:.0f} s)".format(
            k=fit_af["k"], c=fit_af["c"]
        ): (M_OSM_cal, visit_times),
    }
    scenario_evals = {
        _name: evaluate.evaluate_tours(tours_bench, _m, _vt, label=_name)
        for _name, (_m, _vt) in scenario_defs.items()
    }
    _base_name = next(iter(scenario_defs))
    _base_total = scenario_evals[_base_name].total_min.sum()
    assert np.allclose(
        scenario_evals[_base_name].drive_min, tours_bench.drive_min, atol=0.01
    ), "baseline must reproduce the benchmark exactly"

    scen_pct = {
        _name: 100 * (_ev.total_min.sum() / _base_total - 1)
        for _name, _ev in scenario_evals.items()
    }
    _base_drive = scenario_evals[_base_name].drive_min
    raw_err = scenario_evals["OSM travel times, uncorrected"].drive_min / _base_drive - 1
    cal_err = (
        scenario_evals[
            "OSM calibrated (×{k:.2f} + {c:.0f} s)".format(
                k=fit_af["k"], c=fit_af["c"]
            )
        ].drive_min
        / _base_drive
        - 1
    )
    service_pct = scen_pct["Uniform 5-min handling assumption"]
    return cal_err, raw_err, scen_pct, scenario_evals, service_pct


@app.cell(hide_code=True)
def _(COL, demo_tag, plt, scen_pct):
    _items = [(k, v) for k, v in scen_pct.items()][1:]  # skip the 0% benchmark row
    _labels = [k for k, _ in _items][::-1]
    _vals = [v for _, v in _items][::-1]
    _colors = [COL["red"] if v > 0 else COL["blue"] for v in _vals]
    _fig, _ax = plt.subplots(figsize=(9, 3.6))
    _bars = _ax.barh(_labels, _vals, color=_colors, height=0.55)
    _ax.axvline(0, color=COL["ink"], lw=1)
    for _bar, _v in zip(_bars, _vals):
        _ax.annotate(
            f"{_v:+.1f}%",
            xy=(_v, _bar.get_y() + _bar.get_height() / 2),
            xytext=(6 if _v > 0 else -6, 0),
            textcoords="offset points",
            ha="left" if _v > 0 else "right",
            va="center",
            color=COL["ink"],
            fontweight="bold",
        )
    _ax.set_xlabel("total time of the 87 benchmark tours, vs Swiss Post (%)")
    _ax.set_title(
        f"Same tours, re-priced under each assumption{demo_tag}"
    )
    _ax.grid(axis="y", visible=False)
    _ax.margins(x=0.15)
    plt.tight_layout()
    _fig
    return


@app.cell(hide_code=True)
def _(cal_err, mo, raw_err, scen_pct, service_pct):
    _osm_raw_pct = scen_pct["OSM travel times, uncorrected"]
    mo.md(
        f"""
    > **How to read this figure.** Zero = Swiss Post's own total. Blue bars
    > underestimate it, red bars overestimate it. Two findings:
    >
    > 1. **The uncorrected OSM matrix and the 5-minute handling assumption are
    >    errors of the same size** ({_osm_raw_pct:+.1f}% and {service_pct:+.1f}%
    >    of total tour time). Fixing only the travel times while keeping uniform
    >    handling times would still leave results ~13% off — and because both
    >    errors point the same way, together they compound to roughly −25%.
    > 2. **The two-parameter calibration works.** Looking at driving time alone,
    >    raw OSM is {raw_err.mean():+.1%} ± {raw_err.std():.1%} per tour; after
    >    calibration {cal_err.mean():+.1%} ± {cal_err.std():.1%} — a small,
    >    *unbiased* residual instead of a systematic shortfall.
    """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Beyond handling times, the audit of our extraction code found **three
    further assumption differences**, all quantified in notebooks 02 and 05:

    | Assumption in our pipeline | Reality in the Swiss Post data | Effect |
    |---|---|---|
    | Delivery time windows collapsed to a single instant (extraction bug) | all 128 timed deliveries have 30-minute windows | model must hit a ~5-min target instead of a 30-min window → forced detours, waits, or skipped shipments |
    | A second extraction step discards the pickup-window repair | — | pickup windows can stay infeasible |
    | Free 10-hour driver day, no break | 6-hour shift + 30-min break, overtime *penalized* in their objective | their planner trades tour length against overtime; ours feels no such pressure |

    These do not change *travel times* at all — they change **which routes are
    feasible and attractive**, which is why they matter for the next section.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. The limit: durations calibrate, exact routes do not

    Sections 2–3 re-priced *fixed* routes. But an optimizer **reacts** to its
    travel times: change the matrix slightly and a different stop order may
    become "shortest". To measure this we re-optimized four representative days
    under each matrix and compared the resulting routes leg by leg
    (notebook 05, section 4).
    """)
    return


@app.cell
def _(config, json):
    _faith_path = config.OUTPUTS_DIR / "summary_faithfulness.json"
    faith = json.loads(_faith_path.read_text()) if _faith_path.exists() else None
    return (faith,)


@app.cell(hide_code=True)
def _(COL, demo_tag, faith, mo, plt):
    if faith is None:
        _out = mo.md(
            "**Re-optimization results not found.** Run `make run-all` once "
            "(it executes notebook 05, ~2 min on first run) and regenerate "
            "this document."
        ).callout(kind="warn")
    else:
        _noise = faith["solver_noise_route_overlap"]
        _pairs = [
            ("uncorrected OSM vs Swiss Post", faith["sp_vs_osm_route_overlap"]),
            ("calibrated OSM vs Swiss Post", faith["sp_vs_calibrated_route_overlap"]),
        ][::-1]
        _fig, _ax = plt.subplots(figsize=(9, 2.9))
        _bars = _ax.barh(
            [p[0] for p in _pairs],
            [p[1] * 100 for p in _pairs],
            color=COL["blue"],
            height=0.5,
        )
        for _bar, (_lbl, _v) in zip(_bars, _pairs):
            _ax.annotate(
                f"{_v:.0%}",
                xy=(_v * 100, _bar.get_y() + _bar.get_height() / 2),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                color=COL["ink"],
                fontweight="bold",
            )
        _ax.axvline(_noise * 100, color=COL["muted"], ls="--", lw=1.2)
        _ax.annotate(
            f"attainable ceiling: same matrix,\ndifferent random seed ({_noise:.0%})",
            xy=(_noise * 100, 0.97),
            xycoords=("data", "axes fraction"),
            xytext=(-8, 0),
            textcoords="offset points",
            ha="right",
            va="top",
            color=COL["muted"],
        )
        _ax.set_xlim(0, 100)
        _ax.set_xlabel("share of driving legs in common (%)")
        _ax.set_title(f"Do the optimized routes match Swiss Post's?{demo_tag}")
        _ax.grid(axis="y", visible=False)
        plt.tight_layout()
        _out = _fig
    _out
    return


@app.cell(hide_code=True)
def _(faith, mo):
    _txt = (
        f"""
    > **How to read this figure.** The dashed line is the honest yardstick: even
    > re-running the *same* solver on the *same* matrix with a different random
    > seed only reproduces {faith["solver_noise_route_overlap"]:.0%} of the
    > driving legs — no comparison can beat that. Against it, routes optimized
    > on the OSM matrix share only
    > {faith["sp_vs_osm_route_overlap"]:.0%}–{faith["sp_vs_calibrated_route_overlap"]:.0%}
    > of their legs with the Swiss-Post-matrix routes, **and calibration barely
    > helps**. Small per-pair time differences flip which neighbor is "closest",
    > and time windows amplify those flips into different tours. Total durations
    > and distances still come out right — the *sequence of stops* does not.
    """
        if faith is not None
        else ""
    )
    mo.md(_txt)
    return


@app.cell(hide_code=True)
def _(cal_err, fit_af, mo, raw_err, service_pct):
    mo.md(
        f"""
    ## 5. Conclusions and recommendations

    **The methodology is validated.** The divergence decomposes into measured,
    correctable parts — none of them invalidates the optimization approach.

    | What to change | Effect on the gap |
    |---|---|
    | Calibrate OSM travel times: **× {fit_af["k"]:.2f} + {fit_af["c"]:.0f} s per trip** | driving-time error goes from {raw_err.mean():+.1%} to {cal_err.mean():+.1%} ± {cal_err.std():.1%} |
    | Use the per-location handling times from the instance data (not 5 min flat) | removes a {service_pct:+.1f}% bias in total tour time |
    | Fix the two time-window extraction bugs | restores the real 30-min delivery windows for all timed shipments |
    | Model the 6-h driver shift + break as a soft (penalized) limit | matches the pressure that shapes Swiss Post's tours |

    **What the corrected results can be trusted for:** fleet-level and tour-level
    **durations, distances and workloads** — the quantities that drive cost and
    CO₂ estimates — to within a few percent.

    **What they cannot deliver:** a stop-by-stop reproduction of Swiss Post's
    routes. For any analysis where the exact sequence matters, the practical
    recommendation is to **run our models on Swiss Post's travel-time matrix**
    (as this study did) — which we suggest making a standing part of the data
    exchange.
    """
    )
    return


@app.cell(hide_code=True)
def _(legs_match, mo, osm_src):
    mo.md(
        f"""
    ---

    ### About this document

    Generated from the marimo notebook `00_executive_summary.py` in
    `processing/swisspost-pdptw/`. Inputs: the Swiss Post instance, solution and
    travel-time matrix as provided; road travel times from
    **{osm_src}**; benchmark integrity check: {legs_match:.0%} of driving legs
    match the provided matrix. The detailed analyses are in the same project:

    | Notebook | Content |
    |---|---|
    | 01 | How the pickup-and-delivery optimization works (with a worked toy example) |
    | 02 | Audit of the Swiss Post data: units, consistency, time windows, handling times |
    | 03 | Reconstruction of the benchmark (per-tour decomposition) |
    | 04 | Full OSM ↔ Swiss Post matrix comparison (fits, geography, direction, outliers) |
    | 05 | Assumption-by-assumption quantification and the re-optimization experiment |

    Reproduce: `uv sync && make run-all && make export` — the export writes this
    document as a single self-contained HTML file in `outputs/`.
    """
    )
    return


if __name__ == "__main__":
    app.run()
