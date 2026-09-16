"""Request and response models for the areas."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

# The most municipalities one area can be made of.
MAX_MUNICIPALITIES = 100


class Circle(BaseModel):
    """A circle on the map, which is how the picker works."""

    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    radius_m: float = Field(..., gt=0)


class AreaCreateRequest(BaseModel):
    """Create an area from a circle, or from municipalities by BFS number."""

    circle: Optional[Circle] = None
    municipalities: Optional[List[int]] = Field(None, min_length=1, max_length=MAX_MUNICIPALITIES)

    @model_validator(mode="after")
    def one_shape(self) -> "AreaCreateRequest":
        if (self.circle is None) == (self.municipalities is None):
            raise ValueError("give either a circle or a list of municipalities")
        return self


class MunicipalitySet(BaseModel):
    """The municipalities an area is made of, sorted by BFS number."""

    ids: List[int]
    names: List[str] = []


class AreaCounts(BaseModel):
    """What an area holds, or would hold."""

    node_count: int = 0
    edge_count: int = 0
    junction_count: int = 0  # nodes with 3 streets or more, the sampler pool
    scc_fraction: float = 0.0


class AreaPreview(AreaCounts):
    """Answer to "can I use the tool here", without building anything."""

    ok: bool
    code: Optional[
        Literal["too_sparse", "too_large", "disconnected", "outside_coverage", "not_contiguous"]
    ] = None
    message: str = ""
    bbox: Optional[List[float]] = None
    # the GeoJSON geometry of a municipality area, set even when it is refused
    outline: Optional[dict] = None


class AreaInfo(BaseModel):
    """An area that is loaded and ready to answer routing requests."""

    id: str
    kind: Literal["circle", "municipalities"] = "circle"
    name: str = ""
    circle: Optional[Circle] = None
    municipalities: Optional[MunicipalitySet] = None
    outline: Optional[dict] = None
    bbox: Optional[List[float]] = None
    node_count: int
    edge_count: int
    scc_fraction: float
    od_pairs: int = 0
    od_pairs_default: int = 0
    od_pairs_max: int = 0


class AreaLimits(BaseModel):
    """The rules the picker checks before it lets the user confirm."""

    # Junctions, not nodes: a dead end helps nobody route.
    min_junctions: int
    max_nodes: int
    max_edges: int
    min_scc_fraction: float
    min_radius_m: float
    max_radius_m: float
    # Where the network is. The picker refuses a circle outside it.
    coverage_bbox: Optional[List[float]] = None
    # Whether this server can cut an area by municipal boundaries.
    has_municipalities: bool = False
    max_municipalities: int = MAX_MUNICIPALITIES
