#!/usr/bin/env python3
"""Download the elevation rasters for the whole country.

Same idea as download_elevation_data.py, which does Lausanne. swisstopo has no
single national GeoTIFF to fetch, its download page hands you a CSV of tile
URLs instead, so this reads that CSV.

How to get the CSV:

  1. open https://www.swisstopo.admin.ch/en/height-model-dhm25
  2. pick the whole of Switzerland, format GeoTIFF, then "Export list of links"
  3. save it as list_raster_elevation_switzerland.csv next to this script

DHM25 is a 25 m model, which is plenty here: the CO2 model reads the slope of
a street, not the shape of a field. swissALTI3D is 0.5 m and hundreds of GB,
we do not need it outside Lausanne.

    uv run python download_swiss_dem.py
    uv run python download_swiss_dem.py --csv my_links.csv --output data/dem-ch
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

DEFAULT_CSV = "list_raster_elevation_switzerland.csv"
DEFAULT_OUTPUT = Path("data/elevation-ch")
MAX_WORKERS = 4
TIMEOUT = 120


def download(url: str, output: Path) -> tuple:
    """Fetch one tile. Already there means nothing to do."""
    if output.exists() and output.stat().st_size > 0:
        return (output.name, True, f"already there ({output.stat().st_size / 1e6:.1f} MB)")
    try:
        response = requests.get(url, timeout=TIMEOUT, stream=True)
        response.raise_for_status()
        partial = output.with_suffix(output.suffix + ".part")
        with open(partial, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 16):
                handle.write(chunk)
        partial.rename(output)
        return (output.name, True, f"downloaded ({output.stat().st_size / 1e6:.1f} MB)")
    except Exception as error:
        return (output.name, False, f"failed: {error}")


def urls_from_csv(path: Path) -> list:
    """The CSV swisstopo exports has one URL per line, with or without a header."""
    frame = pd.read_csv(path, header=None, names=["url"])
    urls = [str(value).strip() for value in frame["url"] if str(value).startswith("http")]
    if not urls:
        raise SystemExit(f"no URL found in {path}")
    return urls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=DEFAULT_CSV, help="CSV of tile URLs from swisstopo")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="where to put the tiles")
    args = parser.parse_args()

    csv = Path(args.csv)
    if not csv.exists():
        raise SystemExit(f"{csv} not found. Read the top of this file for how to get it.")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    urls = urls_from_csv(csv)
    print(f"{len(urls)} tiles to fetch into {output}")

    failures = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        jobs = {
            pool.submit(download, url, output / Path(url).name.split("?")[0]): url for url in urls
        }
        for done in as_completed(jobs):
            name, ok, message = done.result()
            print(f"  {'✓' if ok else '✗'} {name}: {message}")
            failures += 0 if ok else 1

    print(f"✓ {len(urls) - failures} tiles ready, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
