import json
from pathlib import Path
import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict

from eo_extractor import s1_features , s2_features


def generate() -> dict:

    connection  = openeo.connect("openeo.vito.be").authenticate_oidc()

    # define input parameter
    spatial_extent = Parameter.spatial_extent(
        name = "spatial_extent", 
        description = "Limits the data to process to the specified bounding box or polygons."
        )

    temporal_extent = Parameter.temporal_interval(
        name = "temporal_extent", 
        description = "Temporal extent specified as two-element array with start and end date/date-time."
        )

    # Load s1 and s2 features 
    s1_feature_cube = s1_features(connection,temporal_extent,spatial_extent,"median")
    s2_feature_cube = s2_features(connection,temporal_extent,spatial_extent,"median")
    # Merge the two feature cubes
    inference_cube = s2_feature_cube.merge_cubes(s1_feature_cube)

    # link to the trained model: this model has an expiry date
    model = "https://openeo.vito.be/openeo/1.2/jobs/j-250707130527460a823273791daa4344/results/items/ZWNjZTlmZWEwNGI4YzljNzZhYzc2YjQ1YjZiYTAwYzIwZjIxMWJkYTQ4NTZjMTRhYTQ0NzViOGU4ZWQ0MzNjZEBlZ2kuZXU=/a57df24a856cff107494dedfbfdcc180/ml_model_metadata.json?expires=1752501082"

    # predict of training data
    inference = inference_cube.predict_random_forest(
        model=model,
        dimension="bands"
    )

    # Build the process dictionary
    return build_process_dict(
        process_graph=inference,
        process_id="random_forest_firemapping",
        summary="Forest Fire Mapping Using Random Forest in openEO",
        description="Forest fire mapping is a critical tool for environmental monitoring and disaster management, enabling the timely detection and assessment of burned areas. This service is build upon techniques described in the research paper by Zhou, Bao et al., which introduces a machine learning–based approach using Sentinel-2 imagery. Their method combines spectral, topographic, and textural features to improve classification accuracy, particularly emphasising GLCM texture features extracted from Sentinel-2's short-wave infrared band.Thus, the UDP performs forest fire mapping using a pre-trained Random Forest model in openEO. It combines Sentinel-1 and Sentinel-2 features, applies the model, and outputs the predicted fire mapping results.",
        parameters=[spatial_extent, temporal_extent]
    )


if __name__ == "__main__":
    # save the generated process to a file
    with open(Path(__file__).parent / "random_forest_firemapping.json", "w") as f:
        json.dump(generate(), f, indent=2)
