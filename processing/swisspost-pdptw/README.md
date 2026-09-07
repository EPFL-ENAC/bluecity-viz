# Swiss Post PDPTW — diagnostic notebooks

Why do our routing results (PDPTW / Gurobi, from [EPFL-ENAC/pdptw](https://github.com/EPFL-ENAC/pdptw))
diverge from Swiss Post's values? These notebooks explain the methodology and decompose the divergence
into three independently measurable parts:

1. **Matrix gap** — an OSM-derived travel-time matrix vs Swiss Post's provided matrix
   (uniform multiplicative shift vs structural error)
2. **Modeling gap** — differences between the pdptw model's assumptions and the Swiss Post
   instance (time-window extraction, service times, defaults)
3. **Solver gap** — Gurobi optimality gap / heuristic noise

A key fact established in notebook 03: **Swiss Post's "empirical" tour values are their own solver
running on their own matrix** (every driving leg in the solution JSON matches the npz matrix exactly).
They are not GPS-measured reality, so a clean decomposition of the divergence is possible.

## Notebooks (read in order)

| # | Notebook | Question it answers |
|---|----------|---------------------|
| 00 | `00_executive_summary` | **Client-facing summary**: the whole story in one document, computed live, with "how to read this" notes. Export it with `make export` → `outputs/executive_summary.html` (single self-contained file, no code shown). |
| 01 | `01_pdptw_methodology` | How does the PDPTW model work, mathematically and in code? What does the solver guarantee? |
| 02 | `02_data_characterization` | What exactly is in the Swiss Post data? What units/properties does the matrix have? What do the extraction assumptions/bugs change? |
| 03 | `03_swisspost_solution_analysis` | What are Swiss Post's benchmark values, precisely? (tour decomposition: drive + service + wait) |
| 04 | `04_od_matrix_comparison` | Is the OSM↔SwissPost matrix gap a uniform factor k, or structural? |
| 05 | `05_model_faithfulness` | How much of the tour-level gap does each modeling difference explain? Final verdict. |

The notebooks are [marimo](https://marimo.io) notebooks — pure Python files (clean git diffs,
no hidden state, reactive execution). The config inputs (e.g. the OSM matrix path in
notebook 04) are interactive UI elements.

## Setup

```bash
uv sync
make edit NB=01      # open a notebook in the marimo editor
make run-all         # execute all notebooks top-to-bottom as scripts
make check           # validate marimo format / dataflow
make export          # render the executive summary to outputs/executive_summary.html
```

Note on reactivity: notebook 04's first run downloads the Bern OSM graph (minutes) and
notebook 05 runs ~28 PyVRP solves (~90 s) — both are disk-cached (`data/cache/`,
`notebooks/__marimo__/`), so re-runs and reactive updates are instant.

The notebooks read the data directly from `../../SWISS POST DATA/DATA/` (checked into this repo).
The Bern-area OSM graph used by notebook 04 is downloaded once (network required) and cached in
`data/cache/`. If you already have your own OSM travel-time matrix, point `OSM_MATRIX_PATH` in
notebook 04's config cell at it (long or wide CSV, or `.npy` ordered like `03-index_mapping.parquet`).

## Findings encoded in these notebooks (discovered while building them)

Bugs/assumptions in the upstream [EPFL-ENAC/pdptw](https://github.com/EPFL-ENAC/pdptw) extraction code,
each quantified in notebook 05:

1. **Drop-off time windows collapsed to zero width** — `pdptw_demonstration.ipynb` builds
   `drop_off_TW = (start, start)` instead of `(start, end)`; all 128 transport shipments actually
   have distinct start/end (e.g. 08:00–08:30). `make_the_TW_feasible()` then patches the degenerate
   windows the bug itself created.
2. **`apply_TW_per_date()` discards the pickup-window fix** — its second call is applied to `df_day`
   instead of the result of the first call.
3. **Uniform 5-minute service time** — the instance JSON carries per-location `visit_time`
   (0–5647 s, mean ≈ 4 min); using the real values changes tour durations materially.
4. **Default time window (420, 720)** for the 632/636 hub shipments without an explicit window —
   the code comment says "up to 5 PM" but 720 min = noon (5 PM = 1020).
