import json
from pathlib import Path

import openeo
from openeo.api.process import Parameter
from openeo.processes import array_concat, array_create
from openeo.rest.udp import build_process_dict


def generate() -> dict:
    # TODO: use/inject dummy connection instead of concrete one? (See cdse_marketplace_services)
    connection = openeo.connect("openeofed.dataspace.copernicus.eu")

    # define parameters
    spatial_extent = Parameter.bounding_box(
        name="spatial_extent",
        default={"west": 8.82, "south": 44.40, "east": 8.92, "north": 44.45},
    )
    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent", default=["2023-05-01", "2023-07-30"]
    )

    # load collection
    s1_raw = connection.load_collection(
        collection_id="SENTINEL1_GRD",
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        bands=["VH", "VV"],
    )

    # apply back scatter filtering
    s1_raw = s1_raw.sar_backscatter(coefficient="sigma0-ellipsoid")

    # calculate stats
    s1_stats = s1_raw.apply_dimension(
        process=lambda data: array_concat(
            array1=array_create([data.min(), data.max(), data.mean(), data.sd()]),
            array2=data.quantiles([0.1, 0.5, 0.9]),
        ),
        dimension="t",
        target_dimension="bands",
    )

    # rename the generated bands
    s1_stats = s1_stats.rename_labels(
        "bands",
        [
            f"{b}_{s}"
            for b in s1_stats.metadata.band_names
            for s in ["min", "max", "mean", "sd", "q10", "q50", "q90"]
        ],
    )

    return build_process_dict(
        process_graph=s1_stats,
        process_id="sentinel1_stats",
        summary="Calculate Sentinel-1 SAR stats",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[spatial_extent, temporal_extent],
        returns=None,  # TODO
        categories=None,  # TODO
    )


if __name__ == "__main__":
    # TODO: how to enforce a useful order of top-level keys?
    # save the generated process to a file
    with open(Path(__file__).parent / "sentinel1_stats.json", "w") as f:
        json.dump(generate(), f, indent=2)
