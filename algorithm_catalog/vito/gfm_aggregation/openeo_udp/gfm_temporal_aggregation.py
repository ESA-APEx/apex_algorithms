"""
Build (and optionally publish) an openEO user-defined process (UDP) that performs a
simple temporal aggregation of the Copernicus Global Flood Monitoring (GFM) products.

The GFM products are exposed as COGs through the EODC STAC API:
    https://stac.eodc.eu/api/v1/collections/GFM

The UDP loads the collection with `load_stac`, optionally masks the no-data value and
reduces the temporal dimension with the requested statistic.

Usage:
    python gfm_temporal_aggregation.py                      # write gfm_temporal_aggregation.json
    python gfm_temporal_aggregation.py --publish            # also publish to the backend
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import openeo
from openeo import processes as eop
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict

GFM_STAC_URL = "https://stac.eodc.eu/api/v1/collections/GFM"

#: GFM layers that can be aggregated (see collection `item_assets`).
GFM_BANDS = [
    "ensemble_flood_extent",
    "ensemble_water_extent",
    "ensemble_likelihood",
    "reference_water_mask",
    "exclusion_mask",
    "advisory_flags",
    "dlr_flood_extent",
    "list_flood_extent",
    "tuw_flood_extent",
    "dlr_likelihood",
    "list_likelihood",
    "tuw_likelihood",
]

STATISTICS = ["max", "min", "mean", "median", "sum", "count"]

PROCESS_ID = "gfm_temporal_aggregation"
DEFAULT_OUTPUT = Path(__file__).with_name(f"{PROCESS_ID}.json")

BACKEND = "openeofed.dataspace.copernicus.eu"


def _parameters() -> list[Parameter]:
    return [
        Parameter.spatial_extent(
            name="spatial_extent",
            description=(
                "Spatial extent to load: a bounding box, a GeoJSON geometry or a vector data cube."
            ),
        ),
        Parameter.temporal_interval(
            name="temporal_extent",
            description="Temporal extent [start, end) to aggregate over, e.g. ['2022-09-01', '2022-10-01'].",
        ),
        Parameter.array(
            name="bands",
            description=f"GFM layers to load. One or more of: {', '.join(GFM_BANDS)}.",
            default=["ensemble_flood_extent"],
            optional=True,
            item_schema="string",
        ),
        Parameter.string(
            name="statistic",
            description=(
                "Temporal reducer applied over the full temporal extent. "
                "'max' yields the maximum (observed) flood extent, 'mean' the flood frequency, "
                "'sum' the number of flooded observations and 'count' the number of valid observations."
            ),
            default="max",
            optional=True,
            values=STATISTICS,
        ),
    ]


def build_cube(
    spatial_extent,
    temporal_extent,
    bands,
    statistic,
    connection: openeo.Connection | None = None,
):
    """Build the GFM temporal aggregation data cube (also usable outside of the UDP)."""
    cube = connection.load_stac(
        url=GFM_STAC_URL,
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        bands=bands,
    )

    # The GFM STAC collection names its temporal dimension "time" (not the openEO default "t").
    reduced_cubes = {
        name: cube.reduce_dimension(dimension="time", reducer=name) for name in STATISTICS
    }

    result = reduced_cubes["max"]
    for name in reversed([name for name in STATISTICS if name != "max"]):
        result = connection.datacube_from_process(
            process_id="if",
            value=eop.eq(statistic, name),
            accept=reduced_cubes[name],
            reject=result,
        )

    return result


def build_udp(connection) -> dict:
    spatial_extent, temporal_extent, bands, statistic = _parameters()
    cube = build_cube(
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        bands=bands,
        statistic=statistic,
        connection=connection,
    )
    return build_process_dict(
        process_graph=cube,
        process_id=PROCESS_ID,
        summary="Temporal aggregation of Global Flood Monitoring (GFM) products",
        description=(
            "Loads Copernicus Emergency Management Service Global Flood Monitoring (GFM) layers "
            f"from the EODC STAC API ({GFM_STAC_URL}) with `load_stac` and aggregates them over "
            "the given temporal extent with the selected statistic. Typical uses are the maximum "
            "observed flood extent (statistic='max'), the flood frequency (statistic='mean') or "
            "the number of flooded observations (statistic='sum'). Combine the bands "
            "'ensemble_flood_extent' and 'reference_water_mask' to obtain the observed water extent."
        ),
        parameters=[spatial_extent, temporal_extent, bands, statistic],
        returns={
            "description": "Data cube with the temporal dimension reduced to a single value per band.",
            "schema": {"type": "object", "subtype": "datacube"},
        },
        categories=["flood", "hydrology", "copernicus"],
        links=[
            {
                "rel": "about",
                "href": "https://extwiki.eodc.eu/GFM",
                "title": "GFM Wiki",
            },
            {
                "rel": "about",
                "href": "https://docs.openeo.cloud/usecases/gfm/",
                "title": "GFM use case in openEO Platform",
            },
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON file."
    )
    args = parser.parse_args()

    connection = openeo.connect(BACKEND).authenticate_oidc()

    udp = build_udp(connection)
    args.output.write_text(json.dumps(udp, indent=2) + "\n")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
