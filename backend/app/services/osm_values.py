"""Reading OSM tag values, which are never quite the type you expect.

A tag can come back as a string, a number, or a list when osmnx merged two
ways into one edge. These helpers live alone, with no import of their own, so
the offline pipeline in processing/ can use them without pulling igraph and
the rest of the routing stack.
"""


def parse_lanes(value, default: int = 2) -> int:
    """Read a lane count from an OSM attribute, which can be a list or a string."""
    if isinstance(value, list):
        value = value[0] if value else default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_street_count(value) -> int:
    """Read street_count from a node attribute. Missing or unreadable means 0.

    0 keeps the node out of the OD sampling pool, which is what a missing
    value did before (NaN >= 3 is False).
    """
    if isinstance(value, list):
        value = value[0] if value else 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
