# Leaf Area Index (LAI)
# LAI is the one-sided green leaf area per unit ground area (m2/m2).
# The UDP divides LAI by 3 to show 0-3 m2/m2 as 0-1.
# The value comes from the SNAP biophysical processor neural network
# (S2 toolbox BVNet weights), ported from the openEO UDP "leaf_area_index".
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
        4.96238030555279,
        [
            -0.02340687896647,
            0.921655164636366,
            0.135576544080099,
            -1.93833147239795,
            -3.34249581612268,
            0.902277648009576,
            0.205363538258614,
            -0.040607844721716,
            -0.083196409727092,
            0.260029270773809,
            0.284761567218845,
        ],
    ),
    (
        1.4160084439815,
        [
            -0.132555480856684,
            -0.13957483733354,
            -1.01460601689892,
            -1.33089003864927,
            0.031730624503341,
            -1.43358354131705,
            -0.959637898574699,
            1.133115706551,
            0.216603876541632,
            0.410652303762839,
            0.064760155543506,
        ],
    ),
    (
        1.07589704721331,
        [
            0.086015977724868,
            0.616648776881434,
            0.678003876446556,
            0.141102398644968,
            -0.096682206883546,
            -1.1288326388622,
            0.302189102741375,
            0.434494937299725,
            -0.021903699490589,
            -0.228492476802263,
            -0.039460537589826,
        ],
    ),
    (
        1.53398826465542,
        [
            -0.109366593670404,
            -0.071046262972729,
            0.06458241147832,
            2.90632523682316,
            -0.673873108979163,
            -3.83805186828084,
            1.69597934453153,
            0.046950296081713,
            -0.049709652688365,
            0.021829545430994,
            0.057483827104091,
        ],
    ),
    (
        3.02411593075723,
        [
            -0.089939416159969,
            0.175395483106147,
            -0.08184732917262,
            2.21989536748779,
            1.71387397513685,
            0.713069186099534,
            0.138970813499201,
            -0.060771761518025,
            0.124263341255473,
            0.210086140404351,
            -0.183878138700341,
        ],
    ),
]

# Output layer: linear, (bias, weights for the 5 neurons)
LAYER2 = (
    1.09696310707722,
    [
        -1.50013548972873,
        -0.096283269121503,
        -0.194935930577094,
        -0.352305895755591,
        0.075107415847473,
    ],
)


def lai_visualization(data):
    """
    Compute LAI with the SNAP neural network.
    Output: LAI (m2/m2), shown as LAI / 3.
    Input data array: [B03, B04, B05, B06, B07, B8A, B11, B12,
                       viewZenithMean, viewAzimuthMean, sunZenithAngles, sunAzimuthAngles]

    Reflectance is 0-1 (MPC applies scale/offset), so the UDP's
    division by 10000 is not necessary. Angles are in degrees.

    inputs = normalize(each band), normalize(cos(view zenith)),
             normalize(cos(sun zenith)), cos(sun azimuth - view azimuth)
    n_i = tanh(bias_i + sum(w_ij * input_j))   for 5 neurons
    l2 = bias + sum(w_i * n_i)
    lai = denormalize(l2, 0.000319182538301, 14.4675094548151) / 3

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

    lai = denormalize(l2, 0.000319182538301, 14.4675094548151)

    # Scale for display, as in the UDP
    lai = lai / 3

    return array_create([lai, lai, lai])


# Apply the neural network on the bands dimension
lai_image = reduced.apply_dimension(dimension="bands", process=lai_visualization)
# Linear scale to 0-255 for RGB visualization (values outside 0-1 are clipped)
lai_image = lai_image.linear_scale_range(
    input_min=0, input_max=1, output_min=0, output_max=255
)
# Define PNG visualization
lai_image = lai_image.save_result("PNG")

add_graph_to_map(lai_image, "Leaf Area Index")
