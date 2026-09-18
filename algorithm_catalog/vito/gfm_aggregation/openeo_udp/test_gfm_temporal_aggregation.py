"""
Test / demo script for the `gfm_temporal_aggregation` UDP.

It reproduces the openEO Platform GFM use case (Pakistan floods, September 2022) and
writes a GeoTIFF with the maximum observed flood extent.

Examples:
    # quick offline check: only build the process graph and validate its structure
    python test_gfm_temporal_aggregation.py --dry-run

    # run on a backend (opens an OIDC login) and download the result
    python test_gfm_temporal_aggregation.py

    # flood frequency instead of maximum flood extent
    python test_gfm_temporal_aggregation.py --statistic mean --output flood_frequency.tif

    # run the UDP as published on the backend instead of the inline graph
    python test_gfm_temporal_aggregation.py --use-published-udp
"""

from __future__ import annotations

import argparse
from pathlib import Path

import openeo

from gfm_temporal_aggregation import (
    DEFAULT_OUTPUT,
    PROCESS_ID,
    STATISTICS,
)

# Pakistan flood 2022, as in https://docs.openeo.cloud/usecases/gfm/
SPATIAL_EXTENT = {"west": 67.5, "east": 70.0, "south": 24.5, "north": 26.0}
TEMPORAL_EXTENT = ["2022-09-01", "2022-10-01"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="openeofed.dataspace.copernicus.eu")
    parser.add_argument(
        "--udp", type=Path, help="Path to the UDP JSON file.", default=DEFAULT_OUTPUT
    )

    parser.add_argument("--statistic", default="max", choices=STATISTICS)
    parser.add_argument("--bands", nargs="+", default=["ensemble_flood_extent"])
    parser.add_argument("--output", type=Path, default=Path("gfm_aggregation.tif"))
    args = parser.parse_args()

    connection = openeo.connect(args.backend).authenticate_oidc()

    cube = connection.datacube_from_json(
        str(args.udp),
        spatial_extent=SPATIAL_EXTENT,
        temporal_extent=TEMPORAL_EXTENT,
        bands=args.bands,
        statistic=args.statistic,
    )

    cube.download(args.output)
    print(f"Result written to {args.output}")


if __name__ == "__main__":
    main()
