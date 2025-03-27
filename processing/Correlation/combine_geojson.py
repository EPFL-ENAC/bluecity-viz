import json
import glob
import argparse
import os
import re


def extract_info_from_filename(filename):
    """Extract dataset pair, measure, and access variable from filename"""
    base = os.path.basename(filename)

    # Extract dataset pair (waste_pop, waste_access, pop_access)
    pair_match = re.search(r"corr_(waste_pop|waste_access|pop_access)", base)
    dataset_pair = pair_match.group(1) if pair_match else None

    # Extract measure type (localcorr, similarity)
    measure_match = re.search(r"_(localcorr|similarity)", base)
    measure = measure_match.group(1) if measure_match else None

    # Extract accessibility attribute (if present)
    access_attr = None
    if dataset_pair in ["waste_access", "pop_access"]:
        # Extract index and attribute name
        attr_match = re.search(r"_\d+_(.+)\.geojson$", base)
        if attr_match:
            access_attr = attr_match.group(1)

    return dataset_pair, measure, access_attr


def combine_correlation_files(pattern, output_file):
    """
    Combines multiple correlation GeoJSON files into one,
    adding the correlation measure and accessibility variable as properties.
    """
    # Get list of files that match the pattern
    input_files = sorted(glob.glob(pattern))

    if not input_files:
        print(f"No files found matching pattern: {pattern}")
        return False

    print(f"Combining {len(input_files)} GeoJSON files into {output_file}")

    # Initialize an empty GeoJSON feature collection
    combined_geojson = {"type": "FeatureCollection", "features": []}

    # Process each input file
    for input_file in input_files:
        print(f"Processing {input_file}")
        try:
            # Extract information from filename
            dataset_pair, measure, access_attr = extract_info_from_filename(input_file)

            with open(input_file, "r") as f:
                geojson_data = json.load(f)

                if "features" in geojson_data:
                    features = geojson_data["features"]

                    # Process each feature to add measure and access attribute information
                    for feature in features:
                        # Add the measure type to properties
                        feature["properties"]["measure_type"] = measure

                        # For access-related correlations, add the accessibility attribute
                        if access_attr:
                            feature["properties"]["access_attr"] = access_attr

                            # Add combined property for filtering
                            if measure == "localcorr":
                                feature["properties"][
                                    "correlation_variable"
                                ] = f"{access_attr}-localcorr"
                            elif measure == "similarity":
                                feature["properties"][
                                    "correlation_variable"
                                ] = f"{access_attr}-similarity"

                    # Add processed features to the combined collection
                    combined_geojson["features"].extend(features)
                    print(f"Added {len(features)} features from {input_file}")
                else:
                    print(f"Warning: No 'features' found in {input_file}")
        except Exception as e:
            print(f"Error processing {input_file}: {str(e)}")

    # Write the combined GeoJSON to the output file
    with open(output_file, "w") as f:
        json.dump(combined_geojson, f)

    print(
        f"Successfully created {output_file} with {len(combined_geojson['features'])} features"
    )
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Combine correlation GeoJSON files into one"
    )
    parser.add_argument(
        "--pattern", required=True, help="Glob pattern to match input files"
    )
    parser.add_argument("--output", required=True, help="Output file name")
    args = parser.parse_args()

    combine_correlation_files(args.pattern, args.output)
