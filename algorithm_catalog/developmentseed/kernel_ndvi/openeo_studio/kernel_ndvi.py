# Kernel NDVI (kNDVI) Visualization
from openeo.processes import tanh


def kndvi_visualization(data):
    """
    Apply kNDVI visualization with a stepped vegetation color ramp and
    Scene Classification Layer (SCL) colors for non-vegetation pixels.
    Input data array: [B04, B08, SCL]

    NDVI = (B08 - B04) / (B08 + B04)
    kNDVI = tanh(NDVI^2)

    Color mapping:
    - SCL 4 (vegetation) and 5 (not vegetated): kNDVI ramp,
      cream (low) -> yellow-green -> dark green (high)
    - Other SCL classes: fixed colors (black no data, red defective,
      dark grey topographic shadow, brown cloud shadow, blue water,
      grey unclassified, grey/white clouds, light blue cirrus, cyan snow)

    Deviation from the UDP: no division by 10000 (MPC reflectance is already 0-1).
    """
    B04, B08, SCL = data[0], data[1], data[2]

    ndvi = (B08 - B04) / (B08 + B04)
    kndvi = tanh(ndvi * ndvi)

    # (upper threshold, color): a pixel takes the color of the first
    # threshold that is greater than its value.
    kndvi_ramp = [
        (-1.1, [0, 0, 0]),
        (-0.2, [0.75, 0.75, 0.75]),
        (-0.1, [0.86, 0.86, 0.86]),
        (0, [1, 1, 0.88]),
        (0.025, [1, 0.98, 0.8]),
        (0.05, [0.93, 0.91, 0.71]),
        (0.075, [0.87, 0.85, 0.61]),
        (0.1, [0.8, 0.78, 0.51]),
        (0.125, [0.74, 0.72, 0.42]),
        (0.15, [0.69, 0.76, 0.38]),
        (0.175, [0.64, 0.8, 0.35]),
        (0.2, [0.57, 0.75, 0.32]),
        (0.25, [0.5, 0.7, 0.28]),
        (0.3, [0.44, 0.64, 0.25]),
        (0.35, [0.38, 0.59, 0.21]),
        (0.4, [0.31, 0.54, 0.18]),
        (0.45, [0.25, 0.49, 0.14]),
        (0.5, [0.19, 0.43, 0.11]),
        (0.55, [0.13, 0.38, 0.07]),
        (0.6, [0.06, 0.33, 0.04]),
    ]
    base_color = [0, 0.27, 0]

    # SCL class -> color (classes 4 and 5 keep the kNDVI ramp)
    scl_palette = [
        (0, [0, 0, 0]),  # No data - black
        (1, [1, 0, 0.016]),  # Saturated or defective - red
        (2, [0.525, 0.525, 0.525]),  # Topographic shadow - dark grey
        (3, [0.467, 0.298, 0.043]),  # Cloud shadow - dark brown
        (6, [0, 0, 1]),  # Water - blue
        (7, [0.506, 0.506, 0.506]),  # Unclassified - dark grey
        (8, [0.753, 0.753, 0.753]),  # Cloud medium probability - grey
        (9, [0.949, 0.949, 0.949]),  # Cloud high probability - white
        (10, [0.733, 0.773, 0.925]),  # Thin cirrus - very bright blue
        (11, [0.325, 1, 0.980]),  # Snow or ice - cyan
    ]

    # Create spatial ones for constant colors
    spatial_ones = B04 * 0 + 1

    channels = []
    for c in range(3):
        channel = spatial_ones * base_color[c]
        # kNDVI ramp, built from the highest threshold back to the lowest
        for threshold, color in reversed(kndvi_ramp):
            channel = if_(kndvi < threshold, spatial_ones * color[c], channel)
        # Override non-vegetation SCL classes with their palette color
        for scl_class, color in reversed(scl_palette):
            channel = if_(SCL == scl_class, spatial_ones * color[c], channel)
        channels.append(channel)

    return array_create(channels)

# Apply kNDVI on the data cube on the bands dimension
kndvi_image = reduced.apply_dimension(dimension="bands", process=kndvi_visualization)
# Linear scale to 0-255 for RGB visualization
kndvi_image = kndvi_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
kndvi_image = kndvi_image.save_result("PNG")

add_graph_to_map(kndvi_image, "Kernel NDVI")
