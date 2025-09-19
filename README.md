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

- **Node.js** (v20 or later)
- **Python** (3.11 or later)
- **uv** (Python package manager)
- **npm**

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
- `make dev` - Start development server
- `make build` - Build for production
- `make install` - Install all dependencies
- `make clean` - Clean temporary files
- `make notebook` - Start Jupyter notebook for data processing

## Project Structure

```
bluecity-viz/
├── frontend/          # Vue.js application
│   ├── src/           # Source code
│   │   ├── components/  # Vue components
│   │   ├── views/       # Application views
│   │   ├── stores/      # Pinia state management
│   │   └── utils/       # Utility functions
│   ├── public/        # Static assets
│   │   └── geodata/     # Geospatial data files
│   └── schema/        # JSON schemas
├── processing/        # Python data processing tools
│   ├── Correlation/   # Correlation analysis
│   ├── SP0*/          # Statistical processing modules
│   └── pyproject.toml # Python dependencies
└── Makefile          # Build automation
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
- **Vuetify** for UI components
- **MapLibre GL** for map rendering
- **PMTiles** for efficient geospatial data loading

### Data Processing

The processing module uses:

- **Python 3.11+** with modern tooling
- **uv** for fast dependency management
- **GeoPandas** for geospatial data manipulation
- **Jupyter** for interactive analysis

### Deployment

- Automated deployment via GitHub Actions
- S3 integration for geodata hosting
- Static site generation for GitHub Pages

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes and commit: `git commit -m "feat: add your feature"`
4. Push to your fork: `git push origin feat/your-feature`
5. Create a Pull Request

Please follow the [conventional commits](https://conventionalcommits.org/) format.

## License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

## Acknowledgments

- [MapLibre](https://maplibre.org/) - Open-source map rendering
- [PMTiles](https://github.com/protomaps/PMTiles) - Efficient geospatial data format
- [Vue.js](https://vuejs.org/) - Progressive JavaScript framework
- [EPFL ENAC](https://www.epfl.ch/schools/enac/) - School of Architecture, Civil and Environmental Engineering
