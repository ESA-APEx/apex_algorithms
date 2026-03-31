#%%

import json
from pathlib import Path

import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict


def generate() -> dict:
    # Connect to the openEO backend (no authentication needed for graph building)
    connection = openeo.connect("openeofed.dataspace.copernicus.eu")
    
    # ----- Parameters -----
    spatial_extent = Parameter.bounding_box(
        name="spatial_extent",
        default={"west": 139.194, "south": -35.516, "east": 139.535, "north": -35.284},
        description="Area of interest (bounding box in EPSG:4326)."
    )

    reference_temporal_extent = Parameter.temporal_interval(
        name="reference_temporal_extent",
        default=["2017-02-02", "2020-02-02"],
        description="Time interval for the reference period."
    )

    current_temporal_extent = Parameter.temporal_interval(
        name="current_temporal_extent",
        default=["2020-02-02", "2020-02-28"],
        description="Time interval for the current observation (the last image inside this interval is used)."
    )

    # ----- Load and preprocess reference cube -----
    s1_ref = connection.load_collection(
        "SENTINEL1_GRD",
        temporal_extent=reference_temporal_extent,
        spatial_extent=spatial_extent,
        bands=["VV"]
    )
    s1_ref = s1_ref.sar_backscatter(coefficient="sigma0-ellipsoid")

    # ----- Load and preprocess current cube -----
    s1_cur = connection.load_collection(
        "SENTINEL1_GRD",
        temporal_extent=current_temporal_extent,
        spatial_extent=spatial_extent,
        bands=["VV"]
    )
    s1_cur = s1_cur.sar_backscatter(coefficient="sigma0-ellipsoid")

    # ----- Reference statistics -----
    dry_ref = s1_ref.reduce_dimension(dimension="t", reducer="min")   # historic minimum
    wet_ref = s1_ref.reduce_dimension(dimension="t", reducer="max")   # historic maximum
    avg_ref = s1_ref.reduce_dimension(dimension="t", reducer="mean")  # mean for masking

    # ----- Current observation (last image in the current period) -----
    s1_cur_last = s1_cur.reduce_dimension(dimension="t", reducer="last")

    # ----- Surface Soil Moisture (SSM) formula -----
    ssm = (s1_cur_last - dry_ref) / (wet_ref - dry_ref)

    # ----- Convert average reference to decibels for masking -----
    avg_ref_db = avg_ref.apply(lambda x: 10 * openeo.processes.log(x, base=10))

    # ----- Mask: values above -6 dB (urban) or below -17 dB (water) -----
    mask = (avg_ref_db > -6) | (avg_ref_db < -17)
    ssm_masked = ssm.mask(mask)   # masked pixels become nodata

    # ----- Rename the output band for clarity -----
    ssm_masked = ssm_masked.rename_labels("bands", ["SSM"])

    # ----- Build the UDP dictionary -----
    return build_process_dict(
        process_graph=ssm_masked,
        process_id="sentinel1_soil_moisture",
        summary="Estimate surface soil moisture from Sentinel‑1 using change detection",
        description=(
            "Computes surface soil moisture (SSM) from Sentinel‑1 GRD data (VV polarisation) "
            "based on the change detection method described in the Sentinel‑1 for Surface Soil Moisture project.\n\n"
            "**Formula**: SSM = (σ⁰_current - σ⁰_min) / (σ⁰_max - σ⁰_min)\n"
            "where σ⁰_min and σ⁰_max are the minimum and maximum backscatter over the reference period (typically 3 years).\n"
            "The current observation is the last image inside the current temporal interval.\n"
            "Areas with a long‑term average backscatter above –6 dB (urban) or below –17 dB (permanent water) are masked out.\n\n"
            "References:\n"
            "  - https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-1/soil_moisture_estimation/\n"
            "  - https://doi.org/10.1016/j.dib.2021.107647"
        ),
        parameters=[spatial_extent, reference_temporal_extent, current_temporal_extent],
        returns={
            "description": "Single‑band raster with surface soil moisture estimates (values between 0 and 1, nodata for masked pixels).",
            "schema": {"type": "object", "subtype": "raster-cube"}
        },
        categories=["soil", "sentinel-1", "agriculture"],
    )


if __name__ == "__main__":
    output_file = Path(__file__).parent / "sentinel1_soil_moisture.json"
    with open(output_file, "w") as f:
        json.dump(generate(), f, indent=2)
    print(f"UDP saved to {output_file}")
