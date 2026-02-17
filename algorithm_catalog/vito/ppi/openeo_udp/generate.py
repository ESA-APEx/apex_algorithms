# %%
import json
from pathlib import Path

import openeo
import openeo.processes as eop
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict


def create_ppi_cube(connection: openeo.Connection, temporal_extent, geom):
    s2 = connection.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=temporal_extent,
        bands=["B04", "B08", "sunZenithAngles"],
    ).filter_spatial(geom)

    s2_scl = connection.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=temporal_extent,
        bands=["SCL"],
    ).filter_spatial(geom)
    scl = s2_scl.band("SCL")
    cloudmask = ((scl == 3) | (scl == 8) | (scl == 9) | (scl == 10)) * 1
    s2_masked = s2.mask(cloudmask)

    mdvi = (
        connection.load_stac("https://stac.openeo.vito.be/collections/MDVI", bands=["dvi_max", "dvi_soil"])
        .filter_spatial(geom)
        .reduce_temporal(reducer=lambda x: eop.max(x, ignore_nodata=True))
        .rename_labels(dimension="bands", target=["dvi_max", "dvi_soil"])
    )

    dvi_max = mdvi.filter_bands(["dvi_max"])
    dvi_soil = mdvi.filter_bands(["dvi_soil"])

    scalar_dvi = (
        dvi_soil.aggregate_spatial(geometries=geom, reducer=lambda x: eop.max(x, ignore_nodata=True))
        .vector_to_raster(target=dvi_max)
        .rename_labels(dimension="bands", target=["dvi_soil_scalar"])
    )

    dvi_max_clipped = dvi_max.merge_cubes(scalar_dvi).reduce_bands(reducer=lambda x: eop.max(x, ignore_nodata=True))

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


def _k(sza, dvi_max):
    # Calculate Qe
    Qe = _Qe(sza)

    # Calculate k with safe denominator
    k_num = 1 + dvi_max
    k_den = 1 - dvi_max

    k = (1 / (4 * Qe)) * (k_num / k_den)

    return k


def _ppi(input_bands):
    SCALE = 10000.0

    red = input_bands[0] / SCALE
    nir = input_bands[1] / SCALE
    sza_deg = input_bands[2]
    dvi_max = input_bands[3] / SCALE
    dvi_soil = input_bands[4] / SCALE

    sza_rad = sza_deg * (3.14159265 / 180)
    sza = eop.cos(sza_rad)

    dvi_max = eop.min(eop.array_create([dvi_max, 0.8]), ignore_nodata=True)

    dvi = nir - red

    # Calculate ratio with SAFETY BOUNDS
    numerator = dvi_max - dvi
    denominator = dvi_max - dvi_soil
    ratio = numerator / denominator

    # Calculate k with the corrected _k function
    k = _k(sza, dvi_max)

    # Calculate PPI
    ppi = -1 * k * eop.ln(ratio)

    # Apply PPI bounds
    ppi = eop.if_(dvi < dvi_soil, 0, ppi)
    ppi = eop.if_(dvi_max <= dvi, 3.0, ppi)
    ppi = ppi.clip(0, 3.0)

    return ppi


def generate() -> dict:
    connection = openeo.connect("openeo.dataspace.copernicus.eu")

    temporal_extent = Parameter.temporal_interval(name="temporal_extent")
    geom = Parameter.geojson(name="geometry")

    ppi_cube = create_ppi_cube(
        connection=connection,
        temporal_extent=temporal_extent,
        geom=geom,
    )

    process = build_process_dict(
        process_graph=ppi_cube,
        process_id="ppi",
        summary="Satellite-based vegetation index designed to monitor vegetation growth cycles",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[
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
    OUTPUT_PATH = Path(__file__).parent / "ppi.json"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)  # ensure folder exists

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(generate(), f, indent=2)

    print(f"Saved to {OUTPUT_PATH}")


# Example usage in sandbox
"""
spatial_extent = {
    "west": 4.22,
    "south": 51.16,
    "east": 4.377856,
    "north": 51.26
}
geom = {
    "type": "Polygon",
    "coordinates": [[
        [spatial_extent["west"], spatial_extent["south"]],
        [spatial_extent["east"], spatial_extent["south"]],
        [spatial_extent["east"], spatial_extent["north"]],
        [spatial_extent["west"], spatial_extent["north"]],
        [spatial_extent["west"], spatial_extent["south"]]
    ]]
}

temporal_extent = ["2024-06-01", "2024-08-30"]
ppi_cube = create_ppi_cube(
    connection=connection,
    temporal_extent=temporal_extent,
    geom=geom
)
job = ppi_cube.create_job(out_format="GTiff", title="ppi_example").start_and_wait()
"""
