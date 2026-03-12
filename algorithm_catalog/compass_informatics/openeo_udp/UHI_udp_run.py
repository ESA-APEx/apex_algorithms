"""
uhi_udp_run.py
==============
Invokes the "uhi_jja" User-Defined Process (UDP) that was registered by
uhi_udp_register.py, submits a batch job, and downloads the result GeoTIFF.

Usage
-----
Edit the PARAMETERS dict below (or import and call run_uhi_udp() directly),
then run:

    python uhi_udp_run.py

Prerequisites
-------------
    python uhi_udp_register.py   # must be run first, once
"""

import openeo

OPENEO_URL = "https://openeo.dataspace.copernicus.eu/openeo/1.2"
UDP_ID     = "UHI_per_pixel"

# ---------------------------------------------------------------------------
# Edit these to define your job
# ---------------------------------------------------------------------------
# PARAMETERS = {
#     "spatial_extent": {
#         "west":  -0.563,
#         "south": 51.261,
#         "east":   0.280,
#         "north": 51.732,
#         # "crs": "EPSG:4326",  # optional, 4326 is the default
#     },
#     "temporal_extent": ["2020-01-01", "2021-12-31"],
#     "kernel_size": 71,   # optional — uses the UDP default (51)
#     # Note: CCI land cover year is fixed at UDP registration time (default 2018).
#     # To change it, update CCI_YEAR in uhi_udp_register.py and re-register.
# }

OUTPUT_FILE = r"C:\Users\adriaan.keurhorst\Documents\GTIF\uhi_jja_result_torino.tif"
JOB_TITLE   = "UHI_JJA_torino"

# Uncomment for other cities:
# PARAMETERS = {   # Paris
#     "spatial_extent": {"west": 2.273, "south": 48.819, "east": 2.413, "north": 48.897},
#     "temporal_extent": ["2018-01-01", "2023-12-31"],
# }
PARAMETERS = {   # Torino
    "spatial_extent": {"west": 7.546, "south": 44.989, "east": 7.781, "north": 45.145},
    "temporal_extent": ["2020-01-01", "2021-12-31"],
}

def run_uhi_udp(
    parameters: dict = PARAMETERS,
    output_file: str = OUTPUT_FILE,
    job_title: str   = JOB_TITLE,
) -> openeo.BatchJob:
    """
    Submit a batch job that runs the UHI_per_pixel UDP and downloads the result.

    Parameters
    ----------
    parameters  : dict
        Must contain at least ``spatial_extent`` and ``temporal_extent``.
        ``cci_year`` and ``kernel_size`` are optional (UDP defaults apply).
    output_file : str
        Local path for the downloaded GeoTIFF.
    job_title   : str
        Human-readable title shown in the back-end job manager.

    Returns
    -------
    openeo.BatchJob
        The completed batch job object.
    """
    connection = openeo.connect(OPENEO_URL).authenticate_oidc()

    # Load the stored UDP and supply runtime parameter values
    cube = connection.datacube_from_process(
        process_id=UDP_ID,
        namespace=r'https://openeo.dataspace.copernicus.eu/openeo/1.2/processes/u:776bee94-53de-49f5-88d6-c3660d927048/UHI_per_pixel',
        **parameters,
    )

    job = cube.execute_batch(
        outputfile=output_file,
        out_format="GTiff",
        title=job_title,
    )
    job.get_results().download_files(target=output_file.replace(".tif", ""))
    print(f"Results downloaded to '{output_file.replace('.tif', '')}/'")
    return job

run_uhi_udp()

