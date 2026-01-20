import json
import sys
from pathlib import Path

import openeo
import openeo.processes as eop
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict

SCALING_FACTOR = 10_000


def create_ppi_cube(connection: openeo.Connection, temporal_extent, spatial_extent, geom):
    s2 = connection.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        bands=["B04", "B08", "sunZenithAngles"],
    )

    s2_scl = connection.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        bands=["SCL"],
    )
    scl = s2_scl.band("SCL")
    cloudmask = ((scl == 3) | (scl == 8) | (scl == 9) | (scl == 10)) * 1
    # cloudmask = s2_scl.process(
    #     "to_scl_dilation_mask",
    #     data = s2_scl,
    # )

    s2_masked = s2.mask(cloudmask)

    mdvi = connection.load_stac(
        "https://stac.openeo.vito.be/collections/MDVI", spatial_extent=spatial_extent, bands=["dvi_max", "dvi_soil"]
    ).reduce_temporal(reducer=lambda x: eop.max(x, ignore_nodata=True))

    dvi_max = mdvi.filter_bands(["dvi_max"])
    dvi_soil = mdvi.filter_bands(["dvi_soil"])

    scalar_dvi = (
        dvi_soil.aggregate_spatial(geometries=geom, reducer=lambda x: eop.max(x, ignore_nodata=True))
        .vector_to_raster(target=dvi_max)
        .rename_labels(dimension="bands", target=["dvi_soil_scalar"])
    )

    dvi_max_clipped = dvi_max.merge_cubes(scalar_dvi).reduce_bands(reducer=lambda x: eop.min(x, ignore_nodata=True))

    ppi_input = s2_masked.merge_cubes(dvi_max_clipped).merge_cubes(dvi_soil)

    ppi = ppi_input.apply_dimension(
        process=_ppi,
        dimension="bands",
    ).rename_labels(dimension="bands", target=["PPI"])

    return ppi


def _dc(sza):
    predc = 0.0336 + (0.0477 / sza)
    return eop.min(eop.array_create([predc, 1.0]))


def _Qe(sza):
    dc = _dc(sza)
    g = 0.5
    Qe = dc + (1 - dc) * g / sza
    return Qe


def _k(sza, dvi_max, scaling):
    dvi_max_scaled = dvi_max * scaling
    return (1 / (4 * _Qe(sza))) * ((1 + dvi_max_scaled) / (1 - dvi_max_scaled))


def _ppi(input_bands):
    red = input_bands[0]
    nir = input_bands[1]
    sza = input_bands[2]
    dvi_max = input_bands[3]
    dvi_soil = input_bands[4]

    dvi = nir - red

    scaling = 1 / SCALING_FACTOR

    k = _k(sza, dvi_max, scaling)
    ppi = -1 * k * eop.ln((dvi_max - dvi) / (dvi_max - dvi_soil))

    ppi = eop.if_(dvi < dvi_soil, 0, ppi)
    ppi = eop.if_(dvi_max <= dvi, 3.0, ppi)
    ppi = ppi.clip(0, 3.0)

    ppi = ppi * SCALING_FACTOR

    return eop.array_create([ppi])


def generate() -> dict:
    connection = openeo.connect("openeo.dataspace.copernicus.eu")

    spatial_extent = Parameter.bounding_box(name="bbox")
    temporal_extent = Parameter.temporal_interval(name="temporal_extent")
    geom = Parameter.geojson(name="geometry")

    ppi_cube = create_ppi_cube(
        connection=connection,
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
    )

    process = build_process_dict(
        process_graph=ppi_cube,
        process_id="ppi",
        summary="",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[
            spatial_extent,
            temporal_extent,
            geom,
        ],
        returns=None,  # TODO
        categories=None,  # TODO
    )
    # TODO: cleaner way to inject these (https://github.com/Open-EO/openeo-python-client/issues/731)
    process.update(
        {
            "default_job_options": {"logging-threshold": "info"},
            "default_synchronous_options": {"logging-threshold": "warning"},
        }
    )
    return process


if __name__ == "__main__":
    # TODO: how to enforce a useful order of top-level keys?
    json.dump(generate(), sys.stdout, indent=2)
