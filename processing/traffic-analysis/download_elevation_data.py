#!/usr/bin/env python3
"""
Download Swiss elevation data (swissALTI3D) for Lausanne area.

This script downloads elevation raster tiles from swisstopo for use in
adding elevation data to road network graphs.
"""

import requests
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Configuration
CSV_FILE = "list_raster_elevation_lausanne.csv"
OUTPUT_DIR = Path("data/elevation")
MAX_WORKERS = 4  # Number of parallel downloads
TIMEOUT = 60  # Request timeout in seconds

def download_file(url: str, output_path: Path) -> tuple[str, bool, str]:
    """
    Download a file from URL to output path.
    
    Returns:
        Tuple of (filename, success, message)
    """
    filename = output_path.name
    
    # Skip if already exists
    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        return (filename, True, f"Already exists ({size_mb:.1f} MB)")
    
    try:
        response = requests.get(url, timeout=TIMEOUT, stream=True)
        response.raise_for_status()
        
        # Write file in chunks
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        size_mb = output_path.stat().st_size / (1024 * 1024)
        return (filename, True, f"Downloaded ({size_mb:.1f} MB)")
        
    except Exception as e:
        return (filename, False, f"Failed: {e}")


def main():
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Read URLs from CSV
    print(f"Reading URLs from {CSV_FILE}...")
    df = pd.read_csv(CSV_FILE)
    urls = df['url'].tolist()
    print(f"Found {len(urls)} elevation tiles to download")
    
    # Prepare download tasks
    tasks = []
    for url in urls:
        filename = url.split('/')[-1]
        output_path = OUTPUT_DIR / filename
        tasks.append((url, output_path))
    
    print(f"\nDownloading to: {OUTPUT_DIR.absolute()}")
    print(f"Using {MAX_WORKERS} parallel workers\n")
    
    # Download files in parallel
    successful = 0
    failed = 0
    skipped = 0
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        futures = {
            executor.submit(download_file, url, path): (url, path) 
            for url, path in tasks
        }
        
        # Process results as they complete
        for i, future in enumerate(as_completed(futures), 1):
            filename, success, message = future.result()
            
            if success:
                if "Already exists" in message:
                    skipped += 1
                    status = "⊙"
                else:
                    successful += 1
                    status = "✓"
            else:
                failed += 1
                status = "✗"
            
            # Progress indicator
            print(f"[{i:3d}/{len(tasks)}] {status} {filename}: {message}")
    
    elapsed = time.time() - start_time
    
    # Summary
    print(f"\n{'='*70}")
    print(f"Download complete in {elapsed:.1f} seconds")
    print(f"  Downloaded: {successful}")
    print(f"  Skipped:    {skipped}")
    print(f"  Failed:     {failed}")
    print(f"  Total:      {len(tasks)}")
    print(f"\nElevation data saved to: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
