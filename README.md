# MapLibre Vue Application

This repository contains a Vue.js application designed to display geospatial data using MapLibre. It includes tools for rendering maps with various data layers and a pipeline for processing datasets into PMTiles format for efficient usage in the application.

## Features

- **Map Display**: Integrates MapLibre to visualize geospatial data interactively.
- **Layer Management**: Allows toggling between different data layers.
- **Data Processing**: Includes tools to convert shapefiles, CSV, and other formats into PMTiles.
- **Scalable Design**: Optimized for rendering large datasets.

## Getting Started

### Prerequisites

Ensure you have the following installed:

- Node.js (v20 or later)
- npm or yarn
- Docker (optional, for deployment)

### Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd <repository-name>/frontend
   ```

2. Install dependencies:

   ```bash
   npm install
   ```

3. Start the development server:

   ```bash
   npm run dev
   ```

   The application should be accessible at `http://localhost:5173`.

## Project Structure

- **frontend**: Contains the Vue.js application code.

  - **src**: Application source files.
    - `components`: Vue components for map rendering and interaction.
    - `utils`: Utility functions for data handling.
    - `views`: Application views (e.g., home, about pages).
  - **public**: Static files, including configuration and style files.
  - `.vscode`: Recommended settings for development.

- **data_processing**: Scripts for preparing datasets. For detailed instructions, see [Updating Datasets for the Application](ADD_DATASET.md).

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Commit your changes and push to your fork.
4. Submit a pull request.

## License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.

## Acknowledgments

- [MapLibre](https://maplibre.org/) for the open-source map rendering library.
- [PMTiles](https://github.com/protomaps/PMTiles) for the efficient storage format for geospatial data.

For further questions or support, feel free to contact the repository maintainers.
