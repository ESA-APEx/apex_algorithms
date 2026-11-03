# Plant Senescence Reflectance Index (PSRI) Visualization
def psri_visualization(data):
    """
    Apply PSRI visualization with a reversed red-yellow-green color ramp.
    Input data array: [B02, B04, B06]

    PSRI = (B04 - B02) / B06   (1.0 where B06 <= 0)

    The index goes through Sentinel Hub's HighlightCompressVisualizer
    (min = -0.2, max = 0.4):
    - [-0.2, 0.4] maps linearly to [0, 0.9259]
    - [0.4, 1.0] maps linearly to [0.9259, 1]
    - below -0.2 -> 0, above 1.0 -> 1

    Color mapping (matplotlib RdYlGn_r, as in the notebook color figure):
    - Green: healthy vegetation (PSRI < 0)
    - Yellow: moderate stress (PSRI 0 to 0.2)
    - Red: severe stress, senescence or burned surface (PSRI > 0.2)

    Deviation from the UDP: no division by 10000 (MPC reflectance is already 0-1).
    The UDP returns the single compressed band (grayscale); here the notebook
    RdYlGn_r color map is applied to that band.
    """
    B02, B04, B06 = data[0], data[1], data[2]

    min_value = -0.2
    max_value = 0.4
    highlight_start_output = 0.9259
    highlight_end = 2 * max_value - min_value
    fast_slope = highlight_start_output / (max_value - min_value)
    compressed_slope = (1.0 - highlight_start_output) / (highlight_end - max_value)

    psri = if_(B06 > 0, (B04 - B02) / B06, highlight_end)

    # HighlightCompressVisualizer -> value in [0, 1]
    val = if_(
        psri <= min_value,
        0.0,
        if_(
            psri <= max_value,
            fast_slope * (psri - min_value),
            if_(
                psri <= highlight_end,
                highlight_start_output + compressed_slope * (psri - max_value),
                1.0,
            ),
        ),
    )

    # RdYlGn_r (ColorBrewer RdYlGn, 11 classes, reversed)
    stops = [
        (0.0, [0, 104, 55]),
        (0.1, [26, 152, 80]),
        (0.2, [102, 189, 99]),
        (0.3, [166, 217, 106]),
        (0.4, [217, 239, 139]),
        (0.5, [255, 255, 191]),
        (0.6, [254, 224, 139]),
        (0.7, [253, 174, 97]),
        (0.8, [244, 109, 67]),
        (0.9, [215, 48, 39]),
        (1.0, [165, 0, 38]),
    ]

    # Create spatial ones for constant colors
    spatial_ones = val * 0 + 1

    channels = []
    for c in range(3):
        channel = spatial_ones * (stops[-1][1][c] / 255)
        # Piecewise linear interpolation, built from the top segment down
        for (v0, c0), (v1, c1) in reversed(list(zip(stops[:-1], stops[1:]))):
            t = (val - v0) / (v1 - v0)
            interpolated = c0[c] / 255 + (c1[c] - c0[c]) / 255 * t
            channel = if_(val < v1, interpolated, channel)
        channels.append(channel)

    return array_create(channels)

# Apply PSRI on the data cube on the bands dimension
psri_image = reduced.apply_dimension(dimension="bands", process=psri_visualization)
# Linear scale to 0-255 for RGB visualization
psri_image = psri_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
psri_image = psri_image.save_result("PNG")

add_graph_to_map(psri_image, "PSRI")
