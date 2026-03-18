"""Configuration settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "BlueCity Traffic Analysis API"
    app_version: str = "0.1.0"

    # Graph settings
    graph_path: str = "data/lausanne.graphml"
    geojson_path: str = "data/lausanne.geojson"
    default_weight: str = "travel_time"

    # CVRP settings
    # Directory containing *_final_clustered_centroids.csv files.
    cvrp_centroids_dir: str = "data"

    # API settings
    api_v1_prefix: str = "/api/v1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
