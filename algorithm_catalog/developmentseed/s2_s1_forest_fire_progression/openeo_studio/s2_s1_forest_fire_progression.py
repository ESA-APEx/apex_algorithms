# Forest Fire Progression (Sentinel-2 + Sentinel-1)
# Areas burnt between two periods, from the drop of the Sentinel-1 VH
# backscatter, in red over a Sentinel-2 false-colour background. Water,
# vegetation and burn-scar pixels keep the Sentinel-2 colours; other pixels
# show low VV backscatter in light yellow.
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/data-fusion/s2_s1_forest_fire_progression/
# License: CC-BY-SA-4.0
# Port of the openeo-udp "s2_s1_forest_fire_progression" UDP. Deviations:
# - the /10000 scaling is dropped (MPC reflectance is already 0-1);
# - Planetary Computer has no geocoded Sentinel-1 GRD, so VV and VH come from
#   sentinel-1-rtc (terrain-corrected gamma0, linear power) instead of the
#   CDSE SENTINEL1_GRD backscatter;
# - the project dates are the first period (UDP `time_t1`), for Sentinel-2
#   and Sentinel-1. The second period (UDP `time_t2`) is set below.
#
# Input bands (Sentinel-2), in this order: B03, B04, B08, B11, B12
from openeo.processes import and_, or_

# The band dimension of this backend ("bands", "spectral", ...).
DIM = metadata.band_dimension.name if metadata else "bands"

# Second period: after the fire progression
TIME_T2 = ["2025-08-08", "2025-08-15"]

s2 = datacube.reduce_dimension(dimension="t", reducer="mean")


def s1_mean(temporal_extent, bands, labels):
    cube = DataCube(graph=PGNode(
        "load_collection",
        id="sentinel-1-rtc",
        spatial_extent=bounding_box,
        temporal_extent=temporal_extent,
        bands=bands,
    ))
    return cube.reduce_dimension(dimension="t", reducer="mean").rename_labels(dimension=DIM, target=labels)


s1 = s1_mean(time, ["vh"], ["vh_t1"]).merge_cubes(s1_mean(TIME_T2, ["vh", "vv"], ["vh_t2", "vv_t2"]))
cube = s2.merge_cubes(s1.resample_cube_spatial(target=s2, method="near"))


def fire_progression(data):
    """Input: [B03, B04, B08, B11, B12, vh_t1, vh_t2, vv_t2]"""
    B03, B04, B08, B11, B12 = data[0], data[1], data[2], data[3], data[4]
    vh_t1, vh_t2, vv_t2 = data[5], data[6], data[7]

    burnt = and_(vh_t2 < 0.03, vh_t2 - vh_t1 < -0.015)
    water = (B03 - B08) / (B03 + B08) > 0.15
    vegetation = (B08 - B04) / (B08 + B04) > 0.35
    scar = (B11 - B12) / (B11 + B12) + B08 > 0.2
    optical = or_(or_(water, vegetation), scar)
    low_vv = vv_t2 < 0.2

    return array_create([
        if_(optical, if_(burnt, 1.0, 2.5 * B12), if_(low_vv, 0.9, 0.0)),
        if_(optical, if_(burnt, 0.0, 2.5 * B08), if_(low_vv, 0.9, 0.0)),
        if_(optical, if_(burnt, 0.0, 2.5 * B04), if_(low_vv, 0.7, 1.0)),
    ])


progression = cube.apply_dimension(dimension=DIM, process=fire_progression)
progression = progression.linear_scale_range(0, 1, 0, 255)

add_graph_to_map(progression.save_result("PNG"), "Forest Fire Progression")
