# Urban Areas
# Sentinel-1 VV on the green channel, VH on the blue channel, and strong VH
# on the red channel, so buildings appear purple, green or white.
#
# Reference: https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-1/urban_areas/
# License: CC-BY-SA-4.0
# Port of the openeo-udp "urban_areas" UDP. Deviation: Planetary Computer has
# no geocoded Sentinel-1 GRD, so this uses sentinel-1-rtc (terrain-corrected
# gamma0, linear power) instead of the CDSE SENTINEL1_GRD backscatter.
#
# Input bands, in this order: vh, vv


def urban_areas(data):
    VH, VV = data[0], data[1]
    return array_create([if_(VH * 5.5 > 0.5, 1.0, 0.0), VV, VH * 8])


urban = reduced.apply_dimension(dimension="bands", process=urban_areas)
urban = urban.linear_scale_range(0, 1, 0, 255)

add_graph_to_map(urban.save_result("PNG"), "Urban Areas")
