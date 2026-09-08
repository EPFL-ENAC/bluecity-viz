"""Main FastAPI application."""

import gc
import logging
import logging.config
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import areas as areas_router
from app.api.v1 import cvrp as cvrp_router
from app.api.v1 import routes
from app.config import settings
from app.security import require_api_key

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(levelname)s:     %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {"handlers": ["console"], "level": settings.log_level},
    "loggers": {
        # uvicorn installs its own handlers; keep ours to avoid double lines.
        "uvicorn": {"handlers": [], "propagate": True},
        "uvicorn.error": {"handlers": [], "propagate": True},
        "uvicorn.access": {"handlers": [], "propagate": True},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


def _resolve(path_setting: str) -> Path:
    """Resolve a setting path, relative ones against the backend directory."""
    path = Path(path_setting)
    if path.is_absolute():
        return path
    return (Path(__file__).parent.parent / path).resolve()


def _open_swiss_store() -> None:
    """Open the Swiss graph store, when this deployment ships one.

    Without it the app still runs: it answers on the city it loaded and the
    /areas endpoints say so with a 503.
    """
    from app.services.graph_store import GraphStore

    store_dir = _resolve(settings.swiss_graph_dir)
    if not store_dir.exists():
        logger.info("No Swiss graph store at %s, /areas is disabled", store_dir)
        areas_router.set_store(None)
        return
    try:
        store = GraphStore.open(store_dir)
    except Exception:
        logger.exception("Could not open the Swiss graph store at %s", store_dir)
        areas_router.set_store(None)
        return
    areas_router.set_store(store)
    logger.info(
        "Swiss graph store: %d nodes, %d edges, %d cells",
        store.totals["nodes"],
        store.totals["edges"],
        len(store.cells),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup: Load the graph
    full_path = _resolve(settings.graph_path)

    # The country store stands on its own: a deployment can ship it without the
    # GraphML of the default city.
    _open_swiss_store()

    if full_path.exists():
        logger.info("Loading graph from: %s", full_path)
        routes.graph_service.load_graph(str(full_path))
        logger.info("Graph loaded successfully")

        # Generate default OD pairs using research-based sampling
        logger.info("Initializing default routes with research-based sampling...")
        await routes.graph_service.initialize_default_routes(
            count=500,  # 500 OD pairs (research-based sampling is more intensive)
            seed=42,
            sampling_method="research",  # Use research-based method by default
            sampling_config=None,  # Use default configuration
        )
        logger.info("Default routes initialized")

        # The NetworkX graph and the default area live until the process ends.
        # Freezing them out of the garbage collector removes a gen-2 scan of
        # millions of objects, which used to freeze every request for 300 ms.
        # Only here: an area created later can be evicted, and a frozen object
        # is never collected.
        gc.collect()
        gc.freeze()

        # Initialize CVRP service with waste centroid CSVs
        centroids_full_path = _resolve(settings.cvrp_centroids_dir)

        app.state.cvrp_service.set_graph_service(routes.graph_service)
        if centroids_full_path.exists():
            logger.info("Initializing CVRP service from: %s", centroids_full_path)
            app.state.cvrp_service.initialize(str(centroids_full_path))
            logger.info("CVRP service initialized")
        else:
            logger.warning("Centroids directory not found at %s", centroids_full_path)
            logger.warning("CVRP endpoints will return errors until centroids are available")
    else:
        logger.warning("Graph file not found at %s", full_path)
        logger.warning("API will be available but route endpoints will fail")

    yield

    # Shutdown: cleanup if needed
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="API for traffic network analysis and route optimization",
    version=settings.app_version,
    lifespan=lifespan,
)

# Services live on the app state so tests can swap them.
app.state.cvrp_service = cvrp_router.cvrp_service

# Add GZip compression middleware for responses >= 10KB
app.add_middleware(
    GZipMiddleware,
    minimum_size=10000,  # 10KB - only compress responses larger than this
    compresslevel=3,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the traceback and return a generic 500, never the exception text."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Include routers
app.include_router(routes.router, prefix="/api/v1", dependencies=[Depends(require_api_key)])
app.include_router(areas_router.router, prefix="/api/v1", dependencies=[Depends(require_api_key)])
app.include_router(cvrp_router.router, prefix="/api/v1", dependencies=[Depends(require_api_key)])

# Mount static data directory for serving GeoJSON files
data_dir = Path(__file__).parent.parent / "data"
if data_dir.exists():
    app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "BlueCity Traffic Analysis API",
        "version": settings.app_version,
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
