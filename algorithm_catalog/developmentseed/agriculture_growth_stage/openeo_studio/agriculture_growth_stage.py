# Agricultural Growth Stage
# Mean NDVI of three consecutive months on the red, green and blue channels:
# the colour shows when in the season the vegetation peaked.
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/agriculture_growth_stage/
# Original authors: @HarelDan, András Zlinszky
# License: CC-BY-SA-4.0
# Port of the openeo-udp "agriculture_growth_stage" UDP. Deviations:
# - the /10000 scaling is dropped (MPC reflectance is already 0-1);
# - the three months are computed here from the end date of the project
#   dates (the UDP uses date_shift, which this backend does not have).
#   Set the project dates to the three months, e.g. 2017-06-01 to 2017-08-31.
#
# Input bands, in this order: B04, B08, SCL
from datetime import date, timedelta
from functools import reduce

from openeo.processes import or_

# The band dimension of this backend ("bands", "spectral", ...).
DIM = metadata.band_dimension.name if metadata else "bands"

# Cloud shadow, cloud medium and high probability, thin cirrus, snow
CLOUD_SCL = [3, 8, 9, 10, 11]


def months_before(day, n):
    """Same day of the month, n months earlier (clamped to the month end)."""
    year, month = divmod(day.year * 12 + day.month - 1 - n, 12)
    month += 1
    last = (date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day.day, last))


end = date.fromisoformat(default_time[1])
edges = [months_before(end, n).isoformat() for n in (3, 2, 1, 0)]


def cloud_mask(data):
    scl = data[2]
    return reduce(or_, [scl == c for c in CLOUD_SCL])


def ndvi_fn(data):
    return (data[1] - data[0]) / (data[1] + data[0])


ndvi = datacube.mask(datacube.reduce_dimension(dimension=DIM, reducer=cloud_mask)).reduce_dimension(
    dimension=DIM, reducer=ndvi_fn
)

channels = []
for label, start, stop in zip(["R", "G", "B"], edges[:-1], edges[1:]):
    month = ndvi.filter_temporal(start, stop).reduce_dimension(dimension="t", reducer="mean")
    # Stretch NDVI 0.1-0.7 to 0-1
    month = month.apply(lambda x: clip((x - 0.1) / 0.6, 0.0, 1.0))
    channels.append(month.add_dimension(name=DIM, label=label, type="bands"))

growth_stage = channels[0].merge_cubes(channels[1]).merge_cubes(channels[2])
growth_stage = growth_stage.linear_scale_range(0, 1, 0, 255)

add_graph_to_map(growth_stage.save_result("PNG"), "Agricultural Growth Stage")
