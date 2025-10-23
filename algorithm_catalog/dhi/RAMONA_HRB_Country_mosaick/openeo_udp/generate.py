import json
from pathlib import Path

import openeo
from docutils.nodes import description
from openeo.api.process import Parameter
from openeo.processes import text_concat
from openeo.rest.udp import build_process_dict


def generate():
    connection = openeo.connect("openeofed.dataspace.copernicus.eu").authenticate_oidc()

    african_countries = [
        "algeria",
        "angola",
        "benin",
        "botswana",
        "burkina_faso",
        "burundi",
        "cameroon",
        "cape_verde",
        "central_african_republic",
        "chad",
        "comoros",
        "congo",
        "democratic_congo",
        "djibouti",
        "egypt",
        "equatorial_guinea",
        "eritrea",
        "eswatini",
        "ethiopia",
        "gabon",
        "gambia",
        "ghana",
        "guinea",
        "guinea_bissau",
        "ivory_coast",
        "kenya",
        "lesotho",
        "liberia",
        "libya",
        "madagascar",
        "malawi",
        "mali",
        "mauritania",
        "mauritius",
        "morocco",
        "mozambique",
        "namibia",
        "niger",
        "nigeria",
        "rwanda",
        "sao_tome_and_principe",
        "senegal",
        "seychelles",
        "sierra_leone",
        "somalia",
        "south_africa",
        "south_sudan",
        "sudan",
        "tanzania",
        "togo",
        "tunisia",
        "uganda",
        "western_sahara",
        "zambia",
        "zimbabwe"
    ]

    country_name = Parameter.string(
        name="country",
        description="Country for which data is to be extracted.",
        values=african_countries,
        default= "benin"
    )

    #date_param = Parameter.date_time("date",description="A date between 2021-08-01 and 2023-01-31.", default="2021-08-01T00:00:00Z")
    from openeo.processes import text_concat, date_shift

    year_param = Parameter.string("year", default="2021", values=["2021", "2022", "2023"])
    month_param = Parameter.string("month",description="Data is available between august 2021 and januari 2023.", default="10", values=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"])

    date_param = text_concat([year_param, "-", month_param, "-01T00:00:00Z"])


    format_opts = {
        "filename_prefix": "ramona_hrb_",
        "overviews": "AUTO",
        "tile_size": 512
    }

    cube = (connection.load_stac("https://stac.openeo.vito.be/collections/RAMONA_HERBACEOUS_BIOMASS",
                                        temporal_extent=[date_param, date_shift(date_param, 1, "day")])
                   .filter_spatial(connection.load_url(text_concat(["https://raw.githubusercontent.com/georgique/world-geojson/refs/heads/develop/countries/", country_name, ".json"]),
        format="GeoJSON")).linear_scale_range(-10,31000,-10,31000).save_result(format="GTiff", options= format_opts ))

    udp = build_process_dict(process_graph=cube, process_id="RAMONA_HRB_Country_mosaick",
                                      description=(Path(__file__).parent / "README.md").read_text(),
                                      parameters=[country_name, year_param, month_param],
                             default_job_options={"executor-memory":"7G", "python-memory":"50m", "executor-memoryOverhead":"1G"}
                             )
    connection.save_user_defined_process(process_graph=cube, user_defined_process_id="RAMONA_HRB_Country_mosaick",
                                      description=(Path(__file__).parent / "README.md").read_text(),
                                      parameters=[country_name, year_param, month_param])
    return udp


if __name__ == "__main__":

    with open("RAMONA_HRB_Country_mosaick.json", "w") as f:
        json.dump(generate(), f, indent=2)

import requests

def get_countries():
    url = "https://api.github.com/repos/georgique/world-geojson/contents/countries"
    response = requests.get(url)
    if response.status_code == 200:
        files = response.json()
        african_countries = [file['name'] for file in files if file['name'].endswith('.json')]
        return african_countries
    else:
        raise Exception(f"Failed to fetch data: {response.status_code}")

# if __name__ == "__main__":
#     african_countries = get_countries()
#     print("Countries GeoJSON files:")
#     for country in african_countries:
#         print(country)