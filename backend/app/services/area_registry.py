"""The areas kept in memory, with a size budget.

An area costs tens of megabytes, mostly its baseline route set, so the process
cannot hold every area a user ever drew. The registry keeps the most recently
used ones under a byte budget and a count limit, and never evicts a pinned
area (Lausanne is pinned, it answers most requests).

Eviction only drops the registry's reference. A request already holding an
area keeps working on it until it returns, so there is nothing to count.

An area can be built in two phases (see area_builder.start and finish). The
registry answers with it after the first one and runs the second one in the
background. Until that is done the area is held like a pinned one: dropping it
would throw away a baseline the client is waiting for, and the client would
build the same area again at once.
"""

import logging
import threading
from collections import OrderedDict
from concurrent.futures import Future
from typing import Callable, Dict, Iterable, List, Optional, Set

from app.services.area_graph import AreaGraph

logger = logging.getLogger(__name__)


class AreaNotLoaded(KeyError):
    """The area is unknown, or it was evicted. The client re-creates it."""

    def __init__(self, area_id: str):
        super().__init__(area_id)
        self.area_id = area_id


class AreaRegistry:
    """LRU of AreaGraph, bounded by total bytes and by count."""

    def __init__(
        self,
        budget_bytes: int,
        max_count: int,
        pinned: Iterable[str] = (),
    ):
        self.budget_bytes = budget_bytes
        self.max_count = max_count
        self.pinned = set(pinned)
        self._areas: "OrderedDict[str, AreaGraph]" = OrderedDict()
        self._lock = threading.Lock()
        self._building: Dict[str, Future] = {}
        # Areas whose second build phase still runs. Never evicted.
        self._unfinished: Set[str] = set()
        # How the second phase is run. A daemon thread, so it does not depend
        # on the request or on the event loop. Tests swap it.
        self.spawn: Callable[[Callable[[], None]], None] = _daemon_thread

    # ── Lookup ────────────────────────────────────────────────────────────────

    def get(self, area_id: str) -> AreaGraph:
        area = self.get_optional(area_id)
        if area is None:
            raise AreaNotLoaded(area_id)
        return area

    def get_optional(self, area_id: str) -> Optional[AreaGraph]:
        with self._lock:
            area = self._areas.get(area_id)
            if area is not None:
                self._areas.move_to_end(area_id)
            return area

    def __contains__(self, area_id: str) -> bool:
        return area_id in self._areas

    def loaded(self) -> List[AreaGraph]:
        with self._lock:
            return list(self._areas.values())

    def total_bytes(self) -> int:
        return sum(a.memory_bytes() for a in self.loaded())

    # ── Insert and evict ──────────────────────────────────────────────────────

    def put(self, area: AreaGraph, pin: bool = False, unfinished: bool = False) -> AreaGraph:
        with self._lock:
            self._areas[area.meta.id] = area
            self._areas.move_to_end(area.meta.id)
            if pin:
                self.pinned.add(area.meta.id)
            if unfinished:
                # in the same lock, or a put in between could drop it
                self._unfinished.add(area.meta.id)
            self._evict_locked()
        return area

    def evict(self, area_id: str) -> bool:
        """Drop one area. A pinned or unfinished area is never dropped."""
        with self._lock:
            if area_id in self.pinned or area_id in self._unfinished or area_id not in self._areas:
                return False
            del self._areas[area_id]
        logger.info("[AREAS] evicted %s", area_id)
        return True

    def _evict_locked(self) -> None:
        """Drop the oldest unpinned areas until we are under both limits.

        Never the newest one, even when it alone is over budget: the caller is
        about to answer with it, and dropping it here would send the client to
        an area that is already gone, over and over.
        """
        total = sum(a.memory_bytes() for a in self._areas.values())
        newest = next(reversed(self._areas), None)
        while len(self._areas) > self.max_count or total > self.budget_bytes:
            oldest = next(
                (
                    k
                    for k in self._areas
                    if k not in self.pinned and k not in self._unfinished and k != newest
                ),
                None,
            )
            if oldest is None:
                return
            total -= self._areas[oldest].memory_bytes()
            del self._areas[oldest]
            logger.info(
                "[AREAS] evicted %s, %d left, %.0f MB",
                oldest,
                len(self._areas),
                total / 1e6,
            )

    # ── Build once ────────────────────────────────────────────────────────────

    def get_or_build(
        self,
        area_id: str,
        build: Callable[[], AreaGraph],
        finish: Optional[Callable[[AreaGraph], object]] = None,
    ) -> AreaGraph:
        """Return the area, building it once even if several requests ask together.

        With `finish`, `build` is the first phase only: the area is answered
        with as soon as it returns, and `finish(area)` runs after, through
        `spawn`. See `_finish`.
        """
        area = self.get_optional(area_id)
        if area is not None:
            return area

        with self._lock:
            pending = self._building.get(area_id)
            if pending is None:
                pending = Future()
                self._building[area_id] = pending
                mine = True
            else:
                mine = False

        if not mine:
            # Someone else is building it: wait for the same result.
            return pending.result()

        try:
            area = build()
        except BaseException as exc:  # noqa: BLE001 - re-raised to every waiter
            with self._lock:
                self._building.pop(area_id, None)
            pending.set_exception(exc)
            raise
        else:
            self.put(area, unfinished=finish is not None)
            with self._lock:
                self._building.pop(area_id, None)
            pending.set_result(area)
            if finish is not None:
                self.spawn(lambda: self._finish(area, finish))
            return area

    def _finish(self, area: AreaGraph, finish: Callable[[AreaGraph], object]) -> None:
        """Run the second phase, then let the area be evicted again.

        The area grew by its whole route set, and the budget was only checked
        when it was small, so it is checked again here. The area moves to the
        newest place first: the client is polling it and is about to use it.
        If the phase fails the area is dropped, and the client gets the usual
        `area_not_loaded` and builds it again.
        """
        area_id = area.meta.id
        try:
            finish(area)
        except Exception:  # noqa: BLE001 - nobody waits on this thread
            logger.exception("[AREAS] could not finish %s, dropping it", area_id)
            with self._lock:
                self._unfinished.discard(area_id)
                if self._areas.get(area_id) is area:
                    del self._areas[area_id]
            return
        with self._lock:
            self._unfinished.discard(area_id)
            if self._areas.get(area_id) is area:
                self._areas.move_to_end(area_id)
                self._evict_locked()


def _daemon_thread(job: Callable[[], None]) -> None:
    threading.Thread(target=job, name="area-finish", daemon=True).start()
