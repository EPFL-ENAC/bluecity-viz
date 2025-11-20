"""Main FastAPI application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.v1 import routes
from app.config import settings
from app.services.graph_service import GraphService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup: Load the graph
    graph_path = Path(settings.graph_path)
    if graph_path.is_absolute():
        full_path = graph_path
    else:
        # Relative to backend directory
        backend_dir = Path(__file__).parent.parent
        full_path = (backend_dir / graph_path).resolve()

    if full_path.exists():
        print(f"Loading graph from: {full_path}")
        routes.graph_service.load_graph(str(full_path))
        print("Graph loaded successfully")
    else:
        print(f"Warning: Graph file not found at {full_path}")
        print("API will be available but route endpoints will fail")

    yield

    # Shutdown: cleanup if needed
    print("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="API for traffic network analysis and route optimization",
    version=settings.app_version,
    lifespan=lifespan,
)

# Add GZip compression middleware for responses >= 10KB
app.add_middleware(
    GZipMiddleware,
    minimum_size=10000,  # 10KB - only compress responses larger than this
    compresslevel=3  
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes.router, prefix="/api/v1")

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
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
