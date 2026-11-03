# Flood Detection
# Water from Sentinel-1 VV backscatter (VV <= -15 dB) in blue, over a
# Sentinel-2 NIR (B08) grey background.
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-1/flood_mapping/
# License: CC-BY-SA-4.0
# Port of the openeo-udp "flood_detection" UDP. Deviations:
# - the /10000 scaling is dropped (MPC reflectance is already 0-1);
# - Planetary Computer has no geocoded Sentinel-1 GRD, so the VV band comes
#   from sentinel-1-rtc (terrain-corrected gamma0, linear power) instead of
#   the CDSE SENTINEL1_GRD backscatter. It is loaded here, for the project
#   area and dates.
#
# Input bands (Sentinel-2): B08
from openeo.processes import is_nodata, log

# The band dimension of this backend ("bands", "spectral", ...).
DIM = metadata.band_dimension.name if metadata else "bands"

WATER_THRESHOLD_DB = 15
BACKGROUND_GAIN = 2.5


def latest(cube, band):
    """Per pixel, the value of the last date with data (openEO `last` with
    ignore_nodata). The frames of one day are mosaicked first; where the last
    day has no data, the earliest date with data is used."""
    last_day = (
        cube.aggregate_temporal_period(period="day", reducer="mean")
        .reduce_dimension(dimension="t", reducer="last")
        .rename_labels(dimension=DIM, target=["last"])
    )
    earliest = cube.process("apply_pixel_selection", data=cube, pixel_selection="first")
    earliest = earliest.rename_labels(dimension=DIM, target=["earliest"])
    return last_day.merge_cubes(earliest).apply_dimension(
        dimension=DIM,
        process=lambda data: array_create([if_(is_nodata(data[0]), data[1], data[0])]),
    ).rename_labels(dimension=DIM, target=[band])


nir = latest(datacube, "nir")

vv = DataCube(graph=PGNode(
    "load_collection",
    id="sentinel-1-rtc",
    spatial_extent=bounding_box,
    temporal_extent=time,
    bands=["vv"],
))
vv = latest(vv, "vv").resample_cube_spatial(target=nir, method="near")


def flood(data):
    NIR, VV = data[0], data[1]
    water = 10 * log(VV, 10) <= -WATER_THRESHOLD_DB
    background = BACKGROUND_GAIN * NIR
    return array_create([
        if_(water, VV * 10, background),
        if_(water, VV * 10, background),
        if_(water, VV * 50, background),
    ])


flood_image = nir.merge_cubes(vv).apply_dimension(dimension=DIM, process=flood)
flood_image = flood_image.linear_scale_range(0, 1, 0, 255)

add_graph_to_map(flood_image.save_result("PNG"), "Flood Detection")
