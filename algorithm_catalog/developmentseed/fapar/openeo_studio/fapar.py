# Fraction of Absorbed Photosynthetically Active Radiation (FAPAR)
# FAPAR is the fraction (0-1) of incoming solar radiation in the 400-700 nm
# range that live green vegetation absorbs for photosynthesis.
# The value comes from the SNAP biophysical processor neural network
# (S2 toolbox BVNet weights), ported from the openEO UDP "fapar".
#
# Reference: SNAP Sentinel-2 Toolbox Level-2 Prototype Processor (ATBD, Weiss & Baret)
from math import pi

from openeo.processes import cos, tanh


def normalize(value, min_val, max_val):
    return 2 * (value - min_val) / (max_val - min_val) - 1


def denormalize(value, min_val, max_val):
    return 0.5 * (value + 1) * (max_val - min_val) + min_val


# Hidden layer: 5 tanh neurons, (bias, weights for the 11 inputs)
NEURONS = [
    (
        -0.88706836404028,
        [
            0.268714454733421,
            -0.205473108029835,
            0.281765694196018,
            1.33744341225598,
            0.390319212938497,
            -3.61271434220335,
            0.222530960987244,
            0.821790549667255,
            -0.093664567310731,
            0.019290146147447,
            0.037364446377188,
        ],
    ),
    (
        0.320126471197199,
        [
            -0.248998054599707,
            -0.571461305473124,
            -0.369957603466673,
            0.246031694650909,
            0.332536215252841,
            0.438269896208887,
            0.81900055189045,
            -0.93493149905931,
            0.082716247651866,
            -0.286978634108328,
            -0.035890968351662,
        ],
    ),
    (
        0.610523702500117,
        [
            -0.16406357531588,
            -0.126303285737763,
            -0.253670784366822,
            -0.321162835049381,
            0.06708228797358,
            2.02983228865526,
            -0.023141228827722,
            -0.553176625657559,
            0.059285451897783,
            -0.034334454541432,
            -0.031776704097009,
        ],
    ),
    (
        -0.379156190833946,
        [
            0.130240753003835,
            0.236781035723321,
            0.131811664093253,
            -0.250181799267664,
            -0.011364149953286,
            -1.85757321463352,
            -0.146860751013916,
            0.528008831372352,
            -0.046230769098303,
            -0.034509608392235,
            0.031884395036004,
        ],
    ),
    (
        1.35302339669057,
        [
            -0.029929946166941,
            0.795804414040809,
            0.348025317624568,
            0.943567007518504,
            -0.276341670431501,
            -2.94659418014259,
            0.2894830735075,
            1.04400695044018,
            -0.000413031960419,
            0.403331114840215,
            0.068427130526696,
        ],
    ),
]

# Output layer: linear, (bias, weights for the 5 neurons)
LAYER2 = (
    -0.336431283973339,
    [
        2.12603881106449,
        -0.632044932794919,
        5.59899578720625,
        1.77044414057897,
        -0.267879583604849,
    ],
)


def fapar_visualization(data):
    """
    Compute FAPAR with the SNAP neural network.
    Output: FAPAR (dimensionless, 0-1).
    Input data array: [B03, B04, B05, B06, B07, B8A, B11, B12,
                       viewZenithMean, viewAzimuthMean, sunZenithAngles, sunAzimuthAngles]

    Reflectance is 0-1 (MPC applies scale/offset), so the UDP's
    division by 10000 is not necessary. Angles are in degrees.

    inputs = normalize(each band), normalize(cos(view zenith)),
             normalize(cos(sun zenith)), cos(sun azimuth - view azimuth)
    n_i = tanh(bias_i + sum(w_ij * input_j))   for 5 neurons
    l2 = bias + sum(w_i * n_i)
    fapar = denormalize(l2, 0.000153013463222, 0.977135096979553)

    Color mapping: grayscale, 0 = black, 1 = white (as in the UDP notebook).
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

    fapar = denormalize(l2, 0.000153013463222, 0.977135096979553)

    return array_create([fapar, fapar, fapar])


# Apply the neural network on the bands dimension
fapar_image = reduced.apply_dimension(dimension="bands", process=fapar_visualization)
# Linear scale to 0-255 for RGB visualization (values outside 0-1 are clipped)
fapar_image = fapar_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
fapar_image = fapar_image.save_result("PNG")

add_graph_to_map(fapar_image, "FAPAR")
