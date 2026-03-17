"""Configuration for research-based OD pair sampling."""

from pydantic import BaseModel, Field


class SamplingConfig(BaseModel):
    """Configuration for research-based OD pair sampling.

    Calibrated to Lausanne travel patterns:
    - betweenness_to_slowdown: BC value (veh·day⁻¹·lane⁻¹) at which free-flow speed halves.
      Derived from the BPR formula: speed_cong = speed_free / (1 + BC / (lanes × k))
      where k = betweenness_to_slowdown.
    - lognorm_mu / lognorm_sigma: fitted to travel survey data.
      mode ≈ 940 s (≈ 15 min), reflecting typical urban trip lengths.
    """

    n_origins: int = Field(
        default=500, ge=10, le=2000, description="Number of origin nodes to sample"
    )
    n_destinations_per_origin: int = Field(
        default=200, ge=5, le=500, description="Number of destinations per origin"
    )
    n_nodes_preprocess: int = Field(
        default=1000,
        ge=100,
        le=5000,
        description="Max nodes for travel-time matrix and BC computation",
    )
    daily_km_driven: float = Field(
        default=1_250_000,
        gt=0,
        description="Expected vehicle-km/day — used to normalize raw BC into vehicle-flow units",
    )
    betweenness_to_slowdown: float = Field(
        default=50_000,
        gt=0,
        description="BC value causing 50% speed reduction (veh/day/lane)",
    )
    node_weight_col: str = Field(
        default="dummy",
        description="Node attribute for static weights ('dummy' = uniform)",
    )
    lognorm_mu: float = Field(
        default=6.85, description="Lognormal mu parameter (fitted to travel survey)"
    )
    lognorm_sigma: float = Field(
        default=0.83, gt=0, description="Lognormal sigma parameter"
    )
