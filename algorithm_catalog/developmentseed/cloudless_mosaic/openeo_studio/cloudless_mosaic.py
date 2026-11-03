# Cloudless Mosaic
# Per-pixel, per-band median of the clear observations of the period, after
# SCL cloud masking. Pixels without a clear observation take the median of
# the cloudy observations.
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/cloudless_mosaic/
# License: CC-BY-SA-4.0
# Port of the openeo-udp "cloudless_mosaic" UDP. Deviation: the /10000
# scaling is dropped (MPC reflectance is already 0-1).
#
# Input bands, in this order: B02, B03, B04, SCL
from functools import reduce

from openeo.processes import and_, is_nodata, not_

# The band dimension of this backend ("bands", "spectral", ...).
DIM = metadata.band_dimension.name if metadata else "bands"

BRIGHTEN_SCALE = 5
# Not clear: no data, defective, cloud shadow, cloud medium and high
# probability, thin cirrus, snow
NOT_CLEAR_SCL = [0, 1, 3, 8, 9, 10, 11]


def valid_fn(data):
    return and_(data[0] > 0, and_(data[1] > 0, data[2] > 0))


def clear_fn(data):
    return reduce(and_, [data[3] != c for c in NOT_CLEAR_SCL])


def brightened_rgb(data):
    return array_create([data[2] * BRIGHTEN_SCALE, data[1] * BRIGHTEN_SCALE, data[0] * BRIGHTEN_SCALE])


def median_rgb(keep, labels):
    """Median brightened red, green, blue of the observations where `keep` is true."""
    drop = datacube.reduce_dimension(dimension=DIM, reducer=lambda data: not_(keep(data)))
    return (
        datacube.mask(drop)
        .apply_dimension(dimension=DIM, process=brightened_rgb)
        .reduce_dimension(dimension="t", reducer="median")
        .rename_labels(dimension=DIM, target=labels)
    )


clear = median_rgb(lambda data: and_(valid_fn(data), clear_fn(data)), ["red", "green", "blue"])
cloudy = median_rgb(
    lambda data: and_(valid_fn(data), not_(clear_fn(data))), ["cloudy_red", "cloudy_green", "cloudy_blue"]
)


def clear_first(data):
    """The clear median, or the cloudy median where no observation was clear."""
    return array_create([if_(is_nodata(data[i]), data[i + 3], data[i]) for i in range(3)])


mosaic = clear.merge_cubes(cloudy).apply_dimension(dimension=DIM, process=clear_first)
mosaic = mosaic.linear_scale_range(0, 1, 0, 255)

add_graph_to_map(mosaic.save_result("PNG"), "Cloudless Mosaic")
