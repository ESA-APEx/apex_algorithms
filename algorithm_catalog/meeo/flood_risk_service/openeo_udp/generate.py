import requests


def generate_process():
    """
    OpenEO custom process for Flood Service.
    """

    FLOOD_SERVICE_URL = "https://api.ideas.adamplatform.eu/fixed_value"

    def flood_process(context):
        # Convert the bounding box into a polygon
        bbox = context["area"]
        polygon = [
            [bbox["west"], bbox["north"]],
            [bbox["west"], bbox["south"]],
            [bbox["east"], bbox["south"]],
            [bbox["east"], bbox["north"]],
            [bbox["west"], bbox["north"]],
        ]

        year = context["year"]
        if year.isdigit():
            year = int(year)

        payload = {
            "geometry": {"type": "Polygon", "coordinates": [polygon]},
            "year": year,
            "ssp": context["ssp"],
            "storm_surge": context["storm_surge"],
            "confidence": context["confidence"],
        }

        response = requests.post(FLOOD_SERVICE_URL, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Flood service error: {response.status_code}")
        return response.json()

    process_dict = {
        "process_id": "flood_risk_service",
        "description": "Request flood service and return response",
        "apply": flood_process,
    }

    return process_dict


if __name__ == "__main__":
    process = generate_process()

    # Local test with bounding box
    test_context = {
        "area": { [0.6, 40.8], [0.6, 40.7],  [0.7, 40.7],  [0.7, 40.8]},
        "year": "2150",
        "ssp": "ssp585",
        "storm_surge": "5_0",
        "confidence": "medium",
    }

    result = process["apply"](test_context)
    print(result)
