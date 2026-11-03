# Hollstein Cloud Detection
# Classifies clear sky, shadow, water, cirrus, cloud and snow with the
# Hollstein et al. (2016) decision tree (L2A / titiler variant).
#
# Reference: https://custom-scripts.sentinel-hub.com/sentinel-2/hollstein/
# Citation: Hollstein et al. (2016), Remote Sensing 8(8):666
# License: CC-BY-SA-4.0
def hollstein_cloud_detection(data):
    """
    Apply the Hollstein decision tree and color each class.
    Input data array: [B01, B02, B03, B04, B05, B06, B07, B8A, B09, B11]

    Reflectance is 0-1 (MPC applies scale/offset), so the UDP's
    division by 10000 is not necessary.

    The original algorithm uses the cirrus band B10, which is not in L2A.
    As in the UDP, two tests use blue/SWIR proxies:
    - B02 < 0.2 replaces (B02 / B10) < 14.689
    - B11 < 0.3 replaces (B11 - B10) < 0.255

    Color mapping:
    - Natural color (gain 2.5): clear sky and shadow
    - Dark blue: water
    - Red: cirrus
    - Blue: cloud
    - Yellow: snow
    """
    B01, B02, B03, B04, B05, B06, B07, B8A, B09, B11 = (
        data[0],
        data[1],
        data[2],
        data[3],
        data[4],
        data[5],
        data[6],
        data[7],
        data[8],
        data[9],
    )

    gain = 2.5

    # Enhanced natural color for clear and shadow pixels (same in the UDP)
    clear = array_create([B04 * gain, B03 * gain, B02 * gain])
    shadow = array_create([B04 * gain, B03 * gain, B02 * gain])

    # Create spatial ones for constant colors
    spatial_ones = B04 * 0 + 1

    water = array_create([spatial_ones * 0.1, spatial_ones * 0.1, spatial_ones * 0.7])
    cirrus = array_create([spatial_ones * 0.8, spatial_ones * 0.1, spatial_ones * 0.1])
    cloud = array_create([spatial_ones * 0.3, spatial_ones * 0.3, spatial_ones * 1.0])
    snow = array_create([spatial_ones * 1.0, spatial_ones * 0.8, spatial_ones * 0.4])

    result = if_(
        B03 < 0.319,
        if_(
            B8A < 0.166,
            if_(
                (B03 - B07) < 0.027,
                if_((B09 - B11) < -0.097, clear, shadow),
                if_((B09 - B11) < 0.021, water, shadow),
            ),
            if_(
                B02 < 0.2,  # proxy for (B02 / B10) < 14.689
                if_((B02 / B09) < 0.788, clear, cirrus),
                clear,
            ),
        ),
        if_(
            (B05 / B11) < 4.330,
            if_(
                B11 < 0.3,  # proxy for (B11 - B10) < 0.255
                if_((B06 - B07) < -0.016, cloud, cirrus),
                if_(B01 < 0.300, clear, cloud),
            ),
            if_(B03 < 0.525, if_((B01 / B05) < 1.184, clear, shadow), snow),
        ),
    )
    return result


# Apply the decision tree on the bands dimension
hollstein_image = reduced.apply_dimension(dimension="bands", process=hollstein_cloud_detection)
# Linear scale to 0-255 for RGB visualization (values above 1 are clipped)
hollstein_image = hollstein_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
hollstein_image = hollstein_image.save_result("PNG")

add_graph_to_map(hollstein_image, "Hollstein Cloud Classification")
