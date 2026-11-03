# Atmospherically Resistant Vegetation Index (ARVI) Visualization
from openeo.processes import clip


def arvi_visualization(data):
    """
    Apply ARVI grayscale visualization.
    Input data array: [B02, B04, B8A]

    ARVI = (B8A - B04 - y * (B04 - B02)) / (B8A + B04 - y * (B04 - B02)), y = 0.106

    Color mapping (grayscale, 0 to 1):
    - Black: ARVI <= 0 (no or low vegetation)
    - Grey to white: ARVI 0.2 to 0.8 (denser vegetation is brighter)

    Deviation from the UDP: no division by 10000 (MPC reflectance is already 0-1).
    The UDP returns the raw index; here it is rendered as a grayscale RGB image.
    """
    B02, B04, B8A = data[0], data[1], data[2]

    atmospheric_correction = 0.106
    correction = atmospheric_correction * (B04 - B02)
    arvi = (B8A - B04 - correction) / (B8A + B04 - correction)

    gray = clip(arvi, 0, 1)
    return array_create([gray, gray, gray])

# Apply ARVI on the data cube on the bands dimension
arvi_image = reduced.apply_dimension(dimension="bands", process=arvi_visualization)
# Linear scale to 0-255 for RGB visualization
arvi_image = arvi_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
arvi_image = arvi_image.save_result("PNG")

add_graph_to_map(arvi_image, "ARVI")
