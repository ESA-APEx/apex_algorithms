# Fire Boundary Visualization
def fire_boundary_visualization(data):
    """
    Apply Fire Boundary grayscale visualization.
    Input data array: [B11, B12]

    coefficient = 8.5 * (B12 - B11) / (B12 + B11 + 0.25)

    The coefficient goes through Sentinel Hub's HighlightCompressVisualizer
    (min = -1, max = 1):
    - [-1, 1] maps linearly to [0, 0.9259] (black -> light grey, no active fire)
    - [1, 3] maps linearly to [0.9259, 1] (light grey -> white, active fire)
    - below -1 -> 0, above 3 -> 1

    Deviation from the UDP: no division by 10000 (MPC reflectance is already 0-1).
    The UDP returns one band; here it is repeated on R, G and B.
    """
    B11, B12 = data[0], data[1]

    coefficient = 8.5 * (B12 - B11) / (B12 + B11 + 0.25)

    min_value = -1.0
    max_value = 1.0
    breakpoint_output = 0.9259
    max_input = 2 * max_value - min_value
    slope_linear = breakpoint_output / (max_value - min_value)
    slope_compressed = (1.0 - breakpoint_output) / (max_input - max_value)

    gray = if_(
        coefficient <= min_value,
        0.0,
        if_(
            coefficient <= max_value,
            slope_linear * (coefficient - min_value),
            if_(
                coefficient <= max_input,
                breakpoint_output + slope_compressed * (coefficient - max_value),
                1.0,
            ),
        ),
    )

    return array_create([gray, gray, gray])

# Apply Fire Boundary on the data cube on the bands dimension
fire_boundary_image = reduced.apply_dimension(
    dimension="bands", process=fire_boundary_visualization
)
# Linear scale to 0-255 for RGB visualization
fire_boundary_image = fire_boundary_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
fire_boundary_image = fire_boundary_image.save_result("PNG")

add_graph_to_map(fire_boundary_image, "Fire Boundary")
