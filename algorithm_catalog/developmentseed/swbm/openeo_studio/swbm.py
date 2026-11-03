# Simple Water Bodies' Mapping (SWBM)
# Detects surface water with an OR-ensemble of three water indices
# (MNDWI, NDWI and SWI).
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/simple_water_bodies_mapping-swbm/
# Original author: Mohor Gartner
# License: CC-BY-SA-4.0
# Port of the openeo-udp "swbm" UDP. Deviation: the /10000 scaling is dropped
# (MPC reflectance is already 0-1); resample_spatial (20 m) is dropped.
from openeo.processes import or_


def swbm_visualization(data):
    """
    Input data array: [B02, B03, B04, B08, B11]

    MNDWI = (B03 - B11) / (B03 + B11)
    NDWI  = (B03 - B08) / (B03 + B08)
    SWI   = 1 / sqrt(B02 - B11)
    water = MNDWI > 0.1 OR NDWI > 0.2 OR SWI > 0.03

    Color mapping:
    - Water: blue (0, 0, 1)
    - Other pixels: true color with gain 2
    """
    B02, B03, B04, B08, B11 = (data[0], data[1], data[2], data[3], data[4])

    mndwi_thr = 0.1
    ndwi_thr = 0.2
    swi_thr = 0.03
    gain = 2

    mndwi = (B03 - B11) / (B03 + B11)
    ndwi = (B03 - B08) / (B03 + B08)
    swi = 1 / ((B02 - B11) ** 0.5)

    water = or_(or_(mndwi > mndwi_thr, ndwi > ndwi_thr), swi > swi_thr)

    red = if_(water, 0, gain * B04)
    green = if_(water, 0, gain * B03)
    blue = if_(water, 1, gain * B02)

    return array_create([red, green, blue])

# Apply SWBM on the data cube on the bands dimension
swbm_image = reduced.apply_dimension(dimension="bands", process=swbm_visualization)
# Linear scale to 0-255 for RGB visualization
swbm_image = swbm_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
swbm_image = swbm_image.save_result("PNG")

add_graph_to_map(swbm_image, "Water Bodies (SWBM)")
