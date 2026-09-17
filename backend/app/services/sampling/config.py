"""What the demand model is calibrated with.

See docs/routing-model.md for what each number does to the result.
"""

from pydantic import BaseModel, Field


class SamplingConfig(BaseModel):
    """The parameters of the demand and congestion models, tuned for Lausanne.

    The trip-length distribution is a lognormal over travel time. With the
    default mu and sigma the most likely trip takes 474 s (about 8 min), half
    the trips are under 944 s (about 16 min) and the average is 1,332 s (about
    22 min): the long tail pulls the average well past the peak.

    `betweenness_to_slowdown` is the flow per lane at which a street drops to
    half its free-flow speed, and `daily_km_driven` sets the scale flows are
    measured on. An area smaller than Lausanne gets a proportionally smaller
    `daily_km_driven` (see area_builder._scaled_config).
    """

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
        description=(
            "Node attribute for static weights ('dummy' = uniform, "
            "'population' = residents and jobs score on the graph mirror)"
        ),
    )
    lognorm_mu: float = Field(
        default=6.85, description="Lognormal mu parameter (fitted to travel survey)"
    )
    lognorm_sigma: float = Field(default=0.83, gt=0, description="Lognormal sigma parameter")
