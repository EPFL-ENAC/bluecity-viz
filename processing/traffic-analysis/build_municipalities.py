#!/usr/bin/env python3
"""Build the Swiss municipalities for the "pick municipalities" area mode.

Input: swissBOUNDARIES3D from swisstopo (gpkg or shp, LV95). Three outputs:

  - backend/data/swiss_communes.parquet   one row per commune: BFS number,
    name, canton, neighbours, bbox, simplified polygon. The backend cuts the
    area with it and checks that a selection is one region.
  - frontend/public/geodata/swiss_communes.json   names, neighbours and bbox
    per commune, so the picker can tell "not touching" and name the area
    without asking the server.
  - frontend/public/geodata/swiss_communes.pmtiles   the outlines the user
    clicks on, with the BFS number as the feature id.

    make swiss-boundaries      # once, the official release
    make swiss-communes

The neighbours are computed on the full LV95 geometry. The polygons are then
simplified together (coverage simplify), so two neighbours still share the
exact same border line after simplification: no gap, no overlap.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import shapely

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.municipalities_writer import (  # noqa: E402
    neighbours_of,
    simplify_coverage,
    write_municipalities,
)

sys.path.insert(0, str(HERE))
from generate_graph_tiles import writable_dir  # noqa: E402

# About 15 to 20 m. Enough to click on and to cut streets by, and the whole
# country is 7 MB instead of 60.
DEFAULT_TOLERANCE = 0.0002

# The shp columns are cut at 10 characters.
RENAME = {"kantonsnum": "kantonsnummer"}


def read_communes(path: str, layer: str = None) -> gpd.GeoDataFrame:
    """The Swiss communes, one row each, 2D, in LV95."""
    print(f"Reading {path}...")
    frame = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    frame = frame.rename(columns={c: c.lower() for c in frame.columns if c != "geometry"})
    frame = frame.rename(columns=RENAME)
    frame = frame[(frame["objektart"] == "Gemeindegebiet") & (frame["icc"] == "CH")]
    if frame["bfs_nummer"].duplicated().any():
        duplicated = sorted(frame.loc[frame["bfs_nummer"].duplicated(), "bfs_nummer"].tolist())
        raise SystemExit(f"a BFS number appears twice: {duplicated[:10]}")
    frame = frame.set_geometry(shapely.force_2d(frame.geometry.values))
    print(f"  {len(frame)} communes")
    return frame.reset_index(drop=True)


def default_layer(path: str) -> str:
    """The gpkg holds several layers, the shp only one."""
    return "tlm_hoheitsgebiet" if path.endswith(".gpkg") else None


def source_name(path: str) -> str:
    """The release, read from the file name (swissboundaries3d_2026-01_...)."""
    release = re.search(r"swissboundaries3d_(\d{4}-\d{2})", str(path), re.IGNORECASE)
    return f"swissBOUNDARIES3D {release.group(1)}" if release else "swissBOUNDARIES3D"


def write_index(path: Path, bfs, names, neighbours, bboxes, source: str) -> None:
    communes = {
        str(b): {"name": n, "nb": nb, "bbox": [round(v, 4) for v in box]}
        for b, n, nb, box in zip(bfs, names, neighbours, bboxes)
    }
    payload = {"format_version": 1, "source": source, "communes": communes}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def write_pmtiles(path: Path, bfs, names, geometries, tmpdir: str = None) -> None:
    spool = writable_dir(tmpdir, path.resolve().parent)
    with tempfile.NamedTemporaryFile("w", suffix=".geojsonseq", dir=spool, delete=False) as seq:
        for b, n, geometry in zip(bfs, names, geometries):
            feature = {
                "type": "Feature",
                "properties": {"bfs": int(b), "name": n},
                "geometry": json.loads(shapely.to_geojson(shapely.set_precision(geometry, 1e-6))),
            }
            seq.write(json.dumps(feature, ensure_ascii=False) + "\n")
        seq_path = seq.name

    # No coalesce and no drop: a commune merged into another, or dropped at a
    # zoom, has no id to click on. The polygons are simplified already, the
    # tiles hold them fine from z7. The BFS number becomes the feature id (and
    # leaves the properties), which is what feature-state keys on.
    command = [
        "tippecanoe",
        "-o", str(path),
        "-Z", "7",
        "-z", "12",
        "-l", "communes",
        "--use-attribute-for-id=bfs",
        "--detect-shared-borders",
        "--no-feature-limit",
        "--no-tile-size-limit",
        "-t", spool,
        "--force",
        "-P",
        seq_path,
    ]  # fmt: skip
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        print(f"✗ tippecanoe failed (exit {error.returncode})")
        print(error.stderr.rstrip())
        sys.exit(1)
    except FileNotFoundError:
        print("✗ tippecanoe not found: https://github.com/felt/tippecanoe#installation")
        sys.exit(1)
    finally:
        Path(seq_path).unlink(missing_ok=True)


def size(path: Path) -> str:
    return f"{path.stat().st_size / 1e6:.2f} MB"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--boundaries", required=True, help="swissBOUNDARIES3D gpkg or shp")
    parser.add_argument("--layer", help="layer of the gpkg (default: tlm_hoheitsgebiet)")
    parser.add_argument("--parquet", required=True, help="the file the backend reads")
    parser.add_argument("--index", help="the json the picker reads")
    parser.add_argument("--pmtiles", help="the outlines the picker draws")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE, help="degrees")
    parser.add_argument("--tmpdir", help="where tippecanoe spools")
    args = parser.parse_args()

    frame = read_communes(args.boundaries, args.layer or default_layer(args.boundaries))
    bfs = frame["bfs_nummer"].astype(int).tolist()
    names = frame["name"].astype(str).tolist()
    canton = frame["kantonsnummer"].fillna(0).astype(int).tolist()

    print("Finding the neighbours on the full geometry...")
    neighbours = neighbours_of(frame.geometry.values, bfs)
    alone = [b for b, nb in zip(bfs, neighbours) if not nb]
    print(f"  {sum(len(nb) for nb in neighbours) // 2} shared borders, {len(alone)} alone")

    print(f"Simplifying at {args.tolerance} degrees...")
    wgs84 = frame.to_crs(4326).geometry.values
    simple = simplify_coverage(wgs84, args.tolerance)
    bboxes = shapely.bounds(simple).tolist()
    source = source_name(args.boundaries)

    parquet = Path(args.parquet)
    write_municipalities(
        parquet,
        bfs=bfs,
        name=names,
        canton=canton,
        neighbours=neighbours,
        geometry=simple,
        source=source,
        simplify_deg=args.tolerance,
    )
    print(f"✓ {parquet} ({size(parquet)})")

    if args.index:
        index = Path(args.index)
        write_index(index, bfs, names, neighbours, bboxes, source)
        print(f"✓ {index} ({size(index)})")

    if args.pmtiles:
        pmtiles = Path(args.pmtiles)
        write_pmtiles(pmtiles, bfs, names, simple, args.tmpdir)
        print(f"✓ {pmtiles} ({size(pmtiles)})")


if __name__ == "__main__":
    main()
