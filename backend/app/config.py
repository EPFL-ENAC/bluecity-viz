"""Configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "BlueCity Traffic Analysis API"
    app_version: str = "0.1.0"

    # Graph settings
    graph_path: str = "data/lausanne.graphml"
    default_weight: str = "travel_time"

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
