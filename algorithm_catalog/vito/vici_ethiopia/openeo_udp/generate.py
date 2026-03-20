import json
import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict


def generate() -> dict:
    """
    Generate the UDP process graph for VICI calculation.
    """
    eoconn = openeo.connect("openeo.vito.be").authenticate_oidc()
    # Define Input Parameters
    start_date = Parameter.date(
        name="start_date",
        description="Start of the temporal interval and time. The date format is YYYY-MM-DD. If no time is specified, it defaults to 00:00:00. ",
    )

    end_date = Parameter.date(
        name="end_date",
        description="End of the temporal interval and time. The date format is YYYY-MM-DD. If no time is specified, it defaults to 00:00:00. ",
    )

    vici_cube = eoconn.datacube_from_process(
        "vici_ethiopia",
        namespace="vito",
        start_date=start_date,
        end_date=end_date,
    )

    return build_process_dict(
        process_graph=vici_cube,
        process_id="vici_ethiopia",
        summary="Vegetation Condition Index (VICI) for Ethiopia.",
        description="The Vegetation Index Crop Insurance (VICI) product represents an EO-based insurance model that utilizes NDVI-imagery to quantitatively assess the severity of occurring agronomic droughts. It has been originally developed by dr. Kees de Bie, at the Department of Natural Resources, Faculty Geo-Information Science and Earth Observation (ITC), University of Twente, the Netherlands. As a business model, since 2018, the VICI scheme is successfully in use by various Ethiopian organizations. The model is based on the concept of dekadal (10-daily) anomalies of the Normalized Difference Vegetation Index (NDVI), a general indicator of vegetation vigor and health. In essence, the method compares, in a statistically sound way, the behaviour of this NDVI indicator within a given 10-day period to the “expected” behaviour within the same 10-day period based on a 20-year archive spanning the period 2000-2020. The final outcome of the method is a 1 km resolution raster for the whole country of Ethiopia showing for each pixel and each 10-day period a value between 0 (no impact of drought on vegetation) and 100 (most severe impact of drought on vegetation).",
        parameters=[start_date, end_date],
    )


if __name__ == "__main__":
    with open("vici_ethiopia.json", "w") as f:
        json.dump(generate(), f, indent=2)
    print("Process graph saved to vici_ethiopia.json")