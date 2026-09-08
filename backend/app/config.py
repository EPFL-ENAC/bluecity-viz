"""Configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "BlueCity Traffic Analysis API"
    app_version: str = "0.2.0"

    # Graph settings
    graph_path: str = "data/lausanne.graphml"
    default_weight: str = "travel_time"

    # OD pairs. Every frequency, betweenness and CO2 value a user sees comes
    # from this set, so the count changes the results.
    #
    # od_pairs_max is sampled and routed once at startup. A request asks for a
    # number of pairs N and gets the FIRST N pairs of that set, so a result at
    # 20,000 is a subset of the one at 76,400: more pairs means the same trips
    # plus extra ones, never a different sample.
    od_pairs: int = 20_000  # default N when a request does not say
    od_pairs_max: int = 76_400  # sampled at startup, the largest N allowed

    # Areas kept in memory at the same time. One area is its mirror, its OD
    # pairs, its baseline and its payloads: about 25 MB at 76,400 pairs on a
    # Lausanne-sized graph. The budget counts what an area holds; the process
    # RSS runs higher because the allocator keeps the routing buffers, so
    # leave headroom. The default area (Lausanne) is pinned and never dropped.
    area_memory_budget_mb: int = 1024
    area_max_count: int = 20

    # The Swiss road graph, cut in cells. Empty or missing means the /areas
    # endpoints answer 503 and only the default city works.
    swiss_graph_dir: str = "data/swiss_graph"

    # What an area must look like for the tool to run on it. The node cap is
    # about twice Lausanne (4,771 nodes, 10,854 edges), which keeps a
    # recalculate around a second.
    area_min_nodes: int = 1000  # junctions, the OD sampler pool
    area_max_nodes: int = 10_000
    area_max_edges: int = 20_000
    area_min_scc_fraction: float = 0.9
    area_min_radius_m: float = 500.0
    area_max_radius_m: float = 10_000.0
    # OD pairs sampled for an area. Lower than od_pairs_max shortens the build.
    area_od_pairs_max: int = 76_400
    # Road length of the network daily_km_driven was calibrated on (Lausanne).
    reference_network_km: float = 1547.0

    # CVRP settings
    # Directory containing *_final_clustered_centroids.csv files.
    cvrp_centroids_dir: str = "data"

    # API settings
    api_v1_prefix: str = "/api/v1"

    # Browser origins allowed to call the API. Set CORS_ORIGINS to a JSON list
    # in production, for example '["https://bluecity.epfl.ch"]'.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Shared key checked on /api/v1 endpoints. Empty means no auth.
    api_key: str = ""

    # Root log level (DEBUG, INFO, WARNING, ...).
    log_level: str = "INFO"


settings = Settings()
