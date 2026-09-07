"""Data extraction from the Swiss Post instance JSON.

These are corrected re-implementations of the extraction code in
EPFL-ENAC/pdptw (`pdptw_demonstration.ipynb` / `pdptw/data.py`). Differences
are deliberate and each one is a diagnosed divergence source (see README):

1. Drop-off time windows keep their real ``(start, end)`` — the upstream code
   collapses them to ``(start, start)``.
2. Per-location ``visit_time`` (seconds) is extracted from the realizations —
   upstream assumes a uniform 5 minutes for every stop.
3. The default window for shipments without one is configurable — upstream
   hardcodes ``(420, 720)`` (07:00–12:00) while commenting "up to 5 PM".

Both behaviours are available through flags so notebooks can quantify the
difference (``buggy=...``).
"""

import numpy as np
import pandas as pd

from . import config
from .io import get_area


def tw_to_minutes(tw: dict) -> tuple[float, float]:
    """{'start': 'HH:MM:SS', 'end': 'HH:MM:SS'} -> (minutes, minutes)."""

    def to_minutes(s: str) -> float:
        h, m, *rest = s.split(":")
        sec = float(rest[0]) if rest else 0.0
        return int(h) * 60 + int(m) + sec / 60

    return (to_minutes(tw["start"]), to_minutes(tw["end"]))


def build_nodes_df(instance: dict, index_mapping: pd.DataFrame) -> pd.DataFrame:
    """One row per location across all areas, aligned with the matrix indices.

    Columns: index, uuid, lat, lon, is_hub, is_depot, in_areas (list),
    visit_time_s (from the location's realization; NaN if absent).
    """
    rows = {}
    for area in instance["instance"]["delivery_areas"]:
        area_id = area["delivery_area_id"]
        hub_id = area["hub_location_id"]
        depot_ids = {d["location_id"] for d in area["depots"]}
        for loc in area["locations"]:
            uid = loc["location_id"]
            real = loc["realizations"][0] if loc.get("realizations") else {}
            row = rows.setdefault(
                uid,
                {
                    "uuid": uid,
                    "lat": loc["coordinates"]["lat"],
                    "lon": loc["coordinates"]["lng"],
                    "is_hub": False,
                    "is_depot": False,
                    "in_areas": [],
                    "visit_time_s": real.get("visit_time", np.nan),
                },
            )
            row["in_areas"].append(area_id)
            row["is_hub"] |= uid == hub_id
            row["is_depot"] |= uid in depot_ids

    df = pd.DataFrame(rows.values())
    df = index_mapping.merge(df, on="uuid", how="left")
    return df


def build_shipments_df(
    instance: dict,
    nodes: pd.DataFrame,
    area_id: int = config.AREA_ID,
    default_tw: tuple[float, float] = (420, 1020),
    buggy_dropoff_tw: bool = False,
    buggy_default_tw: bool = False,
) -> pd.DataFrame:
    """All shipments of one area as a single dataframe of pickup→delivery requests.

    Hub-based shipments become (hub → location) or (location → hub) legs, as in
    the upstream code. Location uuids are converted to matrix indices.

    Columns: shipment_id, date, kind ('hub'|'transport'), weight, volume,
    from_idx, to_idx, pickup_tw, dropoff_tw  (windows in minutes-of-day).

    Flags reproduce the upstream bugs for comparison:
    - ``buggy_dropoff_tw``: collapse transport drop-off windows to (start, start)
    - ``buggy_default_tw``: use (420, 720) for shipments without a window
    """
    area = get_area(instance, area_id)
    uuid_to_idx = dict(zip(nodes["uuid"], nodes["index"]))
    hub_idx = uuid_to_idx[area["hub_location_id"]]
    area_key = str(area_id)
    if buggy_default_tw:
        default_tw = (420, 720)

    rows = []
    for r in instance["instance"]["hub_based_shipments"]:
        loc_ids = r["task"]["location_id"]
        if area_key not in loc_ids:
            continue
        loc_idx = uuid_to_idx[loc_ids[area_key]]
        tw = (
            tw_to_minutes(r["task"]["time_window"])
            if "time_window" in r["task"]
            else default_tw
        )
        frm, to = (loc_idx, hub_idx) if r["is_pick_up"] else (hub_idx, loc_idx)
        rows.append(
            {
                "shipment_id": r["shipment_id"],
                "date": r["date"],
                "kind": "hub",
                "weight": r["capacities"][0],
                "volume": r["capacities"][1],
                "from_idx": frm,
                "to_idx": to,
                "pickup_tw": tw,
                "dropoff_tw": tw,
            }
        )

    for r in instance["instance"]["transport_shipments"]:
        loc_ids = r["pick_up"]["location_id"]
        if area_key not in loc_ids:
            continue
        drop_tw = tw_to_minutes(r["drop_off"]["time_window"])
        if buggy_dropoff_tw:
            drop_tw = (drop_tw[0], drop_tw[0])  # the upstream bug
        rows.append(
            {
                "shipment_id": r["shipment_id"],
                "date": r["date"],
                "kind": "transport",
                "weight": r["capacities"][0],
                "volume": r["capacities"][1],
                "from_idx": uuid_to_idx[r["pick_up"]["location_id"][area_key]],
                "to_idx": uuid_to_idx[r["drop_off"]["location_id"][area_key]],
                "pickup_tw": tw_to_minutes(r["pick_up"]["time_window"]),
                "dropoff_tw": drop_tw,
            }
        )

    return pd.DataFrame(rows)


def get_visit_times(nodes: pd.DataFrame) -> dict[int, float]:
    """matrix index -> visit_time in seconds (NaN-free; missing -> 0)."""
    vt = nodes.set_index("index")["visit_time_s"].fillna(0)
    return vt.to_dict()


def get_driver_limits(instance: dict, area_id: int = config.AREA_ID) -> dict:
    """Operational limits of the area's first driver template."""
    area = get_area(instance, area_id)
    avail = area["driver_templates"][0]["availability"]
    return {
        "earliest_start_min": tw_to_minutes(
            {"start": avail["earliest_start_time"], "end": avail["earliest_start_time"]}
        )[0],
        "latest_start_min": tw_to_minutes(
            {"start": avail["latest_start_time"], "end": avail["latest_start_time"]}
        )[0],
        "max_duration_min": avail["maximum_duration"] / 60,
        "break_type": avail["break_type"],
    }
