#!/usr/bin/env python3
import json
import os


def extract_unique_attribute_values(geojson_path, attributes):
    """Extract unique values for specified attributes from a GeoJSON file."""

    print(f"Analyzing {geojson_path} for attributes: {', '.join(attributes)}")

    # Check if file exists
    if not os.path.exists(geojson_path):
        print(f"Error: File {geojson_path} not found")
        return {}

    # Read GeoJSON file
    try:
        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {geojson_path}")
        return {}
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        return {}

    # Initialize dictionary to store unique values for each attribute
    unique_values = {attr: set() for attr in attributes}

    # Extract unique values from features
    features = data.get("features", [])
    print(f"Found {len(features)} features in the GeoJSON file")

    for feature in features:
        properties = feature.get("properties", {})
        for attr in attributes:
            if attr in properties and properties[attr] is not None:
                unique_values[attr].add(properties[attr])

    # Convert sets to sorted lists for better readability
    result = {attr: sorted(list(values)) for attr, values in unique_values.items()}

    # Print results
    for attr, values in result.items():
        print(f"\n{attr} ({len(values)} unique values):")
        for value in values:
            print(f"  - {value}")

    return result


if __name__ == "__main__":
    geojson_path = "geojson/Final_buildings_Lausanne.geojson"
    attributes = ["Era", "Function", "Archetype"]
    extract_unique_attribute_values(geojson_path, attributes)
