# Snow Classifier
# Detects snow with NDSI as the primary indicator. Pixels with a lower NDSI
# are also snow when their NDVI is near 0.1. All snow pixels must be bright
# in the green band.
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/snow_classifier/
# License: CC-BY-SA-4.0
# Port of the openeo-udp "snow_classifier" UDP. Deviation: the /10000 scaling
# is dropped (MPC reflectance is already 0-1); resample_spatial (20 m) is dropped.
def snow_classifier(data):
    """
    Input data array: [B02, B03, B04, B08, B11]

    NDSI = (B03 - B11) / (B03 + B11)
    NDVI = (B08 - B04) / (B08 + B04)
    snow = (NDSI >= 0.4 OR |NDVI - 0.1| <= 0.025) AND B03 > 0.3

    Color mapping:
    - Snow: light beige (1.0, 0.8, 0.4)
    - Other pixels: true color with gain 2.5
    """
    B02, B03, B04, B08, B11 = (data[0], data[1], data[2], data[3], data[4])

    ndsi_threshold = 0.4
    gain = 2.5

    ndsi = (B03 - B11) / (B03 + B11)
    ndvi = (B08 - B04) / (B08 + B04)

    ndvi_flag = if_(absolute(ndvi - 0.1) <= 0.025, 1, 0)
    is_snow = if_(ndsi >= ndsi_threshold, 1, ndvi_flag)
    snow = and_(is_snow, B03 > 0.3)

    red = if_(snow, 1.0, gain * B04)
    green = if_(snow, 0.8, gain * B03)
    blue = if_(snow, 0.4, gain * B02)

    return array_create([red, green, blue])

# Apply the snow classifier on the data cube on the bands dimension
snow_image = reduced.apply_dimension(dimension="bands", process=snow_classifier)
# Linear scale to 0-255 for RGB visualization
snow_image = snow_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
snow_image = snow_image.save_result("PNG")

add_graph_to_map(snow_image, "Snow Classification")
