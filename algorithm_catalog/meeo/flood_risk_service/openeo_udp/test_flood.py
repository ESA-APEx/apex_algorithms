import requests

url = "http://127.0.0.1:5000/flood"

payload = {
    "area": {"west": 0.6, "south": 40.7, "east": 0.7, "north": 40.8},
    "year": "2150",
    "ssp": "ssp585",
    "storm_surge": "5_0",
    "confidence": "medium"
}

response = requests.post(url, json=payload)
print(response.status_code)
print(response.json())