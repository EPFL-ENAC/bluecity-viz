"""Graph service: the NetworkX graph and the areas.

The service owns two things:

  * the Lausanne NetworkX graph (the GraphML), kept for CVRP and the habitat
    layer only. No routing request reads it.
  * an AreaRegistry, the routing graphs the app can answer on

The default area is a circle on Lausanne cut from the Swiss store, like any
area the user picks. It is built at startup, pinned so it is never evicted,
and reached by any request that does not name an area. Everything about
routing lives on the AreaGraph, not here.

Delegates to:
  area_builder    - cuts an area out of the store
  area_graph      - one routing graph, its OD pairs, its baseline and caches
  area_registry   - which areas are in memory, and which one to drop
  graph_mirror    - persistent igraph topology and per-edge arrays
"""

import logging
import threading
from pathlib import Path
from typing import List, Optional

import numpy as np
import osmnx as ox

from app.config import settings
from app.models.route import NodePair, Route
from app.services.area_graph import AreaGraph, Baseline
from app.services.area_registry import AreaNotLoaded, AreaRegistry
from app.services.co2_calculator import CO2Calculator
from app.services.utils.timing import timed  # noqa: F401 - kept for the old import path

logger = logging.getLogger(__name__)
logging.getLogger("osmnx").setLevel(logging.INFO)

__all__ = ["GraphService", "AreaNotLoaded", "Baseline"]

# The waste tool runs on an area when at least this share of its junctions
# are in the CVRP graph. Both come from OSM, so the ids are the same: the
# default circle has 90 %, a circle in Bern 0 %.
CVRP_MIN_SHARE = 0.5


class GraphService:
    """The NetworkX graph, the areas, and the plumbing between them."""

    def __init__(self, graph_path: Optional[str] = None):
        self.graph = None
        self.graph_path = graph_path
        # The node ids of the CVRP graph, sorted, to tell if an area is on it.
        self.cvrp_node_ids: Optional[np.ndarray] = None
        # The area a request with no area_id runs on. None until it is built.
        self.default_area_id: Optional[str] = None
        self.registry = AreaRegistry(
            budget_bytes=settings.area_memory_budget_mb * 1024 * 1024,
            max_count=settings.area_max_count,
        )
        # Guards the shared NetworkX graph, which CVRP copies. Re-entrant so a
        # locked method can call another one.
        self.lock = threading.RLock()

        if graph_path:
            self.load_graph(graph_path)

    # ── Areas ─────────────────────────────────────────────────────────────────

    def area(self, area_id: Optional[str] = None) -> AreaGraph:
        """The area a request asks for. None means the default one."""
        area_id = area_id or self.default_area_id
        if area_id is None:
            # No store, so no default area: say it like any missing area.
            raise AreaNotLoaded("default")
        return self.registry.get(area_id)

    @property
    def default_area(self) -> AreaGraph:
        return self.area(None)

    def set_default_area(self, area: AreaGraph) -> AreaGraph:
        """Pin an area and make it the one a request with no area_id gets."""
        self.registry.put(area, pin=True)
        self.default_area_id = area.meta.id
        return area

    def load_default_area(self, store, seed: int = 42) -> AreaGraph:
        """Cut the default circle out of the store, the same way as any area.

        Startup calls this once. It draws the OD pairs and the baseline, like
        POST /areas. The only differences: the area is pinned, it is named
        Lausanne, and it keeps the bigger caches the default always had.
        """
        from app.services import area_builder
        from app.services.sampling.config import SamplingConfig

        spec = area_builder.CircleSpec.from_circle(
            settings.default_area_lon, settings.default_area_lat, settings.default_area_radius_m
        )
        area = area_builder.build(store, spec, SamplingConfig(), seed)
        # The cache sizes are read at each insert, so this is enough.
        area.dynamic = False
        area.meta.name = "Lausanne"
        logger.info(
            "[STARTUP] default area %s: %d nodes, %d edges",
            area.meta.id,
            area.mirror.n_nodes,
            area.mirror.n_edges,
        )
        return self.set_default_area(area)

    def runs_cvrp(self, area: AreaGraph) -> bool:
        """Whether the waste tool can run on this area.

        CVRP solves on the GraphML, not on the area. It makes sense when most
        of the area is in that graph: the closed streets are then streets the
        solver knows, and its routes land on the streets on screen.
        """
        ids = self.cvrp_node_ids
        if ids is None or len(ids) == 0 or area.mirror.n_nodes == 0:
            return False
        inside = np.isin(area.mirror.node_ids, ids, assume_unique=True)
        return float(inside.mean()) >= CVRP_MIN_SHARE

    # Attributes the tests still read straight off the service.
    def _default_or_none(self) -> Optional[AreaGraph]:
        if self.default_area_id is None:
            return None
        return self.registry.get_optional(self.default_area_id)

    @property
    def mirror(self):
        area = self._default_or_none()
        return area.mirror if area else None

    @property
    def baseline(self):
        area = self._default_or_none()
        return area.baseline if area else None

    @property
    def default_pairs(self):
        area = self._default_or_none()
        return area.pairs if area else None

    @property
    def od_nodes(self):
        area = self._default_or_none()
        return area.od_nodes if area else None

    @property
    def sampling_config(self):
        area = self._default_or_none()
        return area.sampling_config if area else None

    @property
    def base_co2_g(self):
        return self.default_area.base_co2_g

    @property
    def route_cache(self):
        return self.default_area.route_cache

    def load_graph(self, graph_path: str):
        """Load the GraphML file for CVRP and make sure speeds are present.

        This builds no area: routing runs on areas cut from the store.
        """
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
        self.cvrp_node_ids = np.sort(np.fromiter(self.graph.nodes, dtype=np.int64))
        logger.info("[STARTUP] graph loaded: %d nodes, %d edges", len(self.graph.nodes), total)

    def _precompute_graph_metrics(self):
        """Write elevation_gain and co2_g on the NetworkX edges.

        CVRP reads them on the NetworkX graph.
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

    # ── Delegating to an area ─────────────────────────────────────────────────

    def baseline_for(
        self, n_pairs: int, area_id: Optional[str] = None, node_weighting: str = "uniform"
    ):
        return self.area(area_id).baseline_for(n_pairs, node_weighting)

    def baseline_payload(
        self,
        od_pairs: Optional[int] = None,
        area_id: Optional[str] = None,
        node_weighting: str = "uniform",
    ):
        return self.area(area_id).baseline_payload(od_pairs, node_weighting)

    def calculate_routes(
        self, pairs, weight: str = "travel_time", area_id: Optional[str] = None
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
