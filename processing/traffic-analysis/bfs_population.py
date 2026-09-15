#!/usr/bin/env python3
"""Residents and jobs per hectare, from the federal statistics.

Two files of the Federal Statistical Office (BFS), published on the geoportal
of the Confederation, one row per inhabited hectare:

- STATPOP, the residents (column BBTOT, B22BTOT in the older files)
- STATENT, the jobs in full-time equivalents (B08VZAT, or the head count
  B08EMPT when the first one is missing)

    uv run python bfs_population.py --dest .data/bfs     # download both CSVs

The graph builders snap each hectare to its nearest road node, see
snap_hectares in backend/app/services/graph_store_writer.py. The counts stay
raw: a hectare with "3" residents means 1 to 3 (the BFS rounds small counts up
to 3 for privacy), and it is kept as 3.

Two layouts exist. Since 2024 the columns lose their year prefix for STATPOP
and the files carry ERHJAHR (the survey year) and NOLOC. A NOLOC row holds the
people or jobs with no known building, piled on one hectare per commune. It is
not a real place, so it is dropped: it would make a fake dense node in every
commune.
"""

import argparse
from pathlib import Path

import pandas as pd
import requests

GEOPORTAL = "https://data.geo.admin.ch"
# The newest releases on data.geo.admin.ch (September 2026). A newer year only
# needs these two lines changed.
STATPOP_URL = (
    f"{GEOPORTAL}/ch.bfs.statistik-bevoelkerung_haushalte/"
    "statistik-bevoelkerung_haushalte_2025/statistik-bevoelkerung_haushalte_2025_ha_2056.csv"
)
STATENT_URL = (
    f"{GEOPORTAL}/ch.bfs.betriebszaehlungen/"
    "betriebszaehlungen_2024/betriebszaehlungen_2024_ha_2056.csv"
)

# Value columns, first match wins.
RESIDENT_COLUMNS = ["BBTOT", "B22BTOT"]
JOB_COLUMNS = ["VZAT", "B08VZAT", "EMPT", "B08EMPT"]

# Every hectare is a 100 m square, E_KOORD / N_KOORD is its south-west corner.
HALF_HECTARE_M = 50


def download(url: str, dest_dir: Path) -> Path:
    """Download one CSV into dest_dir, or keep the one already there."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / url.rsplit("/", 1)[-1]
    if path.exists() and path.stat().st_size > 0:
        print(f"  {path.name} already there")
        return path

    part = path.with_suffix(path.suffix + ".part")
    with requests.get(url, stream=True, timeout=60) as answer:
        answer.raise_for_status()
        with open(part, "wb") as out:
            for chunk in answer.iter_content(chunk_size=1 << 20):
                out.write(chunk)
    part.rename(path)
    print(f"  {path.name}, {path.stat().st_size / 1e6:.0f} MB")
    return path


def read_hectares(csv: Path, value_candidates: list) -> pd.DataFrame:
    """One value per hectare: RELI, E_KOORD, N_KOORD, value.

    Reads the header first to pick the value column, then only the columns it
    needs (the files have about a hundred).
    """
    header = pd.read_csv(csv, sep=";", nrows=0).columns
    value = next((c for c in value_candidates if c in header), None)
    if value is None:
        raise ValueError(f"{csv}: none of {value_candidates} in the header")
    extra = [c for c in ("ERHJAHR", "NOLOC") if c in header]

    table = pd.read_csv(csv, sep=";", usecols=["RELI", "E_KOORD", "N_KOORD", value, *extra])
    if "NOLOC" in table:
        noloc = table["NOLOC"] == 1
        print(f"  {csv.name}: dropped {int(noloc.sum()):,} NOLOC rows")
        table = table[~noloc]
    if "ERHJAHR" in table:
        # A hectare can come back for several survey years, keep the latest.
        table = table.sort_values("ERHJAHR").drop_duplicates("RELI", keep="last")

    print(f"  {csv.name}: {len(table):,} hectares, column {value}")
    table = table.rename(columns={value: "value"})
    return table[["RELI", "E_KOORD", "N_KOORD", "value"]]


def load_hectares(statpop_csv: Path, statent_csv: Path) -> pd.DataFrame:
    """Residents and jobs on the same hectares: e, n (centre, LV95), residents, jobs_fte.

    A hectare with people and no job (or the other way) keeps a 0 for the
    missing one.
    """
    people = read_hectares(Path(statpop_csv), RESIDENT_COLUMNS)
    jobs = read_hectares(Path(statent_csv), JOB_COLUMNS)

    both = people.merge(
        jobs, on=["RELI", "E_KOORD", "N_KOORD"], how="outer", suffixes=("_res", "_jobs")
    ).fillna({"value_res": 0, "value_jobs": 0})
    hectares = pd.DataFrame(
        {
            "e": both["E_KOORD"].to_numpy(dtype="float64") + HALF_HECTARE_M,
            "n": both["N_KOORD"].to_numpy(dtype="float64") + HALF_HECTARE_M,
            "residents": both["value_res"].to_numpy(dtype="float64"),
            "jobs_fte": both["value_jobs"].to_numpy(dtype="float64"),
        }
    )
    # A wrong column shows at once here: Switzerland has about 9 M residents
    # and about 4.5 M full-time jobs.
    print(
        f"  {len(hectares):,} hectares, {hectares['residents'].sum() / 1e6:.2f} M residents, "
        f"{hectares['jobs_fte'].sum() / 1e6:.2f} M full-time jobs"
    )
    return hectares


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", default=".data/bfs", help="where the CSVs go")
    parser.add_argument("--statpop-url", default=STATPOP_URL)
    parser.add_argument("--statent-url", default=STATENT_URL)
    args = parser.parse_args()

    print("Downloading the federal hectare statistics ...")
    statpop = download(args.statpop_url, Path(args.dest))
    statent = download(args.statent_url, Path(args.dest))
    load_hectares(statpop, statent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
