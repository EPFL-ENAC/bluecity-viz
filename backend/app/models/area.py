"""Request and response models for the areas."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Circle(BaseModel):
    """A circle on the map, which is how the picker works."""

    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    radius_m: float = Field(..., gt=0)


class AreaCreateRequest(BaseModel):
    """Create an area from a circle or from a polygon. Exactly one of them."""

    circle: Optional[Circle] = None
    polygon: Optional[List[List[float]]] = Field(
        default=None,
        min_length=3,
        description="Ring of [lon, lat] points, not closed",
    )

    @model_validator(mode="after")
    def exactly_one_shape(self):
        if (self.circle is None) == (self.polygon is None):
            raise ValueError("give exactly one of circle or polygon")
        return self


class AreaCounts(BaseModel):
    """What an area holds, or would hold."""

    node_count: int = 0
    edge_count: int = 0
    junction_count: int = 0  # nodes with 3 streets or more, the sampler pool
    scc_fraction: float = 0.0


class AreaPreview(AreaCounts):
    """Answer to "can I use the tool here", without building anything."""

    ok: bool
    code: Optional[Literal["too_sparse", "too_large", "disconnected", "outside_coverage"]] = None
    message: str = ""
    bbox: Optional[List[float]] = None


class AreaInfo(BaseModel):
    """An area that is loaded and ready to answer routing requests."""

    id: str
    kind: str
    name: str
    circle: Optional[Circle] = None
    polygon: Optional[List[List[float]]] = None
    bbox: Optional[List[float]] = None
    node_count: int
    edge_count: int
    scc_fraction: float
    od_pairs: int = 0
    od_pairs_default: int = 0
    od_pairs_max: int = 0
    status: str = "ready"
    build_ms: float = 0.0
    cached: bool = False


class AreaLimits(BaseModel):
    """The rules the picker checks before it lets the user confirm."""

    min_nodes: int
    max_nodes: int
    max_edges: int
    min_scc_fraction: float
    min_radius_m: float
    max_radius_m: float
    coverage_bbox: Optional[List[float]] = None
    density_url: str = "/geodata/swiss_graph_density.json"
