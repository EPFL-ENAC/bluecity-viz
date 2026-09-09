#!/usr/bin/env python3
"""Download a national elevation raster, for the slopes of the country graph.

swisstopo publishes swissALTIRegio as one cloud optimised GeoTIFF for the whole
country: 10 m pixels, EPSG:2056, 10 GB. We do not need 10 m and we do not want
10 GB, so this reads one of the overviews the file already carries and writes a
small local raster. At 40 m it is 30 seconds and a few hundred MB, which is the
right scale for the slope of a street.

    uv run python download_swiss_dem.py                  # 40 m, the default
    uv run python download_swiss_dem.py --overview 1     # 10 m, 10 GB, slow
    uv run python download_swiss_dem.py --bbox 2500000,1110000,2560000,1160000

DHM25 is retired, its old download URL now serves the 200 m model, which is too
coarse for a street. Lausanne keeps swissALTI3D through
download_elevation_data.py, it is the default area and it deserves the fine one.
"""

import argparse
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window

# The national model, one cloud optimised GeoTIFF served by swisstopo.
SOURCE = (
    "/vsicurl/https://data.geo.admin.ch/ch.swisstopo.swissaltiregio/"
    "swissaltiregio/swissaltiregio_2056_5728.tif"
)
DEFAULT_OUTPUT = Path("data/elevation-ch/swissaltiregio.tif")
# 4 means every 4th pixel, so 40 m. The file carries 4, 8, 16, 32 and 64.
DEFAULT_OVERVIEW = 4
# One band of the output at a time, so memory stays flat whatever the size.
STRIP_ROWS = 1024


def copy_down(source: str, output: Path, overview: int, bbox=None) -> None:
    """Read the source at 1/overview of its resolution and write it locally."""
    output.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(source) as src:
        window = Window(0, 0, src.width, src.height)
        if bbox:
            window = src.window(*bbox).round_offsets().round_lengths()

        width = int(window.width) // overview
        height = int(window.height) // overview
        if width < 1 or height < 1:
            raise SystemExit("the box is smaller than one output pixel")

        transform = src.window_transform(window) * rasterio.Affine.scale(overview, overview)
        profile = {
            "driver": "GTiff",
            "dtype": "float32",
            "count": 1,
            "width": width,
            "height": height,
            "crs": src.crs,
            "transform": transform,
            "nodata": src.nodata,
            "compress": "deflate",
            "predictor": 3,
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
        }
        resolution = src.res[0] * overview
        print(f"source {src.width} x {src.height} at {src.res[0]:.0f} m, {src.crs}")
        print(f"output {width} x {height} at {resolution:.0f} m -> {output}")

        started = time.perf_counter()
        with rasterio.open(output, "w", **profile) as dst:
            for row in range(0, height, STRIP_ROWS):
                rows = min(STRIP_ROWS, height - row)
                read_window = Window(
                    window.col_off,
                    window.row_off + row * overview,
                    window.width,
                    rows * overview,
                )
                data = src.read(
                    1,
                    window=read_window,
                    out_shape=(rows, width),
                    resampling=Resampling.average,
                )
                dst.write(data.astype(np.float32), 1, window=Window(0, row, width, rows))
                done = min(row + rows, height)
                print(f"  {done}/{height} rows, {time.perf_counter() - started:.0f} s", end="\r")

    print()
    size = output.stat().st_size / 1e6
    print(f"✓ {output} written, {size:.0f} MB, in {time.perf_counter() - started:.0f} s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="output GeoTIFF")
    parser.add_argument(
        "--overview",
        type=int,
        default=DEFAULT_OVERVIEW,
        help="1 keeps the 10 m source, 4 gives 40 m (default), 8 gives 80 m",
    )
    parser.add_argument(
        "--bbox",
        default=None,
        help="minx,miny,maxx,maxy in EPSG:2056, to fetch one region only",
    )
    parser.add_argument("--source", default=SOURCE, help="override the source raster")
    args = parser.parse_args()

    output = Path(args.output)
    if output.exists():
        print(f"{output} is already there ({output.stat().st_size / 1e6:.0f} MB), nothing to do.")
        return 0

    bbox = [float(v) for v in args.bbox.split(",")] if args.bbox else None
    partial = output.with_suffix(output.suffix + ".part")
    copy_down(args.source, partial, args.overview, bbox)
    partial.rename(output)
    print(f"✓ {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
