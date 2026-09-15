#!/usr/bin/env python3
"""Add residents and jobs to a graph store that was built without them.

A full 'make swiss-store' needs the Geofabrik PBF and about 20 minutes. The
roads did not change, only two node columns are new, so this script rewrites
nodes.parquet alone:

    make swiss-store-population

1. read every node (x, y), snap the hectares of bfs_population.py onto them
2. write nodes.parquet again, one row group per original row group, in the
   same order, so the row group numbers in index.json stay right
3. set format_version in index.json and density.json

edges.parquet is not touched. The new file is written next to the old one and
renamed at the end, so a run that dies leaves the store as it was.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.graph_store import (  # noqa: E402
    DENSITY_FILE,
    FORMAT_VERSION,
    INDEX_FILE,
    NODE_COLUMNS,
    NODES_FILE,
)
from app.services.graph_store_writer import NODE_PARQUET, snap_hectares  # noqa: E402
from bfs_population import load_hectares  # noqa: E402


def set_version(path: Path) -> None:
    """Change the format_version of a JSON file, and nothing else in it."""
    text = path.read_text()
    old = json.loads(text)["format_version"]
    before = f'"format_version": {old}'
    if text.count(before) != 1:
        raise SystemExit(f"{path}: cannot find {before} once")
    path.write_text(text.replace(before, f'"format_version": {FORMAT_VERSION}'))
    print(f"  {path.name}: format_version {old} -> {FORMAT_VERSION}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, help="the store directory")
    parser.add_argument("--statpop", required=True, help="STATPOP hectare CSV")
    parser.add_argument("--statent", required=True, help="STATENT hectare CSV")
    args = parser.parse_args()

    store = Path(args.store)
    nodes_path = store / NODES_FILE
    source = pq.ParquetFile(nodes_path)
    columns = [c for c in source.schema_arrow.names if c not in ("residents", "jobs_fte")]

    print(f"Reading {source.metadata.num_rows:,} nodes in {source.num_row_groups} row groups ...")
    everything = source.read(columns=["x", "y"])
    hectares = load_hectares(Path(args.statpop), Path(args.statent))
    residents, jobs_fte = snap_hectares(
        everything["x"].to_numpy(),
        everything["y"].to_numpy(),
        hectares["e"].to_numpy(),
        hectares["n"].to_numpy(),
        hectares["residents"].to_numpy(),
        hectares["jobs_fte"].to_numpy(),
    )
    print(
        f"  on the nodes: {int(residents.sum()):,} residents, {float(jobs_fte.sum()):,.0f} jobs, "
        f"{int(((residents > 0) | (jobs_fte > 0)).sum()):,} nodes with someone"
    )

    schema = pa.schema(NODE_COLUMNS)
    temp = nodes_path.with_suffix(".parquet.part")
    writer = pq.ParquetWriter(temp, schema, **NODE_PARQUET)
    start = 0
    try:
        for rg in range(source.num_row_groups):
            table = source.read_row_group(rg, columns=columns)
            end = start + table.num_rows
            data = {name: table[name] for name in columns}
            data["residents"] = pa.array(residents[start:end], type=pa.int32())
            data["jobs_fte"] = pa.array(jobs_fte[start:end], type=pa.float32())
            writer.write_table(pa.table({name: data[name] for name in NODE_COLUMNS}, schema=schema))
            start = end
    finally:
        writer.close()

    check = pq.ParquetFile(temp)
    if check.num_row_groups != source.num_row_groups or check.metadata.num_rows != start:
        temp.unlink()
        raise SystemExit("the new nodes.parquet does not match the old one, store left as it was")
    for rg in (0, source.num_row_groups - 1):
        old = source.read_row_group(rg, columns=["node_id"])["node_id"].to_numpy()
        new = check.read_row_group(rg, columns=["node_id"])["node_id"].to_numpy()
        if not np.array_equal(old, new):
            temp.unlink()
            raise SystemExit(f"row group {rg} moved, store left as it was")

    temp.replace(nodes_path)
    print(f"  {NODES_FILE}: {nodes_path.stat().st_size / 1e6:.1f} MB")
    set_version(store / INDEX_FILE)
    set_version(store / DENSITY_FILE)
    print(f"✓ {store} is format {FORMAT_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
