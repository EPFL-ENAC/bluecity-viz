# BlueCity Viz - Data Processing

This folder contains the data processing scripts and tools for the BlueCity visualization project.

## Setup with uv

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management.

### Prerequisites

1. Install uv if you haven't already:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Restart your shell or run:
   ```bash
   source ~/.bashrc  # or ~/.zshrc
   ```

### Getting Started

1. Navigate to the processing directory:

   ```bash
   cd processing
   ```

2. Create a virtual environment and install dependencies:

   ```bash
   uv sync
   ```

3. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```

### Common Commands

- **Install dependencies**: `uv sync`
- **Add a new dependency**: `uv add package-name`
- **Add a development dependency**: `uv add --dev package-name`
- **Remove a dependency**: `uv remove package-name`
- **Update dependencies**: `uv sync --upgrade`
- **Run a script**: `uv run python script.py`
- **Run with specific Python version**: `uv run --python 3.11 python script.py`

### Development Tools

The project includes several development tools:

- **Code formatting**: `uv run black .`
- **Import sorting**: `uv run isort .`
- **Linting**: `uv run flake8 .`
- **Type checking**: `uv run mypy .`
- **Testing**: `uv run pytest`

### Project Structure

- `Correlation/` - Correlation analysis scripts
- `GWS2022/` - GWS2022 data processing
- `Population and Households Statistics/` - Population data processing
- `SP0_Migration/` - Migration data processing
- `SP02_Mobility/`, `SP02 - Mobility/` - Mobility data processing
- `SP03_Nature/`, `SP03 - Nature/` - Nature data processing
- `SP04_Waste/` - Waste data processing
- `SP06_Materials/`, `SP06 - Materials/` - Materials data processing
- `SP7/` - Additional processing scripts

### Dependencies

Main dependencies include:

- `pandas` - Data manipulation and analysis
- `geopandas` - Geospatial data processing
- `shapely` - Geometric operations
- `numpy` - Numerical computing
- `matplotlib` - Plotting
- `seaborn` - Statistical data visualization
- `folium` - Interactive maps
- `plotly` - Interactive plotting

## Usage Examples

### Running a processing script

```bash
# Using uv run (recommended)
uv run python SP7/process.py

# Or activate the environment first
source .venv/bin/activate
python SP7/process.py
```

### Installing additional packages

```bash
# Add a new package
uv add requests

# Add a development package
uv add --dev jupyter
```

### Working with Jupyter notebooks

```bash
# Install jupyter if not already installed
uv add --dev jupyter

# Start jupyter
uv run jupyter notebook
```
