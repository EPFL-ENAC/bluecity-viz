# BlueCity Viz

A Vue.js application designed to visualize geospatial data using MapLibre, with integrated data processing tools for urban analytics and sustainability metrics.

## Features

- **Interactive Map Visualization**: Built with MapLibre for smooth geospatial data rendering
- **Layer Management**: Toggle between different data layers and visualizations
- **Data Processing Pipeline**: Convert shapefiles, CSV, and other formats into PMTiles
- **Urban Analytics**: Specialized tools for analyzing city data and sustainability metrics
- **Responsive Design**: Optimized for both desktop and mobile viewing

## Getting Started

### Prerequisites

- **Node.js** 24 (see `frontend/.nvmrc`)
- **pnpm** (pinned by the `packageManager` field)
- **Python** 3.12 or later
- **uv** (Python package manager)
- **GNU Make**

### Quick Start

1. **Clone the repository:**

   ```bash
   git clone https://github.com/EPFL-ENAC/bluecity-viz.git
   cd bluecity-viz
   ```

2. **Install all dependencies:**

   ```bash
   make install
   ```

3. **Start the development server:**

   ```bash
   make dev
   ```

   The application will be available at `http://localhost:5173`

### Available Commands

- `make help` - Show all available commands
- `make install` - Install all dependencies (frontend, backend, processing)
- `make dev` - Start backend and frontend together
- `make dev-frontend` - Frontend only
- `make dev-backend` - Backend only
- `make build` - Build the frontend for production
- `make upload-frontend-geodata` - Push the geodata to S3 (needs `BUCKET_NAME`,
  see `.env.example`)

To work on several branches at once, the repo has a git worktree setup
(`make go BRANCH=feat/x`). See [docs/worktree-env/](docs/worktree-env/).

## Project Structure

```
bluecity-viz/
├── frontend/          # Vue 3 application
│   ├── src/
│   │   ├── components/  # sidebar, dock, panels, dialogs, ui
│   │   ├── composables/ # map and Deck.gl logic
│   │   ├── views/       # HomeView, the shell
│   │   ├── stores/      # Pinia state
│   │   ├── services/    # backend HTTP clients
│   │   ├── config/      # layer definitions per dataset
│   │   └── utils/       # basemap style, colours, helpers
│   └── public/
│       └── geodata/     # local PMTiles (production reads the CDN)
├── backend/           # FastAPI: routing, CO2, betweenness centrality
│   └── app/services/  # graph, routing engine, BPR, sampling
├── processing/        # Python tools, raw datasets to PMTiles
│   ├── Correlation/   # correlation analysis
│   └── SP0*/          # sustainability indicator modules
├── docs/              # worktree setup, traffic analysis
└── Makefile           # build automation
```

### Key Directories

- **`frontend/`**: Vue.js application with MapLibre integration
- **`processing/`**: Python tools for data analysis and processing
- **`frontend/public/geodata/`**: Processed geospatial data in PMTiles format

For detailed dataset management instructions, see [ADD_DATASET.md](ADD_DATASET.md).

## Development

### Frontend Development

The frontend is built with:

- **Vue 3** with Composition API
- **TypeScript** for type safety
- **MapLibre GL** for map rendering, **Deck.gl** for the analytics overlays
- **Pinia** for state, **Vuetify** for a few remaining widgets
- **PMTiles** for efficient geospatial data loading

See [frontend/README.md](frontend/README.md) for the scripts and the layout.

### Backend Development

FastAPI over a GraphML road network loaded with osmnx. It pre-generates
research-sampled OD pairs at startup and serves routing and impact analysis
on `/api/v1/routes/`. Interactive docs at `http://127.0.0.1:8000/docs`.

### Data Processing

The processing module uses:

- **Python 3.12+** with modern tooling
- **uv** for fast dependency management
- **GeoPandas** for geospatial data manipulation
- **Jupyter** for interactive analysis

### Deployment

- Automated deployment via GitHub Actions
- S3 integration for geodata hosting
- Static site generation for GitHub Pages

## Contributing

Branch from `dev`, open the pull request against `dev`, and follow the
[conventional commits](https://conventionalcommits.org/) format. CI checks the
commit messages, the lint, the types, the tests and the build.

The full guide is in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

## Acknowledgments

- [MapLibre](https://maplibre.org/) - Open-source map rendering
- [PMTiles](https://github.com/protomaps/PMTiles) - Efficient geospatial data format
- [Vue.js](https://vuejs.org/) - Progressive JavaScript framework
- [EPFL ENAC](https://www.epfl.ch/schools/enac/) - School of Architecture, Civil and Environmental Engineering
