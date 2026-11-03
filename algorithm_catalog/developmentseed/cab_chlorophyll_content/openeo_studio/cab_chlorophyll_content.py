# Leaf Chlorophyll Content (Cab)
# Cab is the chlorophyll a+b content of the canopy (ug/cm2).
# The UDP divides Cab by 300 to show 0-300 ug/cm2 as 0-1.
# The value comes from the SNAP biophysical processor neural network
# (S2 toolbox BVNet weights), ported from the openEO UDP "cab_chlorophyll_content".
#
# Reference: SNAP Sentinel-2 Toolbox Level-2 Prototype Processor (ATBD, Weiss & Baret)
from math import pi

from openeo.processes import clip, cos, tanh


def normalize(value, min_val, max_val):
    return 2 * (value - min_val) / (max_val - min_val) - 1


def denormalize(value, min_val, max_val):
    return 0.5 * (value + 1) * (max_val - min_val) + min_val


# Hidden layer: 5 tanh neurons, (bias, weights for the 11 inputs)
NEURONS = [
    (
        4.24229967015519,
        [
            0.40039655525658,
            0.607936279259404,
            0.137468650780226,
            -2.95586657346164,
            -3.18674668772957,
            2.20680075124643,
            -0.313784336139636,
            0.256063547510639,
            -0.071613219805105,
            0.510113504210111,
            0.142813982138661,
        ],
    ),
    (
        -0.259569088225796,
        [
            -0.250781102414872,
            0.439086302920381,
            -1.1605909375223,
            -1.86193525026961,
            0.981359868451638,
            1.63423083425484,
            -0.872527934645577,
            0.448240475035072,
            0.037078083501217,
            0.030044189670404,
            0.005956686619403,
        ],
    ),
    (
        3.13039262733836,
        [
            0.552080132568747,
            -0.502919673166901,
            6.10504192496623,
            -1.2943861191408,
            -1.0599563883528,
            -1.39409290241882,
            0.324752732710706,
            -1.75887182282768,
            -0.036663679860328,
            -0.183105291400739,
            -0.038145312117381,
        ],
    ),
    (
        0.77442357718162,
        [
            0.211591184882422,
            -0.248788896074327,
            0.887151598039092,
            1.14367589557141,
            -0.753968830338323,
            -1.18545695307676,
            0.541897860471577,
            -0.252685834607768,
            -0.023414901078143,
            -0.046022503549557,
            -0.006570284080657,
        ],
    ),
    (
        2.58427664853461,
        [
            0.254790234231378,
            -0.724968611431065,
            0.731872806026834,
            2.30345382102127,
            -0.849907966921912,
            -6.42531550053727,
            2.23884455845903,
            -0.19993757429799,
            0.097303331714567,
            0.334528254938326,
            0.113075306591838,
        ],
    ),
]

# Output layer: linear, (bias, weights for the 5 neurons)
LAYER2 = (
    0.463426463933822,
    [
        -0.35276004059919,
        -0.603407399151276,
        0.135099379384275,
        -1.73567312385193,
        -0.147546813318256,
    ],
)

# matplotlib "YlGn" color stops (equally spaced from 0 to 1)
YLGN_STOPS = ["#ffffe5", "#f7fcb9", "#d9f0a3", "#addd8e", "#78c679", "#41ab5d", "#238443", "#006837", "#004529"]


def hex_to_rgb(color):
    return [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def colormap(value, stops):
    """Piecewise-linear color ramp for a value in 0-1."""
    colors = [hex_to_rgb(c) for c in stops]
    step = 1 / (len(colors) - 1)
    value = clip(value, 0, 1)

    def segment(i):
        t = (value - i * step) / step
        return array_create([
            colors[i][c] + (colors[i + 1][c] - colors[i][c]) * t for c in range(3)
        ])

    result = segment(len(colors) - 2)
    for i in reversed(range(len(colors) - 2)):
        result = if_(value < (i + 1) * step, segment(i), result)
    return result


def cab_visualization(data):
    """
    Compute Cab with the SNAP neural network.
    Output: Cab (ug/cm2), shown as Cab / 300.
    Input data array: [B03, B04, B05, B06, B07, B8A, B11, B12,
                       viewZenithMean, viewAzimuthMean, sunZenithAngles, sunAzimuthAngles]

    Reflectance is 0-1 (MPC applies scale/offset), so the UDP's
    division by 10000 is not necessary. Angles are in degrees.

    inputs = normalize(each band), normalize(cos(view zenith)),
             normalize(cos(sun zenith)), cos(sun azimuth - view azimuth)
    n_i = tanh(bias_i + sum(w_ij * input_j))   for 5 neurons
    l2 = bias + sum(w_i * n_i)
    cab = denormalize(l2, 0.007426692959872, 873.908222110306) / 300

    Color mapping: matplotlib YlGn (light yellow = 0, dark green = 1),
    as in the UDP notebook.
    """
    (B03, B04, B05, B06, B07, B8A, B11, B12,
     viewZenithMean, viewAzimuthMean, sunZenithAngles, sunAzimuthAngles) = (
        data[0],
        data[1],
        data[2],
        data[3],
        data[4],
        data[5],
        data[6],
        data[7],
        data[8],
        data[9],
        data[10],
        data[11],
    )

    deg_to_rad = pi / 180

    B03_norm = normalize(B03, 0, 0.253061520471542)
    B04_norm = normalize(B04, 0, 0.290393577911328)
    B05_norm = normalize(B05, 0, 0.305398915248555)
    B06_norm = normalize(B06, 0.006637972542253, 0.608900395797889)
    B07_norm = normalize(B07, 0.013972727018939, 0.753827384322927)
    B8A_norm = normalize(B8A, 0.026690138082061, 0.782011770669178)
    B11_norm = normalize(B11, 0.016388074192258, 0.493761397883092)
    B12_norm = normalize(B12, 0, 0.493025984460231)
    view_zenith_norm = normalize(cos(viewZenithMean * deg_to_rad), 0.918595400582046, 1.0)
    sun_zenith_norm = normalize(cos(sunZenithAngles * deg_to_rad), 0.342022871159208, 0.936206429175402)
    rel_azimuth_norm = cos((sunAzimuthAngles - viewAzimuthMean) * deg_to_rad)

    inputs = [
        B03_norm, B04_norm, B05_norm, B06_norm, B07_norm, B8A_norm, B11_norm, B12_norm,
        view_zenith_norm, sun_zenith_norm, rel_azimuth_norm,
    ]

    neurons = []
    for bias, weights in NEURONS:
        s = bias
        for w, x in zip(weights, inputs):
            s = s + w * x
        neurons.append(tanh(s))

    l2 = LAYER2[0]
    for w, n in zip(LAYER2[1], neurons):
        l2 = l2 + w * n

    cab = denormalize(l2, 0.007426692959872, 873.908222110306)

    # Scale for display, as in the UDP
    cab = cab / 300

    return colormap(cab, YLGN_STOPS)


# Apply the neural network on the bands dimension
cab_image = reduced.apply_dimension(dimension="bands", process=cab_visualization)
# Linear scale to 0-255 for RGB visualization (values outside 0-1 are clipped)
cab_image = cab_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
cab_image = cab_image.save_result("PNG")

add_graph_to_map(cab_image, "Leaf Chlorophyll Content")
