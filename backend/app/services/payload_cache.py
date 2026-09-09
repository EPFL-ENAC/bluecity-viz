"""Serialised JSON payloads that never change, kept with their ETag.

A payload is built once and then served as bytes. Every cache belongs to
something that can go away: the areas keep their own, so evicting an area
frees its megabytes too.
"""

import hashlib
import logging
import threading
from typing import Callable, Dict, Tuple

import orjson

logger = logging.getLogger(__name__)


class PayloadCache:
    """Small thread-safe {key: (bytes, etag)} store."""

    def __init__(self, label: str = ""):
        self.label = label
        self._items: Dict[str, Tuple[bytes, str]] = {}
        self._lock = threading.Lock()

    def get_or_build(self, key: str, build: Callable[[], object]) -> Tuple[bytes, str]:
        """Return (bytes, etag), building the payload the first time."""
        hit = self._items.get(key)
        if hit is None:
            with self._lock:
                hit = self._items.get(key)
                if hit is None:
                    data = orjson.dumps(build())
                    etag = '"' + hashlib.blake2b(data, digest_size=16).hexdigest() + '"'
                    hit = (data, etag)
                    self._items[key] = hit
                    logger.info(
                        "[CACHE] built %s%s payload, %.1f MB",
                        f"{self.label}:" if self.label else "",
                        key,
                        len(data) / 1e6,
                    )
        return hit

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def nbytes(self) -> int:
        return sum(len(data) for data, _etag in self._items.values())
