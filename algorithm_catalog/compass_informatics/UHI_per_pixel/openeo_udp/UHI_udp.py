"""
uhi_udp_register.py
====================
Builds and stores the Urban Heat Island (UHI) User-Defined Process (UDP)
on the Copernicus OpenEO back-end.

Usage
-----
    python uhi_udp_register.py

The UDP will be saved under the process id "UHI_per_pixel" in your account.
"""

import numpy as np
import openeo
from openeo.api.process import Parameter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LANDSAT_STAC = (
    "https://planetarycomputer.microsoft.com/api/stac/v1/collections/landsat-c2-l2"
)
CCI_STAC = (
    "https://planetarycomputer.microsoft.com/api/stac/v1/collections/esa-cci-lc"
)
CCI_URBAN_CLASS  = 190  # ESA CCI LCCS class for artificial / urban surfaces
MAX_CLOUD_COVER  = 5    # %
DEFAULT_KERNEL   = 51   # pixels  (~1.5 km radius at 30 m Landsat resolution)
UDP_ID           = "UHI_per_pixel"

# JJA intervals are pre-built for this range at registration time.
# Extend YEAR_RANGE_END if you need to process data beyond 2035.
YEAR_RANGE_START = 1985
YEAR_RANGE_END   = 2035

# CCI land cover year — fixed at registration time because load_stac cannot
# accept a runtime Parameter as a temporal_extent value (causes ValueError).
# Change this constant and re-register if you need a different CCI snapshot.
CCI_YEAR = 2018


# ---------------------------------------------------------------------------
# Build the parameterised process graph
# ---------------------------------------------------------------------------

def build_uhi_graph(
    connection: openeo.Connection,
    spatial_extent: Parameter,
    temporal_extent: Parameter,
    kernel_size: Parameter,
) -> openeo.DataCube:
    """
    Construct the symbolic UHI process graph.

    spatial_extent, temporal_extent, and kernel_size are Parameter objects;
    the openEO client serialises them as ``{"from_parameter": "<n>"}`` nodes.
    CCI year is baked in at registration time via the CCI_YEAR constant.

    Returns the final (result) DataCube node.
    """

    # ------------------------------------------------------------------
    # 1.  Load Landsat TIRS B10 for the requested AOI + time window
    # ------------------------------------------------------------------
    landsat_cube = connection.load_stac(
        LANDSAT_STAC,
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        bands=["TIRS_B10"],
        properties={"eo:cloud_cover": lambda v: v <= MAX_CLOUD_COVER},
    )

    # Scale DN → °C  (Landsat Collection-2 scale + offset, then K→°C)
    lst_raw = landsat_cube.band("TIRS_B10") * 0.00341802 + 149.0 - 273.15

    # ------------------------------------------------------------------
    # 2.  JJA mean across all years in the temporal extent
    #
    #     We cannot loop over a runtime Parameter to build per-year
    #     intervals dynamically, so instead we pre-build JJA intervals
    #     for a wide year range (YEAR_RANGE_START–YEAR_RANGE_END) at
    #     UDP registration time.  The temporal_extent parameter already
    #     limits which Landsat scenes are loaded, so intervals that fall
    #     outside that window simply contribute no data and are ignored
    #     by the reducer.
    # ------------------------------------------------------------------
    jja_intervals = [
        [f"{y}-06-01", f"{y}-09-01"]   # left-closed, right-open → Jun/Jul/Aug
        for y in range(YEAR_RANGE_START, YEAR_RANGE_END + 1)
    ]

    lst = lst_raw.aggregate_temporal(
        intervals=jja_intervals,
        reducer="mean",
    ).reduce_temporal(reducer="mean")

    # ------------------------------------------------------------------
    # 3.  Load ESA CCI land cover for the requested year
    # ------------------------------------------------------------------
    cci_raw = connection.load_stac(
        CCI_STAC,
        spatial_extent=spatial_extent,
        temporal_extent=[f"{CCI_YEAR}-01-01", f"{CCI_YEAR}-12-31"],
        bands=["lccs_class"],
    )
    cci = cci_raw.reduce_temporal(reducer="first").resample_cube_spatial(lst)

    # ------------------------------------------------------------------
    # 4.  Urban / rural masks
    #     CCI class 190 = Urban / artificial surfaces
    # ------------------------------------------------------------------
    urban_mask = cci != CCI_URBAN_CLASS   # True  → urban
    rural_mask = cci == CCI_URBAN_CLASS   # True  → rural

    rural_indicator = rural_mask * 1      # 1 = rural, 0 = urban

    # ------------------------------------------------------------------
    # 5.  Rural-only LST  (urban pixels → 0)
    # ------------------------------------------------------------------
    rural_temp_zero = lst * rural_indicator

    # ------------------------------------------------------------------
    # 6.  Moving-window local rural mean
    #     We cannot build a Python list from a runtime Parameter, so we
    #     use apply_kernel with a flat unit kernel whose size is fixed at
    #     registration time.  If you need a dynamic kernel size at
    #     runtime, register separate UDPs or use apply_neighborhood.
    # ------------------------------------------------------------------
    kernel = [[1] * DEFAULT_KERNEL for _ in range(DEFAULT_KERNEL)]

    rural_sum   = rural_temp_zero.apply_kernel(kernel=kernel, factor=1, border=0)
    rural_count = rural_indicator.apply_kernel(kernel=kernel, factor=1, border=0)

    local_rural_mean = rural_sum / rural_count
    local_rural_mean = local_rural_mean.mask(rural_count == 0)

    # ------------------------------------------------------------------
    # 7.  UHI = LST − local rural mean, clipped to urban pixels only
    # ------------------------------------------------------------------
    local_uhi       = lst - local_rural_mean
    local_uhi_urban = local_uhi.mask(urban_mask)

    return local_uhi_urban


