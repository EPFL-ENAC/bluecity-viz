"""Parse the Swiss Post solution JSON into tidy dataframes.

The solution itineraries are sequences of timestamped events:
``TourStart, [Arrival, Departure | DrivingStart, DrivingEnd]*, TourEnd``.
From them we extract per-leg driving times and a per-tour decomposition

    total_duration = driving + service + wait

which is the precise definition of "Swiss Post's empirical values".
"""

from datetime import datetime

import pandas as pd


def _ts(event: dict) -> datetime:
    return datetime.fromisoformat(event["time_stamp"])


def extract_legs(solution: dict, uuid_to_idx: dict[str, int]) -> pd.DataFrame:
    """All driving legs: from_idx, to_idx, seconds, date, area_id."""
    rows = []
    for planning in solution["solution"]["sector_plannings"]:
        area_id = planning["delivery_area_id"]
        for tour in planning["tours"]:
            it = tour["itinerary"]
            for a, b in zip(it, it[1:]):
                if a["type"] == "DrivingStart" and b["type"] == "DrivingEnd":
                    i = uuid_to_idx.get(a["location_id"])
                    j = uuid_to_idx.get(b["location_id"])
                    rows.append(
                        {
                            "area_id": area_id,
                            "date": tour["date"],
                            "from_idx": i,
                            "to_idx": j,
                            "seconds": (_ts(b) - _ts(a)).total_seconds(),
                        }
                    )
    return pd.DataFrame(rows)


def extract_tours(solution: dict, uuid_to_idx: dict[str, int]) -> pd.DataFrame:
    """Per-tour decomposition of the itinerary timeline.

    Columns: area_id, date, n_stops (locations with an Arrival→Departure block,
    depot excluded), n_shipments, drive_min, service_min, wait_min, total_min,
    stops (ordered list of matrix indices, depot included at both ends).

    service = time between Arrival and Departure at each location;
    wait = anything in the timeline that is neither driving nor service
    (e.g. waiting for a time window to open, breaks).
    """
    rows = []
    for planning in solution["solution"]["sector_plannings"]:
        area_id = planning["delivery_area_id"]
        for tour in planning["tours"]:
            it = tour["itinerary"]
            total = (_ts(it[-1]) - _ts(it[0])).total_seconds()

            drive = service = 0.0
            stops: list[int] = []
            n_stops = 0
            arrival_t = None
            arrival_loc = None
            shipments = set()

            for ev in it:
                if ev.get("shipment_id"):
                    shipments.add(ev["shipment_id"])
                if ev["type"] == "DrivingStart":
                    drive_start = _ts(ev)
                elif ev["type"] == "DrivingEnd":
                    drive += (_ts(ev) - drive_start).total_seconds()
                elif ev["type"] == "Arrival":
                    arrival_t = _ts(ev)
                    arrival_loc = ev["location_id"]
                elif ev["type"] == "Departure" and arrival_t is not None:
                    service += (_ts(ev) - arrival_t).total_seconds()
                    idx = uuid_to_idx.get(arrival_loc)
                    if not stops or stops[-1] != idx:
                        stops.append(idx)
                    n_stops += 1
                    arrival_t = None

            rows.append(
                {
                    "area_id": area_id,
                    "date": tour["date"],
                    "vehicle_id": tour["vehicle_id"],
                    "n_stops": max(n_stops - 2, 0),  # exclude start/end depot visits
                    "n_shipments": len(shipments),
                    "drive_min": drive / 60,
                    "service_min": service / 60,
                    "wait_min": (total - drive - service) / 60,
                    "total_min": total / 60,
                    "stops": stops,
                }
            )
    return pd.DataFrame(rows)
