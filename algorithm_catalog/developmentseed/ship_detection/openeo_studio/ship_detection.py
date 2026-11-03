# Ship Detection (Sentinel-2 + Sentinel-1)
# Ships: bright Sentinel-1 VV or VH backscatter (> 0.3) on water
# (Sentinel-2 NDWI > 0.1), in white over a Sentinel-2 true-colour background.
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/data-fusion/ship_detection/
# License: CC-BY-SA-4.0
# Port of the openeo-udp "ship_detection" UDP. Deviations:
# - Planetary Computer has no Sentinel-2 L1C, so the background and the
#   water mask use sentinel-2-l2a (0-1 reflectance, no /10000 scaling);
# - Planetary Computer has no geocoded Sentinel-1 GRD, so VV and VH come from
#   sentinel-1-rtc (terrain-corrected gamma0, linear power) instead of the
#   CDSE SENTINEL1_GRD backscatter. They are loaded here, for the project
#   area and dates.
#
# Input bands (Sentinel-2), in this order: B02, B03, B04, B08
from openeo.processes import and_, or_

# The band dimension of this backend ("bands", "spectral", ...).
DIM = metadata.band_dimension.name if metadata else "bands"

# Both sensors are resampled to 50 m, as in the UDP
RESOLUTION = 50

s2 = reduced.resample_spatial(resolution=RESOLUTION, method="near")
s1 = DataCube(graph=PGNode(
    "load_collection",
    id="sentinel-1-rtc",
    spatial_extent=bounding_box,
    temporal_extent=time,
    bands=["vv", "vh"],
))
s1 = s1.process("apply_pixel_selection", data=s1, pixel_selection="first")
s1 = s1.resample_spatial(resolution=RESOLUTION, method="near").resample_cube_spatial(target=s2, method="near")


def ships(data):
    """Input: [B02, B03, B04, B08, VV, VH]"""
    B02, B03, B04, B08, VV, VH = data[0], data[1], data[2], data[3], data[4], data[5]
    water = (B03 - B08) / (B03 + B08) > 0.1
    ship = and_(water, or_(VV > 0.3, VH > 0.3))
    return array_create([
        if_(ship, 1.0, 4 * B04 - 0.2),
        if_(ship, 1.0, 4 * B03 - 0.2),
        if_(ship, 1.0, if_(water, 5 * B02 - 0.2, 4 * B02 - 0.2)),
    ])


detection = s2.merge_cubes(s1).apply_dimension(dimension=DIM, process=ships)
detection = detection.linear_scale_range(0, 1, 0, 255)

add_graph_to_map(detection.save_result("PNG"), "Ship Detection")
