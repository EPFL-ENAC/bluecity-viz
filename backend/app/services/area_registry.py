"""The areas kept in memory, with a size budget.

An area costs tens of megabytes, mostly its baseline route set, so the process
cannot hold every area a user ever drew. The registry keeps the most recently
used ones under a byte budget and a count limit, and never evicts a pinned
area (Lausanne is pinned, it answers most requests).

Eviction only drops the registry's reference. A request already holding an
area keeps working on it until it returns, so there is nothing to count.
"""

import logging
import threading
from collections import OrderedDict
from concurrent.futures import Future
from typing import Callable, Dict, Iterable, List, Optional

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

    def put(self, area: AreaGraph, pin: bool = False) -> AreaGraph:
        with self._lock:
            self._areas[area.meta.id] = area
            self._areas.move_to_end(area.meta.id)
            if pin:
                self.pinned.add(area.meta.id)
            self._evict_locked()
        return area

    def evict(self, area_id: str) -> bool:
        """Drop one area. A pinned area is never dropped."""
        with self._lock:
            if area_id in self.pinned or area_id not in self._areas:
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
            oldest = next((k for k in self._areas if k not in self.pinned and k != newest), None)
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

    def get_or_build(self, area_id: str, build: Callable[[], AreaGraph]) -> AreaGraph:
        """Return the area, building it once even if several requests ask together."""
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
            self.put(area)
            with self._lock:
                self._building.pop(area_id, None)
            pending.set_result(area)
            return area
