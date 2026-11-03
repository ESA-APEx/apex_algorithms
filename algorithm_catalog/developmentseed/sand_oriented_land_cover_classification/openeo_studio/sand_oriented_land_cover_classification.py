# Sand-Oriented Land Cover Classification (Sentinel-2 + Sentinel-1)
# Classes, from the highest priority:
# - urban (VH or VV backscatter > 0.2): white
# - sparse vegetation (0.2 < NDVI < 0.4): yellow
# - dense vegetation (NDVI >= 0.4): green
# - water ((B03 - B12) / (B03 + B12) > 0 and VH < 0.015): blue
# - bare soil (BSI > 0.2): red
# - sand ((B04 - B02) / (B04 + B02) > 0.1): orange
# - other: black
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/data-fusion/sand_oriented_land_cover_classification/
# License: CC-BY-SA-4.0
# Port of the openeo-udp "sand_oriented_land_cover_classification" UDP.
# Deviations:
# - the /10000 scaling is dropped (MPC reflectance is already 0-1);
# - Planetary Computer has no geocoded Sentinel-1 GRD, so VH and VV come from
#   sentinel-1-rtc (terrain-corrected gamma0, linear power) instead of the
#   CDSE SENTINEL1_GRD backscatter. They are loaded here, for the project
#   area and dates.
#
# Input bands (Sentinel-2), in this order: B02, B03, B04, B08, B11, B12
from openeo.processes import and_, or_

# The band dimension of this backend ("bands", "spectral", ...).
DIM = metadata.band_dimension.name if metadata else "bands"

s2 = datacube.reduce_dimension(dimension="t", reducer="mean")
s1 = DataCube(graph=PGNode(
    "load_collection",
    id="sentinel-1-rtc",
    spatial_extent=bounding_box,
    temporal_extent=time,
    bands=["vh", "vv"],
))
s1 = s1.reduce_dimension(dimension="t", reducer="mean").resample_cube_spatial(target=s2, method="near")


def land_cover(data):
    """Input: [B02, B03, B04, B08, B11, B12, VH, VV]"""
    B02, B03, B04, B08, B11, B12 = data[0], data[1], data[2], data[3], data[4], data[5]
    VH, VV = data[6], data[7]

    ndvi = (B08 - B04) / (B08 + B04)
    bsi = ((B11 + B04) - (B08 + B02)) / ((B11 + B04) + (B08 + B02))

    # (condition, color), from the lowest priority to the highest
    classes = [
        ((B04 - B02) / (B04 + B02) > 0.1, [1.0, 0.65, 0.0]),  # sand
        (bsi > 0.2, [0.75, 0.0, 0.0]),  # bare soil
        (and_((B03 - B12) / (B03 + B12) > 0, VH < 0.015), [0.0, 0.0, 0.75]),  # water
        (ndvi >= 0.4, [0.2, 0.75, 0.0]),  # dense vegetation
        (and_(ndvi > 0.2, ndvi < 0.4), [0.9, 0.9, 0.0]),  # sparse vegetation
        (or_(VH > 0.2, VV > 0.2), [1.0, 1.0, 1.0]),  # urban
    ]

    channels = []
    for c in range(3):
        channel = B02 * 0  # other: black
        for condition, color in classes:
            channel = if_(condition, color[c], channel)
        channels.append(channel)
    return array_create(channels)


classification = s2.merge_cubes(s1).apply_dimension(dimension=DIM, process=land_cover)
classification = classification.linear_scale_range(0, 1, 0, 255)

add_graph_to_map(classification.save_result("PNG"), "Sand-Oriented Land Cover")
