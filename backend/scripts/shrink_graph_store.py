#!/usr/bin/env python3
"""Rewrite a graph store the small way, without building it again from OSM.

The store used to keep every shape point OSM gives and plain float32
coordinates, which is 76 MB for Switzerland. `graph_store_writer` now drops
the points a road does not need and encodes the coordinates so zstd can do
its work, which is about 44 MB. Building the country again takes twenty
minutes and the OSM extract, so this converts a store already on disk
instead. What it writes is byte for byte what a fresh build would write.

The row groups keep their boundaries and their order, so `index.json`, which
names them by number, stays valid and is not touched. Neither is
`density.json`.

    uv run python scripts/shrink_graph_store.py data/swiss_graph
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.graph_store import EDGES_FILE, NODES_FILE  # noqa: E402
from app.services.graph_store_writer import (  # noqa: E402
    EDGE_PARQUET,
    NODE_PARQUET,
    SIMPLIFY_M,
    simplify_geometry,
)


def rewrite(path: Path, options: dict, simplify: float = 0.0) -> tuple[float, float]:
    """Write one parquet file again, same rows in the same row groups."""
    before = path.stat().st_size / 1e6
    source = pq.ParquetFile(path)
    rows = [source.metadata.row_group(i).num_rows for i in range(source.metadata.num_row_groups)]
    table = pq.read_table(path)

    if simplify:
        column = table.column("geom_xy").combine_chunks()
        offsets = column.offsets.to_numpy().astype(np.int64)
        flat = column.values.to_numpy(zero_copy_only=False)
        lines = [flat[offsets[i] : offsets[i + 1]] for i in range(len(offsets) - 1)]
        kept = simplify_geometry(lines, simplify)
        was = sum(len(line) for line in lines) // 2
        now = sum(len(line) for line in kept) // 2
        print(f"  shape points {was:,} -> {now:,} ({100 * now / was:.0f}%)")
        table = table.set_column(
            table.schema.get_field_index("geom_xy"),
            "geom_xy",
            pa.array(kept, type=table.schema.field("geom_xy").type),
        )

    temporary = path.with_suffix(".parquet.new")
    writer = pq.ParquetWriter(temporary, table.schema, **options)
    try:
        start = 0
        for count in rows:
            writer.write_table(table.slice(start, count), row_group_size=count)
            start += count
    finally:
        writer.close()

    check = pq.ParquetFile(temporary)
    wanted, written = source.metadata, check.metadata
    if written.num_rows != wanted.num_rows:
        raise SystemExit(f"{path.name}: wrote {written.num_rows} rows, expected {wanted.num_rows}")
    if written.num_row_groups != wanted.num_row_groups:
        raise SystemExit(f"{path.name}: the row groups moved, index.json would not match")

    after = temporary.stat().st_size / 1e6
    os.replace(temporary, path)
    return before, after


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store", help="the store directory, e.g. data/swiss_graph")
    parser.add_argument(
        "--simplify-m",
        type=float,
        default=SIMPLIFY_M,
        help=f"how far a drawn street may move, in metres (default {SIMPLIFY_M})",
    )
    args = parser.parse_args()

    store = Path(args.store)
    if not (store / EDGES_FILE).exists():
        raise SystemExit(f"No store in {store}")

    total_before = total_after = 0.0
    for name, options, simplify in (
        (EDGES_FILE, EDGE_PARQUET, args.simplify_m),
        (NODES_FILE, NODE_PARQUET, 0.0),
    ):
        print(name)
        before, after = rewrite(store / name, options, simplify)
        print(f"  {before:.1f} MB -> {after:.1f} MB")
        total_before += before
        total_after += after

    print(f"\nstore {total_before:.1f} MB -> {total_after:.1f} MB")


if __name__ == "__main__":
    main()
