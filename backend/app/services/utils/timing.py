"""Timing utilities for performance instrumentation."""

import time
from contextlib import contextmanager
from typing import Generator


@contextmanager
def timed(label: str, results: dict) -> Generator[None, None, None]:
    """Measure wall-clock time for a named phase and store ms in *results*.

    Usage::
        timing: dict = {}
        with timed("route_calculation", timing):
            routes = await calculate_routes(...)
        print(timing["route_calculation"])  # ms
    """
    t0 = time.perf_counter()
    try:
        yield
    finally:
        results[label] = (time.perf_counter() - t0) * 1000
