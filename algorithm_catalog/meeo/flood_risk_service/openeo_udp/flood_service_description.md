
# openeo_udp — Flood Service Driver per OpenEO / APEX

Custom OpenEO driver for [ADAM platform's](https://api.ideas.adamplatform.eu) flood‑risk prediction service.

---

## Structure

```
openeo_udp/
├── app.py                     # Flask API to expose the process as an endpoint
├── generate.py                # Definition of the custom OpenEO process
├── flood_risk_service.json    # OpenEO‑standard process graph (JSON)
├── test_flood.py              # Local test script for the Flask endpoint
└── README.md
```

---

## Installation

```bash
pip install requests flask openeo
```

---

## Start the Flask API

```bash
python app.py
```

The API will listen on **port 5000** (configurable in `app.py`).  

### Endpoint

POST /flood

**Body JSON example:**

```json
{
  "area": {"west": 0.6, "south": 40.7, "east": 0.7, "north": 40.8},
  "year": "2150",
  "ssp": "ssp585",
  "storm_surge": "5_0",
  "confidence": "medium"
}
```

---

## Direct usage with Python (without Flask)

```python
from generate import generate_process

process = generate_process()

context = {
    "area": {"west": 0.6, "south": 40.7, "east": 0.7, "north": 40.8},
    "year": "2150",
    "ssp": "ssp585",
    "storm_surge": "5_0",
    "confidence": "medium",
}

result = process["apply"](context)
print(result)
```

---

## Local test of the Flask endpoint

```bash
python test_flood.py
```

`test_flood.py` sends a POST request to the `/flood` endpoint and prints:

- Status code
- JSON returned by the flood service

---

## Registration in the APEX catalog

The process must be registered **only once** in the back‑end catalog.

### Option A — Via REST API (curl)

```bash
curl -X PUT   https://<apex-backend>/processes/flood_service_request   -H "Content-Type: application/json"   -d @process_graph.json
```

### Option B — Via OpenEO Python SDK

```python
import openeo, json

conn = openeo.connect("https://<apex-backend>")
# add here the chosen authentication method

with open("process_graph.json") as f:
    pg = json.load(f)

conn.save_user_defined_process(
    user_defined_process_id="flood_service_request",
    process_graph=pg["process_graph"],
    parameters=pg["parameters"],
    summary=pg.get("summary", "Flood service request"),
    description=pg.get("description", "Request flood service and return response"),
)
```

### Option C — Through the APEX UI

1. Go to **Processes** → **User-defined** → **New**.
2. Paste the contents of `process_graph.json`.
3. Save and publish.

---

## Parameters

| Parameter     | Type   | Allowed values                                  | Default    |
|---------------|--------|----------------------------------------- -------|------------|
| `area`        | object | `{west, south, east, north}` in decimal degrees | —          |
| `year`        | string | 2020, 2040, 2060, 2080, 2100, 2120, 2150, all   | `"2150"`   |
| `ssp`         | string | ssp119, ssp126, ssp245, ssp370, ssp585, all     | —          |
| `storm_surge` | string | 0_0, 0_5, 1_0, 1_5, 2_0, 3_0, 5_0, all          | —          |
| `confidence`  | string | low, medium, high                               | `"medium"` |

> Nota: `area` must be an object with the keys "west", "south", "east", "north" in decimal degrees. Do not use coordinate lists.

---

## Composition with other OpenEO processes

```json
{
  "process_graph": {
    "flood_node": {
      "process_id": "flood_service_request",
      "arguments": {
        "area":        { "from_parameter": "area" },
        "year":        "2100",
        "ssp":         "ssp585",
        "storm_surge": "1_0",
        "confidence":  "high"
      }
    },
    "save_node": {
      "process_id": "save_result",
      "arguments": {
        "data":   { "from_node": "flood_node" },
        "format": "JSON"
      },
      "result": true
    }
  }
}
```

---

## Notes for APEX integration

- **`process_id`**: `flood_service_request`
- The `"apply"` field in `generate_process()` is the callable invoked by the Python runtime; it is ignored in the JSON serialization.
- Il back-end must have network access to `https://api.ideas.adamplatform.eu/`.
- Timeout is set to 120 seconds: increase it in generate.py for very large areas or for requests using the `"all"` parameter.

---

## References

- [openEO API — Processes](https://api.openeo.org/#tag/Process-Discovery)
- [openEO Python Client](https://open-eo.github.io/openeo-python-client/)
- [ADAM Platform API](https://api.ideas.adamplatform.eu/docs)
