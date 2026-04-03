#%%

"""
Generation script for the timeseries_statistics UDP.

Run this script to (re-)generate timeseries_statistics.json:

    python generate.py

"""

import json
from pathlib import Path

import openeo
from openeo.api.process import Parameter
from openeo.processes import array_concat, array_create, is_valid
from openeo.rest.datacube import CollectionMetadata, DataCube
from openeo.rest.udp import build_process_dict


def generate() -> dict:
    connection = openeo.connect("openeofed.dataspace.copernicus.eu")

    # ── parameters ──────────────────────────────────────────────────────────
    collection_id = Parameter(
        name="collection_id",
        description=(
            "The identifier of the EO collection to load "
            "(e.g. 'SENTINEL2_L2A', 'SENTINEL1_GRD'). "
            "The collection must be available on the target backend."
        ),
        default="SENTINEL2_L2A",
        optional=True,
    )

    bands = Parameter(
        name="bands",
        description=(
            "Band names to include in the statistics "
            "(e.g. ['B04', 'B08'] for Sentinel-2 L2A Red and NIR). "
            "When set to null (the default) all bands of the collection are loaded."
        ),
        
        default=None,
        optional=True,
    )

    spatial_extent = Parameter.bounding_box(
        name="spatial_extent",
        description=(
            "Spatial extent as a bounding box with 'west', 'south', 'east' "
            "and 'north' fields in WGS84."
        ),
        default={"west": 4.97, "south": 51.19, "east": 5.07, "north": 51.28},
    )

    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent",
        description=(
            "Temporal extent as a two-element array [start, end] "
            "using ISO-8601 date or date-time strings."
        ),
        default=["2025-05-01", "2025-07-31"],
    )

    resolution = Parameter(
        name="resolution",
        description=(
            "Target spatial resolution in the units of the collection's native CRS "
            "(e.g. metres for a projected CRS). "
            "When set to null (the default) the collection's native resolution is kept."
        ),
        schema=[
            {"type": "number", "exclusiveMinimum": 0},
            {"type": "null"},
        ],
        default=None,
        optional=True,
    )

    # ── load collection ───────────────────────────────────────────────────────

    cube = connection.datacube_from_process(
        process_id="load_collection",
        id=collection_id,
        bands=bands,
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
    )


    # ── optionally resample to requested resolution ───────────────────────────
    cube = connection.datacube_from_process(
        process_id="if",
        value=is_valid(resolution),
        accept=connection.datacube_from_process(
            process_id="resample_spatial",
            data=cube,
            resolution=resolution,
            method="near",
        ),
        reject=cube,
    )

    # ── compute temporal statistics ──────────────────────────────────────────

    _meta = CollectionMetadata({
        "cube:dimensions": {
            "t":     {"type": "temporal"},
            "bands": {"type": "bands", "values": []},
            "x":     {"type": "spatial"},
            "y":     {"type": "spatial"},
        }
    })
    cube = DataCube(graph=cube._pg, connection=connection, metadata=_meta)

    stats = cube.apply_dimension(
        process=lambda data: array_concat(
            array1=array_create([data.min(), data.max(), data.mean(), data.sd()]),
            array2=data.quantiles([0.1, 0.5, 0.9]),
        ),
        dimension="t",
        target_dimension="bands",
    )


    description = (
        Path(__file__).parent / "timeseries_statistics_description.md"
    ).read_text()

    return build_process_dict(
        process_graph=stats,
        process_id="timeseries_statistics",
        summary="Calculate temporal statistics for any EO collection",
        description=description,
        parameters=[collection_id, bands, spatial_extent, temporal_extent, resolution],
    )


if __name__ == "__main__":
    result = generate()
    out = Path(__file__).parent / "timeseries_statistics.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Written to {out}")



#%%


