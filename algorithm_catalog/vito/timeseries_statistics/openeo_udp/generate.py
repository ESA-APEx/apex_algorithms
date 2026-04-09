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
from openeo.processes import is_valid
from openeo.rest.datacube import CollectionMetadata, DataCube
from openeo.rest.udp import build_process_dict


def generate() -> dict:
    connection = openeo.connect("openeofed.dataspace.copernicus.eu")

    # ── parameters ──────────────────────────────────────────────────────────
    collection_id = Parameter.string(
        name="collection_id",
        description=(
            "The identifier of the EO collection to load "
            "(e.g. 'SENTINEL2_L2A', 'SENTINEL1_GRD'). "
            "The collection must be available on the target backend."
        ),
        default="SENTINEL2_L2A",
        optional=True,
    )

    bands = Parameter.array(
        name="bands",
        description=(
            "Band names to include in the statistics "
            "(e.g. ['B04', 'B08'] for Sentinel-2 L2A Red and NIR). "
            "Must be provided so that output bands can be labelled "
            "(e.g. B04_min, B04_max, …)."
        ),
        item_schema={"type": "string"},
        default=["B04", "B08"],
    )

    geometry = Parameter.geojson(
        name="geometry",
        description=(
            "GeoJSON geometry (Polygon or MultiPolygon) defining the area "
            "of interest. Statistics are spatially averaged over this geometry."
        )
    )

    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent",
        description=(
            "Temporal extent as a two-element array [start, end] "
            "using ISO-8601 date or date-time strings."
        )
        )

    period = Parameter.string(
        name="period",
        description=(
            "Temporal aggregation period. When set to null (the default) "
            "a single set of summary statistics (min, max, mean, sd, q10, "
            "q50, q90) is computed over the full temporal extent, collapsing "
            "the time dimension.  When set to a calendar period such as "
            "'month' or 'year', the same statistics are computed for every "
            "period, producing a time-series of statistics."
        ),
        values=["year", "month", "week", "dekad", "day"],
        default=None,
        optional=True,
    )


    # ── load collection ───────────────────────────────────────────────────────

    cube = connection.datacube_from_process(
        process_id="load_collection",
        id=collection_id,
        bands=bands,
        temporal_extent=temporal_extent,
    )

    # ── spatial filter using GeoJSON geometry ─────────────────────────────────
    cube = connection.datacube_from_process(
        process_id="filter_spatial",
        data=cube,
        geometries=geometry,
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

    # ── helper: quantile reducer returning a scalar ─────────────────────────
    def _quantile_reducer(prob):
        return {
            "process_graph": {
                "quantiles1": {
                    "process_id": "quantiles",
                    "arguments": {
                        "data": {"from_parameter": "data"},
                        "probabilities": [prob],
                    },
                },
                "element1": {
                    "process_id": "array_element",
                    "arguments": {
                        "data": {"from_node": "quantiles1"},
                        "index": 0,
                    },
                    "result": True,
                },
            }
        }

    # ── helper: rename bands by appending a suffix ──────────────────────────
    def _rename_bands_with_suffix(stat_cube, suffix):
        """Rename bands: e.g. B04 → B04_min, B08 → B08_min"""
        suffixed_labels = connection.datacube_from_process(
            process_id="array_apply",
            data=bands,
            process={
                "process_graph": {
                    "concat1": {
                        "process_id": "text_concat",
                        "arguments": {
                            "data": [{"from_parameter": "x"}, suffix],
                            "separator": "",
                        },
                        "result": True,
                    },
                }
            },
        )
        return connection.datacube_from_process(
            process_id="rename_labels",
            data=stat_cube,
            dimension="bands",
            target=suffixed_labels,
        )

    # Simple scalar reducers
    _simple_reducers = {
        "min": "min",
        "max": "max",
        "mean": "mean",
        "sd": "sd",
    }
    # Quantile reducers
    _quantile_reducers = {
        "q10": _quantile_reducer(0.1),
        "q50": _quantile_reducer(0.5),
        "q90": _quantile_reducer(0.9),
    }

    stat_order = ["min", "max", "mean", "sd", "q10", "q50", "q90"]

    # ── full mode: 7 separate reduce_dimension calls ────────────────────────
    full_cubes = {}
    for label, reducer in _simple_reducers.items():
        reduced = cube.reduce_dimension(reducer=reducer, dimension="t")
        full_cubes[label] = _rename_bands_with_suffix(reduced, f"_{label}")
    for label, reducer in _quantile_reducers.items():
        reduced = connection.datacube_from_process(
            process_id="reduce_dimension",
            data=cube,
            dimension="t",
            reducer=reducer,
        )
        full_cubes[label] = _rename_bands_with_suffix(reduced, f"_{label}")

    full_stats = full_cubes[stat_order[0]]
    for name in stat_order[1:]:
        full_stats = connection.datacube_from_process(
            process_id="merge_cubes",
            cube1=full_stats,
            cube2=full_cubes[name],
        )

    # ── period mode: 7 separate aggregate_temporal_period calls ─────────────
    period_cubes = {}
    for label, reducer in _simple_reducers.items():
        agg = cube.aggregate_temporal_period(period=period, reducer=reducer)
        period_cubes[label] = _rename_bands_with_suffix(agg, f"_{label}")
    for label, reducer in _quantile_reducers.items():
        agg = connection.datacube_from_process(
            process_id="aggregate_temporal_period",
            data=cube,
            period=period,
            reducer=reducer,
        )
        period_cubes[label] = _rename_bands_with_suffix(agg, f"_{label}")

    period_stats = period_cubes[stat_order[0]]
    for name in stat_order[1:]:
        period_stats = connection.datacube_from_process(
            process_id="merge_cubes",
            cube1=period_stats,
            cube2=period_cubes[name],
        )

    # ── conditional: period provided → per-period, else → full ──────────────
    stats = connection.datacube_from_process(
        process_id="if",
        value=is_valid(period),
        accept=period_stats,
        reject=full_stats,
    )

    # ── aggregate spatially → JSON timeseries ───────────────────────────────
    stats = connection.datacube_from_process(
        process_id="aggregate_spatial",
        data=stats,
        geometries=geometry,
        reducer={
            "process_graph": {
                "mean1": {
                    "process_id": "mean",
                    "arguments": {"data": {"from_parameter": "data"}},
                    "result": True,
                }
            }
        },
    )

    # ── save result ─────────────────────────────────────────────────────────
    stats = connection.datacube_from_process(
        process_id="save_result",
        data=stats,
        format="CSV",
    )

    description = (
        Path(__file__).parent / "timeseries_statistics_description.md"
    ).read_text()

    return build_process_dict(
        process_graph=stats,
        process_id="timeseries_statistics",
        summary="Calculate temporal statistics for any EO collection",
        description=description,
        parameters=[
            collection_id,
            bands,
            geometry,
            temporal_extent,
            period
        ],
    )


if __name__ == "__main__":
    result = generate()
    out = Path(__file__).parent / "timeseries_statistics.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Written to {out}")



#%%

import openeo
connection = openeo.connect("openeo.dataspace.copernicus.eu").authenticate_oidc()

geometry = {
    "type": "Polygon",
    "coordinates": [[
        [4.97, 51.19], [5.07, 51.19], [5.07, 51.28], [4.97, 51.28], [4.97, 51.19]
    ]]
}
temporal_extent = ["2025-05-01", "2025-07-31"]

collection_id = "SENTINEL2_L2A"
bands = ["B04", "B08"]
period = "month"

cube = connection.datacube_from_json('C:\\Git_projects\\apex_algorithms\\algorithm_catalog\\vito\\timeseries_statistics\\openeo_udp\\timeseries_statistics.json',
                                     parameters = {'geometry': geometry,
                                                'temporal_extent': temporal_extent,
                                                'collection_id': collection_id,
                                                'bands': bands,
                                                'period': period})
cube

#%%
job = cube.create_job()
job.start_and_wait()



