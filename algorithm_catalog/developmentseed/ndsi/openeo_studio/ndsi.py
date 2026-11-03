# Normalized Difference Snow Index (NDSI)
# Detects snow from the contrast between green (high snow reflectance)
# and SWIR (strong snow absorption) bands.
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/ndsi/
# License: CC-BY-SA-4.0
# Port of the openeo-udp "ndsi" UDP. Deviation: the /10000 scaling is dropped
# (MPC reflectance is already 0-1); resample_spatial (60 m) is dropped.
def ndsi_visualization(data):
    """
    Input data array: [B02, B03, B04, B11]

    NDSI = (B03 - B11) / (B03 + B11)

    Color mapping:
    - Snow (NDSI > 0.42): blue (0, 0.8, 1)
    - Other pixels: true color with gain 2.5
    """
    B02, B03, B04, B11 = (data[0], data[1], data[2], data[3])

    ndsi_threshold = 0.42
    gain = 2.5

    ndsi = (B03 - B11) / (B03 + B11)
    snow = ndsi > ndsi_threshold

    red = if_(snow, 0, gain * B04)
    green = if_(snow, 0.8, gain * B03)
    blue = if_(snow, 1, gain * B02)

    return array_create([red, green, blue])

# Apply NDSI on the data cube on the bands dimension
ndsi_image = reduced.apply_dimension(dimension="bands", process=ndsi_visualization)
# Linear scale to 0-255 for RGB visualization
ndsi_image = ndsi_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
ndsi_image = ndsi_image.save_result("PNG")

add_graph_to_map(ndsi_image, "NDSI Snow")
