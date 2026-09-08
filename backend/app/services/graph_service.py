"""Graph service: the NetworkX graph and the areas built on it.

The service owns two things:

  * the Lausanne NetworkX graph, kept for CVRP and for the legacy GeoJSON
    endpoints, which are the only places that still need it
  * an AreaRegistry, the routing graphs the app can answer on

Lausanne is the default area: built from the GraphML file at startup, pinned
so it is never evicted, and reached by any request that does not name one.
Everything about routing lives on the AreaGraph, not here.

Delegates to:
  area_graph      - one routing graph, its OD pairs, its baseline and caches
  area_registry   - which areas are in memory, and which one to drop
  graph_mirror    - persistent igraph topology and per-edge arrays
  graph_helpers   - graph serialization for the legacy endpoints
"""

import functools
import logging
import threading
from pathlib import Path
from typing import List, Optional

import anyio.to_thread
import osmnx as ox

from app.config import settings
from app.models.route import NodePair, Route
from app.services.area_graph import DEFAULT_AREA_ID, AreaGraph, Baseline
from app.services.area_registry import AreaNotLoaded, AreaRegistry
from app.services.co2_calculator import CO2Calculator
from app.services.graph_helpers import get_edge_geometries, get_graph_data
from app.services.routing_engine import PairArrays
from app.services.utils.timing import timed  # noqa: F401 - kept for the old import path

logger = logging.getLogger(__name__)
# main.py has no logging setup and belongs to another branch right now, so the
# app keeps configuring its own handler here, as it did before.
logging.basicConfig(level=logging.INFO)
ox_logger = logging.getLogger("osmnx")
ox_logger.setLevel(logging.INFO)

__all__ = ["GraphService", "AreaNotLoaded", "Baseline", "DEFAULT_AREA_ID"]


