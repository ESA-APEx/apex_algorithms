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

    date_param = Parameter.date_time("date",description="A date between 2021-08-01 and 2023-01-31.", default="2021-08-01T00:00:00Z")

    from openeo.processes import text_concat, date_shift


    cube = (connection.load_stac("https://stac.openeo.vito.be/collections/RAMONA_HERBACEOUS_BIOMASS",
                                        temporal_extent=[date_param, date_shift(date_param, 1, "day")])
                   .filter_spatial(connection.load_url(text_concat(["https://raw.githubusercontent.com/georgique/world-geojson/refs/heads/develop/countries/", country_name, ".json"]),
        format="GeoJSON")))

    udp = build_process_dict(process_graph=cube, process_id="ramona_biomass_extract",
                                      description=(Path(__file__).parent / "README.md").read_text(),
                                      parameters=[country_name, date_param])
    connection.save_user_defined_process(process_graph=cube, user_defined_process_id="ramona_rangeland_extract",
                                      description=(Path(__file__).parent / "README.md").read_text(),
                                      parameters=[country_name, date_param])
    return udp


if __name__ == "__main__":

    with open("ramona_biomass_extract.json", "w") as f:
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