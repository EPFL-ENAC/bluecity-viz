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


# ── Two phases: the area is held until its build is finished ─────────────────


def held_registry(budget_mb: int = 1000, max_count: int = 10):
    """A registry that keeps the second phases instead of running them."""
    reg = registry(budget_mb=budget_mb, max_count=max_count)
    jobs = []
    reg.spawn = jobs.append
    return reg, jobs


def test_the_second_phase_runs_after_the_answer():
    reg, jobs = held_registry()
    finished = []

    area = reg.get_or_build("a", lambda: FakeArea("a"), finished.append)

    assert reg.get("a") is area
    assert finished == []
    jobs.pop()()
    assert finished == [area]


def test_an_unfinished_area_survives_the_count_limit():
    reg, jobs = held_registry(max_count=2)
    reg.get_or_build("a", lambda: FakeArea("a"), lambda area: None)
    for name in "bc":
        reg.put(FakeArea(name))

    assert [a.meta.id for a in reg.loaded()] == ["a", "c"]


def test_an_unfinished_area_survives_the_budget_and_evict():
    reg, jobs = held_registry(budget_mb=15)
    reg.get_or_build("a", lambda: FakeArea("a", mb=10), lambda area: None)
    reg.put(FakeArea("b", mb=10))

    assert "a" in reg
    assert reg.evict("a") is False


def test_finishing_checks_the_budget_again():
    reg, jobs = held_registry(budget_mb=25)
    reg.put(FakeArea("old", mb=10))

    def grow(area):
        # the baseline route set lands on the area
        area._bytes = 20 * 1024 * 1024

    reg.get_or_build("a", lambda: FakeArea("a", mb=1), grow)
    assert [a.meta.id for a in reg.loaded()] == ["old", "a"]

    jobs.pop()()

    # over budget now: the old one goes, the area just finished stays
    assert [a.meta.id for a in reg.loaded()] == ["a"]
    assert reg.evict("a") is True


def test_a_finished_area_moves_to_the_newest_place():
    reg, jobs = held_registry(max_count=3)
    reg.get_or_build("a", lambda: FakeArea("a"), lambda area: None)
    reg.put(FakeArea("b"))
    reg.put(FakeArea("c"))

    jobs.pop()()
    reg.put(FakeArea("d"))

    # the client polls the area it just built, so b goes first
    assert [a.meta.id for a in reg.loaded()] == ["c", "a", "d"]


def test_a_failed_second_phase_drops_the_area():
    reg, jobs = held_registry()

    def fail(area):
        raise RuntimeError("no trip could be drawn")

    reg.get_or_build("a", lambda: FakeArea("a"), fail)
    jobs.pop()()

    assert "a" not in reg
    # and the next request builds it again
    again = reg.get_or_build("a", lambda: FakeArea("a"), lambda area: None)
    assert reg.get("a") is again


def test_concurrent_callers_get_one_build_and_one_finish():
    reg, jobs = held_registry()
    builds = []
    start = threading.Barrier(8)

    def build():
        builds.append(1)
        time.sleep(0.05)
        return FakeArea("slow")

    results = []

    def worker():
        start.wait()
        results.append(reg.get_or_build("slow", build, lambda area: None))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(builds) == 1
    assert len(jobs) == 1
    assert all(r is results[0] for r in results)


def test_the_default_spawn_runs_the_phase_on_a_thread():
    reg = registry()
    done = threading.Event()

    reg.get_or_build("a", lambda: FakeArea("a"), lambda area: done.set())

    assert done.wait(timeout=5)
