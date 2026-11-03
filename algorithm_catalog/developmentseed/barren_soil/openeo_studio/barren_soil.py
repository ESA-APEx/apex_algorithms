# Barren Soil Index (BSI) Visualization
from openeo.processes import clip


def barren_soil_visualization(data):
    """
    Apply Barren Soil visualization (BSI on red, NIR on green, SWIR on blue).
    Input data array: [B02, B04, B08, B11]

    BSI = ((B11 + B04) - (B08 + B02)) / ((B11 + B04) + (B08 + B02))

    Color mapping:
    - Red channel: 2.5 * BSI (brightness 2.5, UDP default)
    - Green channel: B08
    - Blue channel: B11
    Barren ground shows in red, vegetation shows in green.

    Deviation from the UDP: no division by 10000 (MPC reflectance is already 0-1).
    The UDP "brightness" parameter is fixed to its default (2.5).
    """
    B02, B04, B08, B11 = data[0], data[1], data[2], data[3]

    brightness = 2.5
    bsi = ((B11 + B04) - (B08 + B02)) / ((B11 + B04) + (B08 + B02))

    return array_create([
        clip(brightness * bsi, 0, 1),
        clip(B08, 0, 1),
        clip(B11, 0, 1),
    ])

# Apply Barren Soil on the data cube on the bands dimension
barren_soil_image = reduced.apply_dimension(
    dimension="bands", process=barren_soil_visualization
)
# Linear scale to 0-255 for RGB visualization
barren_soil_image = barren_soil_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
barren_soil_image = barren_soil_image.save_result("PNG")

add_graph_to_map(barren_soil_image, "Barren Soil")
