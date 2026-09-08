"""The registry decides which areas stay in memory.

An area costs tens of megabytes, so the process keeps the recent ones under a
byte budget and a count limit. The default area is pinned: it answers most
requests and must never be dropped.
"""

import threading
import time

import pytest

from app.services.area_registry import AreaNotLoaded, AreaRegistry


class FakeArea:
    """Just enough of an AreaGraph for the registry: an id and a size."""

    def __init__(self, area_id: str, mb: int = 10):
        self.meta = type("Meta", (), {"id": area_id})()
        self._bytes = mb * 1024 * 1024
        self.last_used = time.time()

    def memory_bytes(self) -> int:
        return self._bytes

    def touch(self) -> None:
        self.last_used = time.time()


def registry(budget_mb: int = 1000, max_count: int = 10) -> AreaRegistry:
    return AreaRegistry(
        budget_bytes=budget_mb * 1024 * 1024, max_count=max_count, pinned={"lausanne"}
    )


def test_unknown_area_is_not_loaded():
    with pytest.raises(AreaNotLoaded):
        registry().get("nope")


def test_get_returns_what_was_put():
    reg = registry()
    area = FakeArea("a")
    reg.put(area)
    assert reg.get("a") is area
    assert "a" in reg


def test_count_limit_drops_the_oldest():
    reg = registry(max_count=3)
    for name in "abcd":
        reg.put(FakeArea(name))

    assert [a.meta.id for a in reg.loaded()] == ["b", "c", "d"]


def test_reading_an_area_saves_it_from_eviction():
    reg = registry(max_count=3)
    for name in "abc":
        reg.put(FakeArea(name))

    reg.get("a")  # a is the most recent now, b is the oldest
    reg.put(FakeArea("d"))

    assert [a.meta.id for a in reg.loaded()] == ["c", "a", "d"]


def test_budget_drops_areas_even_under_the_count_limit():
    reg = registry(budget_mb=25, max_count=10)
    reg.put(FakeArea("a", mb=10))
    reg.put(FakeArea("b", mb=10))
    reg.put(FakeArea("c", mb=10))

    assert [a.meta.id for a in reg.loaded()] == ["b", "c"]
    assert reg.total_bytes() <= 25 * 1024 * 1024


def test_the_pinned_area_is_never_dropped():
    reg = registry(budget_mb=15, max_count=2)
    reg.put(FakeArea("lausanne", mb=100), pin=True)
    for name in "abc":
        reg.put(FakeArea(name, mb=10))

    ids = [a.meta.id for a in reg.loaded()]
    assert "lausanne" in ids
    assert reg.evict("lausanne") is False


def test_evict_removes_one_area():
    reg = registry()
    reg.put(FakeArea("a"))
    assert reg.evict("a") is True
    assert reg.evict("a") is False
    with pytest.raises(AreaNotLoaded):
        reg.get("a")


def test_get_or_build_runs_once_for_concurrent_callers():
    reg = registry()
    calls = []
    start = threading.Barrier(8)

    def build():
        calls.append(1)
        time.sleep(0.05)
        return FakeArea("slow")

    results = []

    def worker():
        start.wait()
        results.append(reg.get_or_build("slow", build))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(calls) == 1
    assert len(results) == 8
    assert all(r is results[0] for r in results)


def test_a_failed_build_is_raised_to_every_caller_and_not_cached():
    reg = registry()
    attempts = []

    def build():
        attempts.append(1)
        raise RuntimeError("too sparse")

    for _ in range(2):
        with pytest.raises(RuntimeError, match="too sparse"):
            reg.get_or_build("bad", build)

    # not remembered as a failure: the second call tried again
    assert len(attempts) == 2
    assert "bad" not in reg
