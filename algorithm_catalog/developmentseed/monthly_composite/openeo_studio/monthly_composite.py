# Monthly Composite
# Cloud-free greenest-pixel composite: for each pixel, the date with the
# highest B08 / B03 ratio, after SCL cloud masking, in an enhanced true color.
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/monthly_composite/
# License: CC-BY-SA-4.0
# Port of the openeo-udp "monthly_composite" UDP. Deviations:
# - the /10000 scaling is dropped (MPC reflectance is already 0-1);
# - the greenest date is selected with the backend's "lastbandhight" pixel
#   selection, which keeps the bands of the date where the last band is highest.
#
# Input bands, in this order: B02, B03, B04, B05, B08, SCL
from functools import reduce

from openeo.processes import or_

# The band dimension of this backend ("bands", "spectral", ...).
DIM = metadata.band_dimension.name if metadata else "bands"

GAIN = 2.8
# Cloud shadow, cloud medium and high probability, thin cirrus, snow
CLOUD_SCL = [3, 8, 9, 10, 11]


def cloud_mask(data):
    scl = data[5]
    return reduce(or_, [scl == c for c in CLOUD_SCL])


def color_and_greenness(data):
    """Enhanced red, green, blue, and the B08 / B03 ratio last (the selection band)."""
    B02, B03, B04, B05, B08 = data[0], data[1], data[2], data[3], data[4]
    return array_create([
        GAIN * B04 + 0.1 * B05,
        GAIN * B03 + 0.15 * B08,
        GAIN * B02,
        B08 / B03,
    ])


clear = datacube.mask(datacube.reduce_dimension(dimension=DIM, reducer=cloud_mask))
composite = clear.apply_dimension(dimension=DIM, process=color_and_greenness)
composite = composite.process("apply_pixel_selection", data=composite, pixel_selection="lastbandhight")
composite = composite.linear_scale_range(0, 1, 0, 255)

add_graph_to_map(composite.save_result("PNG"), "Monthly Composite")