# ---------------------------------------------------------------------------
# Register the UDP
# ---------------------------------------------------------------------------

def register_udp() -> None:
    connection = openeo.connect(
        "https://openeo.dataspace.copernicus.eu/openeo/1.2"
    ).authenticate_oidc()

    # --- Declare parameters ------------------------------------------------
    spatial_extent = Parameter.spatial_extent(
        name="spatial_extent",
        description=(
            "Bounding box of the area of interest as an object with "
            "'west', 'south', 'east', 'north' keys (EPSG:4326)."
        ),
    )

    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent",
        description=(
            "Date range over which to compute the JJA mean LST, "
            "e.g. ['2015-01-01', '2024-12-31'].  "
            "All June-August periods within the range are averaged."
        ),
        # schema={"type": "array", "subtype": "temporal-interval"},
        default=["2018-01-01", "2023-12-31"],
    )

    kernel_size = Parameter.integer(
        name="kernel_size",
        description=(
            "Side length (pixels) of the square moving-window kernel "
            "used to estimate the local rural background temperature.  "
            "Must be odd.  At 30 m Landsat resolution, 51 ≈ 1.5 km radius.  "
            "NOTE: the kernel is fixed at registration time (default 51).  "
            "Re-register with a different DEFAULT_KERNEL constant to change it."
        ),
        default=DEFAULT_KERNEL,
    )

    # --- Build graph -------------------------------------------------------
    result_cube = build_uhi_graph(
        connection,
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        kernel_size=kernel_size,
    )

    # --- Store on the back-end ---------------------------------------------
    udp = connection.save_user_defined_process(
        user_defined_process_id=UDP_ID,
        process_graph=result_cube,
        parameters=[spatial_extent, temporal_extent, kernel_size],
        summary="Urban Heat Island intensity (JJA mean LST - local rural background)",
        description=(
            "Computes per-pixel Urban Heat Island (UHI) intensity for a given "
            "area and time period using Landsat 8/9 TIRS Band 10 Land Surface "
            "Temperature (LST) and ESA CCI land cover.\n\n"
            "Algorithm:\n"
            "  1. Load Landsat TIRS B10, convert to °C.\n"
            "  2. Aggregate to JJA (June-August) mean across all years in the "
            "     requested temporal extent.\n"
            "  3. Load ESA CCI land cover; resample to LST grid.\n"
            "  4. Separate urban (CCI=190) and rural pixels.\n"
            "  5. Compute local rural mean LST with a moving-window kernel.\n"
            "  6. UHI = LST_urban - local_rural_mean  (urban pixels only).\n"
        ),
        public=True,  # set True to share with other users
    )

    print(f"UDP '{UDP_ID}' successfully registered.")
    print(udp.describe())


if __name__ == "__main__":
    register_udp()