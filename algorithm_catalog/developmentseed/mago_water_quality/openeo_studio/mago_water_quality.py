# MAGO Water Quality Monitoring Tool
# Estimates a water-quality indicator for lakes, reservoirs and large ponds
# and shows it with a Blue -> Cyan -> Green -> Yellow -> Red color scale.
# Non-water pixels (NDWI < 0) are shown in true color.
#
# Reference: MAGO Water Quality Monitoring Tool (Sentinel Hub custom script)
# License: CC-BY-SA-4.0
# Port of the openeo-udp "mago_water_quality" UDP. Deviations:
# - the /10000 scaling is dropped (MPC reflectance is already 0-1);
# - the UDP runtime parameters (indicator, min_value, max_value) are Python
#   constants below. Only the selected indicator is put in the process graph.
from openeo.processes import log, process

# Indicator to compute (UDP default: 0):
# 0 = Chl-a NDCI (mg/m3), 1 = Chl-a high (mg/m3), 2 = Chl-a low (mg/m3),
# 3 = Cyanobacteria (cells/mL), 4 = Cyanobacteria (mg/m3),
# 5 = Turbidity (NTU), 6 = CDOM (ug/L), 7 = TSS (mg/L)
INDICATOR = 0
# Color scale bounds (Blue at MIN_VALUE, Red at MAX_VALUE)
MIN_VALUE = 6
MAX_VALUE = 12


def mago_visualization(data):
    """
    Input data array: [B02, B03, B04, B05, B07, B08]

    NDWI = (B03 - B08) / (B03 + B08); NDWI < 0 -> true color (gain 3)
    Indicators:
    0: 14.039 + 86.11 * NDCI + 194.325 * NDCI^2, NDCI = (B05 - B04) / (B05 + B04)
    1: 19.866 * (B05 / B04)^2.3051
    2: 10^(-2.4792 * log10(max(B03, B02) / B03) - 0.0389)
    3: 115530.31 * ((B03 * B04) / B02^2)^2.38
    4: 21.554 * (B05 / B04)^3.4791
    5: 194.79 * (B05 * (B05 / B02)) + 0.9061
    6: 2.4072 * (B04 / B02) + 0.0709
    7: 14.464 * (B07 / B02) + 16.336
    t = (value - MIN_VALUE) / (MAX_VALUE - MIN_VALUE) -> 5-stop color scale
    """
    B02, B03, B04, B05, B07, B08 = (
        data[0],
        data[1],
        data[2],
        data[3],
        data[4],
        data[5],
    )

    def chl_ndci():
        ndci = (B05 - B04) / (B05 + B04)
        return 14.039 + 86.11 * ndci + 194.325 * ndci ** 2

    def chl_low():
        max_b03_b02 = if_(B03 > B02, B03, B02)
        exponent = -2.4792 * log(max_b03_b02 / B03, 10) - 0.0389
        return process("power", base=10, p=exponent)

    indicators = {
        0: chl_ndci,
        1: lambda: 19.866 * (B05 / B04) ** 2.3051,
        2: chl_low,
        3: lambda: 115530.31 * ((B03 * B04) / B02 ** 2) ** 2.38,
        4: lambda: 21.554 * (B05 / B04) ** 3.4791,
        5: lambda: 194.79 * (B05 * (B05 / B02)) + 0.9061,
        6: lambda: 2.4072 * (B04 / B02) + 0.0709,
        7: lambda: 14.464 * (B07 / B02) + 16.336,
    }
    value = indicators[INDICATOR]()

    t = (value - MIN_VALUE) / (MAX_VALUE - MIN_VALUE)

    # Blue (t<=0) -> Cyan (0.25) -> Green (0.5) -> Yellow (0.75) -> Red (t>=1)
    red = if_(
        t < 0,
        0,
        if_(t > 1, 1, if_(t <= 0.5, 0, if_(t <= 0.75, (t - 0.5) * 4, 1))),
    )
    green = if_(
        t < 0,
        0,
        if_(t > 1, 0, if_(t <= 0.25, t * 4, if_(t <= 0.75, 1, 1 - (t - 0.75) * 4))),
    )
    blue = if_(
        t < 0,
        1,
        if_(t > 1, 0, if_(t <= 0.25, 1, if_(t <= 0.5, 1 - (t - 0.25) * 4, 0))),
    )
    water_color = array_create([red, green, blue])

    land_color = array_create([B04 * 3, B03 * 3, B02 * 3])

    ndwi = (B03 - B08) / (B03 + B08)

    return if_(ndwi < 0, land_color, water_color)

# Apply MAGO on the data cube on the bands dimension
mago_image = reduced.apply_dimension(dimension="bands", process=mago_visualization)
# Linear scale to 0-255 for RGB visualization
mago_image = mago_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
mago_image = mago_image.save_result("PNG")

add_graph_to_map(mago_image, "MAGO Water Quality (Chlorophyll-a)")
