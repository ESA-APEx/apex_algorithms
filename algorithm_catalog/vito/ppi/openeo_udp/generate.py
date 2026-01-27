#%%
import json
import sys
from pathlib import Path

import openeo
import openeo.processes as eop
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict


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
    s2_masked = s2.mask(cloudmask)

    mdvi = connection.load_stac(
        "https://stac.openeo.vito.be/collections/MDVI", spatial_extent=spatial_extent, bands=["dvi_max", "dvi_soil"]
    ).reduce_temporal(reducer=lambda x: eop.max(x, ignore_nodata=True)).rename_labels(dimension="bands", target=["dvi_max", "dvi_soil"])

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

def _k(sza, dvi_max):
    sza_rad = sza  # Assume radians for now
    
    # Safety: ensure reasonable values
    sza_safe = eop.max(eop.array_create([sza_rad, 0.01]))  # > 0
    sza_safe = eop.min(eop.array_create([sza_safe, 1.5]))   # < ~85°
    
    dvi_max_safe = eop.max(eop.array_create([dvi_max, 0.3]))
    dvi_max_safe = eop.min(eop.array_create([dvi_max_safe, 0.9]))
    
    # Calculate Qe
    Qe_deg = _Qe(sza_safe * (180/3.14159))  # Convert rad to deg
    
    # Use whichever gives reasonable Qe (~0.05-0.5)
    Qe = Qe_deg  #
    
    # Calculate k with safe denominator
    k_num = 1 + dvi_max_safe
    k_den = 1 - dvi_max_safe
    k_den = eop.max(eop.array_create([k_den, 0.01]))
    
    k = (1 / (4 * Qe)) * (k_num / k_den)
    
    # k should be 0.3-1.5 - if not, something's wrong
    k = eop.min(eop.array_create([k, 2.0]))
    
    return k


def _ppi(input_bands):
    SCALE = 10000.0
    
    SCALE = 10000.0
    
    red_raw = input_bands[0] / SCALE
    nir_raw = input_bands[1] / SCALE
    sza = input_bands[2]
    dvi_max = input_bands[3] / SCALE
    dvi_soil = input_bands[4] / SCALE
    
    # CLIP reflectance to physically possible range [0, 1]
    red = eop.max(eop.array_create([red_raw, 0.0]))
    red = eop.min(eop.array_create([red, 1.0]))
    
    nir = eop.max(eop.array_create([nir_raw, 0.0]))
    nir = eop.min(eop.array_create([nir, 1.0]))
    
    dvi = nir - red
    
    # CLIP dvi_max to reasonable vegetation range
    dvi_max = eop.max(eop.array_create([dvi_max, 0.3]))  # Minimum 0.3
    dvi_max = eop.min(eop.array_create([dvi_max, 0.9]))  # Maximum 0.9
    
    # CLIP dvi_soil to reasonable soil range  
    dvi_soil = eop.max(eop.array_create([dvi_soil, 0.05]))  # Minimum 0.05
    dvi_soil = eop.min(eop.array_create([dvi_soil, 0.3]))   # Maximum 0.3
    
    # Ensure dvi_soil < dvi_max
    dvi_soil = eop.min(eop.array_create([dvi_soil, dvi_max * 0.8]))
    
    # Calculate ratio with SAFETY BOUNDS
    numerator = dvi_max - dvi
    denominator = dvi_max - dvi_soil
    
    # Prevent division by near-zero and extreme values
    denominator = eop.max(eop.array_create([denominator, 0.001]))
    ratio = numerator / denominator
    
    # Clip ratio to valid log range
    ratio = eop.max(eop.array_create([ratio, 0.001]))  # Avoid log(0)
    ratio = eop.min(eop.array_create([ratio, 0.999]))  # Avoid log(1)
    
    # Calculate k with the corrected _k function below
    k = _k(sza, dvi_max)
    
    # Calculate PPI
    ppi = -1 * k * eop.ln(ratio)
    
    # Apply PPI bounds
    ppi = eop.if_(dvi < dvi_soil, 0, ppi)
    ppi = eop.if_(dvi_max <= dvi, 3.0, ppi)
    ppi = ppi.clip(0, 3.0)
    
    # Return with debug bands
    return ppi


def generate() -> dict:
    connection = openeo.connect("openeo.dataspace.copernicus.eu")

    spatial_extent = Parameter.bounding_box(name="bbox")
    temporal_extent = Parameter.temporal_interval(name="temporal_extent")
    geom = Parameter.geojson(name="geometry")

    ppi_cube = create_ppi_cube(
        connection=connection,
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        geom=geom,
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
    OUTPUT_PATH = Path(r".\records\ppi.json")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)  # ensure folder exists

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(generate(), f, indent=2)

    print(f"Saved to {OUTPUT_PATH}")



# Example usage in sandbox
'''
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
    spatial_extent=spatial_extent,
    geom=geom
)
job = ppi_cube.create_job(out_format="GTiff", title="ppi_example").start_and_wait()
'''

#%%
import openeo
connection = openeo.connect("openeo.dataspace.copernicus.eu").authenticate_oidc()
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
    spatial_extent=spatial_extent,
    geom=geom
)
job = ppi_cube.create_job(out_format="GTiff", title="ppi_example").start_and_wait()

#%%
geom
