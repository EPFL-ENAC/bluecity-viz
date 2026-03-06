import requests
import os
from pathlib import Path
from tqdm.notebook import tqdm
from zipfile import ZipFile


def download_file(url: str, output_path: Path | str, chunk_size: int = 1024) -> None:
    """
    Download a file from a URL with progress bar

    Args:
        url: URL to download from
        output_path: Path where to save the file
        chunk_size: Size of chunks to download
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Send a HEAD request first to get the file size
    response = requests.head(url)
    total_size = int(response.headers.get("content-length", 0))

    # Download with progress bar
    response = requests.get(url, stream=True)
    response.raise_for_status()

    progress_bar = tqdm(
        total=total_size, unit="iB", unit_scale=True, desc=output_path.name
    )

    with open(output_path, "wb") as f:
        for data in response.iter_content(chunk_size=chunk_size):
            progress_bar.update(len(data))
            f.write(data)

    progress_bar.close()



data_folder = os.path.join(os.getcwd(), 'data')
Path(data_folder).mkdir(parents=True, exist_ok=True)

habitat_url = "https://data.geo.admin.ch/ch.bafu.lebensraumkarte-schweiz/lebensraumkarte-schweiz_vd/lebensraumkarte-schweiz_vd_2056.gdb.zip"
habitat_filename = os.path.join(data_folder, "habitat.zip")

download_file(habitat_url, habitat_filename)

with ZipFile(habitat_filename, 'r') as zip_ref:
    zip_ref.extractall(data_folder)

os.remove(habitat_filename)