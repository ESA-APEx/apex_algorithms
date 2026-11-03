# Wildfire Visualization (burn scars)
# Natural color base map with burn scars highlighted by the
# Normalized Burn Ratio (NBR).
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/markuse_fire/
# Author: Pierre Markuse (QuickFire 1.0)
# License: CC-BY-SA-4.0
from openeo.processes import sqrt


def wildfire_visualization(data):
    """
    Apply the wildfire burn scar visualization.
    Input data array: [B02, B03, B04, B08, B12]

    Base map (color corrected natural color):
        R = sqrt(B04), G = sqrt(B03), B = sqrt(B02)

    Burn scars:
        NBR = (B08 - B12) / (B08 + B12)
        If NBR < -0.25, add 0.3 to the red and green channels.

    This is the configuration of the UDP (hotspot = 0, showBurnScars = 1).
    Reflectance is 0-1 (MPC applies scale/offset), so the UDP's
    division by 10000 is not necessary. The UDP loads B11, but the
    burn scar mode does not use it, so this script does not load it.
    """
    B02, B03, B04, B08, B12 = (
        data[0],
        data[1],
        data[2],
        data[3],
        data[4],
    )

    # Image brightness and contrast
    brightness = 1.0
    offset = 0.0

    # Threshold and strength for burn scars
    burn_scar_threshold = -0.25
    burn_scar_strength = 0.3

    # True colors with color correction
    base_r = sqrt(brightness * B04 + offset)
    base_g = sqrt(brightness * B03 + offset)
    base_b = sqrt(brightness * B02 + offset)

    # Normalized Burn Ratio
    nbr = (B08 - B12) / (B08 + B12)
    burn_scar = nbr < burn_scar_threshold

    result = array_create([
        if_(burn_scar, base_r + burn_scar_strength, base_r),
        if_(burn_scar, base_g + burn_scar_strength, base_g),
        base_b,
    ])
    return result


# Apply the visualization on the bands dimension
wildfire_image = reduced.apply_dimension(dimension="bands", process=wildfire_visualization)
# Linear scale to 0-255 for RGB visualization (values above 1 are clipped)
wildfire_image = wildfire_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
wildfire_image = wildfire_image.save_result("PNG")

add_graph_to_map(wildfire_image, "Wildfire Burn Scars")