class GraphService:
    """The NetworkX graph, the areas, and the plumbing between them."""

    def __init__(self, graph_path: Optional[str] = None):
        self.graph = None
        self.graph_path = graph_path
        self.registry = AreaRegistry(
            budget_bytes=settings.area_memory_budget_mb * 1024 * 1024,
            max_count=settings.area_max_count,
            pinned={DEFAULT_AREA_ID},
        )
        # Guards the shared NetworkX graph, which CVRP copies. Re-entrant so a
        # locked method can call another one.
        self.lock = threading.RLock()

        if graph_path:
            self.load_graph(graph_path)

    # ── Areas ─────────────────────────────────────────────────────────────────

    def area(self, area_id: Optional[str] = None) -> AreaGraph:
        """The area a request asks for. None means the default one."""
        return self.registry.get(area_id or DEFAULT_AREA_ID)

    @property
    def default_area(self) -> AreaGraph:
        return self.registry.get(DEFAULT_AREA_ID)

    # Attributes the rest of the app still reads straight off the service.
    @property
    def mirror(self):
        area = self.registry.get_optional(DEFAULT_AREA_ID)
        return area.mirror if area else None

    @property
    def baseline(self):
        area = self.registry.get_optional(DEFAULT_AREA_ID)
        return area.baseline if area else None

    @property
    def default_pairs(self):
        area = self.registry.get_optional(DEFAULT_AREA_ID)
        return area.pairs if area else None

    @property
    def od_nodes(self):
        area = self.registry.get_optional(DEFAULT_AREA_ID)
        return area.od_nodes if area else None

    @property
    def sampling_config(self):
        area = self.registry.get_optional(DEFAULT_AREA_ID)
        return area.sampling_config if area else None

    @property
    def base_co2_g(self):
        return self.default_area.base_co2_g

    @property
    def base_co2_per_km(self):
        return self.default_area.base_co2_per_km

    @property
    def route_cache(self):
        return self.default_area.route_cache

    def load_graph(self, graph_path: str):
        """Load the GraphML file, make sure speeds are present, build the default area."""
        path = Path(graph_path)
        if not path.exists():
            raise FileNotFoundError(f"Graph file not found: {graph_path}")

        self.graph = ox.load_graphml(graph_path)
        total = len(self.graph.edges)

        if (
            sum(1 for _, _, d in self.graph.edges(data=True) if d.get("speed_kph", 0) > 0)
            < total * 0.9
        ):
            self.graph = ox.routing.add_edge_speeds(self.graph)
        if (
            sum(1 for _, _, d in self.graph.edges(data=True) if d.get("travel_time", 0) > 0)
            < total * 0.9
        ):
            self.graph = ox.routing.add_edge_travel_times(self.graph)

        self._precompute_graph_metrics()
        self.registry.put(AreaGraph.from_networkx(self.graph, name="Lausanne"), pin=True)
        logger.info("[STARTUP] graph loaded: %d nodes, %d edges", len(self.graph.nodes), total)

    def _precompute_graph_metrics(self):
        """Write elevation_gain and co2_g on the NetworkX edges.

        The mirror does not need this, but CVRP and the GeoJSON endpoints read
        the NetworkX graph, so the attributes stay where they were.
        """
        if not self.graph:
            return

        for u, v, _k, data in self.graph.edges(keys=True, data=True):
            elevation_gain = data.get("elevation_gain")
            if elevation_gain is None:
                elevation_gain = 0.0
                if "elevation" in self.graph.nodes[u] and "elevation" in self.graph.nodes[v]:
                    diff = self.graph.nodes[v]["elevation"] - self.graph.nodes[u]["elevation"]
                    if diff > 0:
                        elevation_gain = diff
                data["elevation_gain"] = elevation_gain

            t = data.get("travel_time", 0)
            length_m = data.get("length", 0)
            s = data.get("speed_kph") or ((length_m / 1000) / (t / 3600) if t > 0 else None)
            data["co2_g"] = CO2Calculator.calculate_edge_co2(
                length=length_m, speed_kph=s, elevation_gain=elevation_gain
            )

    # ── Startup: OD pairs and baseline ────────────────────────────────────────

    async def initialize_default_routes(
        self,
        count: int = 500,
        radius_km: float = 2.0,
        seed: int = 42,
        sampling_method: str = "research",
        sampling_config=None,
    ):
        """Await-able wrapper: runs the sync startup work in a worker thread.

        main.py calls this with `await` during the FastAPI lifespan. The work
        is pure CPU, so it runs off the event loop.
        """
        await anyio.to_thread.run_sync(
            functools.partial(
                self.initialize_default_routes_sync,
                count=count,
                radius_km=radius_km,
                seed=seed,
                sampling_method=sampling_method,
                sampling_config=sampling_config,
            )
        )

    def initialize_default_routes_sync(
        self,
        count: int = 500,
        radius_km: float = 2.0,
        seed: int = 42,
        sampling_method: str = "research",
        sampling_config=None,
    ):
        """Generate the default OD pairs and compute the baseline once."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        from app.services.sampling.config import SamplingConfig

        config = sampling_config or SamplingConfig()
        area = self.default_area
        area.sampling_config = config

        if sampling_method == "research":
            # main.py still passes count=500, which the old sampler ignored: the
            # real size was n_origins x n_destinations_per_origin. The size is a
            # setting now. Drop the argument in main.py when that file is free.
            n_pairs = settings.od_pairs_max
            if settings.od_pairs > n_pairs:
                raise ValueError(
                    f"OD_PAIRS ({settings.od_pairs}) cannot be larger than OD_PAIRS_MAX ({n_pairs})"
                )
            if count != n_pairs:
                logger.info("[STARTUP] ignoring count=%s, using OD_PAIRS_MAX=%d", count, n_pairs)
            # No lock: the sampler reads the mirror and writes nothing. The old
            # one set weight attributes on the shared NetworkX graph.
            area.sample_research_pairs(n_pairs, config, seed)
        else:
            logger.info("[STARTUP] simple random sampling, %d OD pairs", count)
            area.pairs = PairArrays.from_nodepairs(
                area.generate_random_pairs(count=count, seed=seed, radius_km=radius_km)
            )

        logger.info("[STARTUP] %d OD pairs generated", len(area.pairs))
        area.build_baseline(config, seed)

    # ── Delegating to an area ─────────────────────────────────────────────────

    def baseline_for(self, n_pairs: int, area_id: Optional[str] = None):
        return self.area(area_id).baseline_for(n_pairs)

    def baseline_payload(self, od_pairs: Optional[int] = None, area_id: Optional[str] = None):
        return self.area(area_id).baseline_payload(od_pairs)

    def calculate_routes(
        self,
        pairs,
        weight: str = "travel_time",
        use_parallel: bool = None,
        area_id: Optional[str] = None,
    ) -> List[Route]:
        return self.area(area_id).calculate_routes(pairs, weight=weight)

    def recalculate_with_modifications(
        self, *args, area_id: Optional[str] = None, **kwargs
    ) -> dict:
        return self.area(area_id).recalculate_with_modifications(*args, **kwargs)

    def generate_random_pairs(
        self,
        count: int = 100,
        seed: Optional[int] = None,
        radius_km: float = 2.0,
        area_id: Optional[str] = None,
    ) -> List[NodePair]:
        return self.area(area_id).generate_random_pairs(count=count, seed=seed, radius_km=radius_km)

    def get_graph_info(self, area_id: Optional[str] = None) -> dict:
        return self.area(area_id).graph_info()

    def clear_route_cache(self, area_id: Optional[str] = None):
        """Drop the memoised route sets and betweenness, on one area or on all."""
        areas = [self.area(area_id)] if area_id else self.registry.loaded()
        for area in areas:
            area.clear_route_cache()

    # ── Legacy NetworkX endpoints ─────────────────────────────────────────────

    def get_edge_geometries(self, limit: Optional[int] = None) -> List[dict]:
        if not self.graph:
            raise RuntimeError("Graph not loaded")
        with self.lock:
            return get_edge_geometries(self.graph, limit)

    def get_graph_data(self):
        if not self.graph:
            raise RuntimeError("Graph not loaded")
        with self.lock:
            return get_graph_data(self.graph)
