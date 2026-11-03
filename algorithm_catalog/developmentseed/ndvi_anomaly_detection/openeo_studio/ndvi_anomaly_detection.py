# NDVI Anomaly Detection
# Mean NDVI of the project dates minus the mean NDVI of the same dates in the
# three previous years, after SCL cloud masking. Red: less vegetation than
# usual; green: more.
#
# License: CC-BY-SA-4.0
# Port of the openeo-udp "ndvi_anomaly_detection" UDP. Deviations:
# - the /10000 scaling is dropped (MPC reflectance is already 0-1);
# - the three baseline periods are computed here from the project dates
#   (the UDP uses date_shift, which this backend does not have);
# - the anomaly is shown with the RdYlGn colormap from -0.7 to 0.7.
#
# Input bands, in this order: B04, B08, SCL
from datetime import date
from functools import reduce

from openeo.processes import or_

# The band dimension of this backend ("bands", "spectral", ...).
DIM = metadata.band_dimension.name if metadata else "bands"

BASELINE_YEARS = 3
# Cloud shadow, cloud medium and high probability, thin cirrus, snow
CLOUD_SCL = [3, 8, 9, 10, 11]


def years_before(day, n):
    day = date.fromisoformat(day)
    # 29 February has no match in most years
    return day.replace(year=day.year - n, day=min(day.day, 28) if day.month == 2 else day.day).isoformat()


def cloud_mask(data):
    scl = data[2]
    return reduce(or_, [scl == c for c in CLOUD_SCL])


def ndvi_fn(data):
    return (data[1] - data[0]) / (data[1] + data[0])


def mean_ndvi(cube):
    clear = cube.mask(cube.reduce_dimension(dimension=DIM, reducer=cloud_mask))
    return clear.reduce_dimension(dimension=DIM, reducer=ndvi_fn).reduce_dimension(dimension="t", reducer="mean")


# The same dates in each of the previous years: the project's collection, area
# and filters, with other dates.
baselines = [
    mean_ndvi(DataCube(graph=PGNode(
        "load_collection",
        **{**load_collection_args, "temporal_extent": [years_before(d, n) for d in default_time]},
    )))
    for n in range(1, BASELINE_YEARS + 1)
]
baseline = reduce(lambda a, b: a.merge_cubes(b, overlap_resolver="add"), baselines) / BASELINE_YEARS
anomaly = mean_ndvi(datacube).merge_cubes(baseline, overlap_resolver="subtract")

# -0.7 to 0.7 -> 0 to 255, then the RdYlGn colormap
anomaly = anomaly.apply(lambda x: clip(x, -0.7, 0.7)).linear_scale_range(-0.7, 0.7, 0, 255)
anomaly = anomaly.process("colormap", data=anomaly, colormap=PGNode("get_colormap", name="rdylgn"))

add_graph_to_map(anomaly.save_result("PNG"), "NDVI Anomaly")
