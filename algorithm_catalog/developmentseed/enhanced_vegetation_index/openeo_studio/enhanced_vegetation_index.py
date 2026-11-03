# Enhanced Vegetation Index 2 (EVI2) Visualization
def evi2_visualization(data):
    """
    Apply EVI2 visualization with a stepped color ramp.
    Input data array: [B08, B04]

    EVI2 = 2.4 * (B08 - B04) / (B08 + B04 + 1.0)

    Color mapping (Sentinel Hub EVI2 evalscript):
    - Black / light blue / grey: negative values (water, no vegetation)
    - Cream to khaki: bare soil and sparse vegetation
    - Light green to dark green: low to high vegetation signal

    Deviation from the UDP: no division by 10000 (MPC reflectance is already 0-1).
    """
    B08, B04 = data[0], data[1]

    evi2 = 2.4 * (B08 - B04) / (B08 + B04 + 1.0)

    # (upper threshold, color): a pixel takes the color of the first
    # threshold that is greater than its value.
    stops = [
        (-1.1, [0, 0, 0]),
        (-0.2, [0.75, 0.75, 1]),
        (-0.1, [0.86, 0.86, 0.86]),
        (0.0, [1, 1, 0.88]),
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
    last_color = [0, 0.27, 0]

    # Create spatial ones for constant colors
    spatial_ones = evi2 * 0 + 1

    channels = []
    for c in range(3):
        channel = spatial_ones * last_color[c]
        # Build the chain from the highest threshold back to the lowest
        for threshold, color in reversed(stops):
            channel = if_(evi2 < threshold, spatial_ones * color[c], channel)
        channels.append(channel)

    return array_create(channels)

# Apply EVI2 on the data cube on the bands dimension
evi_image = reduced.apply_dimension(dimension="bands", process=evi2_visualization)
# Linear scale to 0-255 for RGB visualization
evi_image = evi_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
evi_image = evi_image.save_result("PNG")

add_graph_to_map(evi_image, "EVI2")
