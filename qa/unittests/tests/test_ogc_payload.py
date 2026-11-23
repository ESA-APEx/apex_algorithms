from unittest.mock import Mock

import pytest
from ogc_api_processes_client.models.status_info import StatusInfo

from apex_algorithm_qa_tools.benchmarks.ogc import create_ogc_api_client, create_ogc_job
from apex_algorithm_qa_tools.scenarios.ogc import OGCAPIBenchmarkScenario


@pytest.mark.parametrize(
    "endpoint,properties,expected_properties",
    [
        ("https://processing.geohazards-tep.eu/namespace", {"title": "benchmark"}, {"title": "benchmark"}),
        ("https://processing.geohazards-tep.eu/namespace", {}, None),
        ("https://processing.geohazards-tep.eu/namespace", None, None),
        ("https://example.org/namespace", {"title": "benchmark"}, None),
        ("https://processing.geohazards-tep.eu.example.org/namespace", {"title": "benchmark"}, None),
    ],
)
def test_scenario_execute_payload(endpoint, properties, expected_properties):
    data = {
        "id": "test",
        "type": "ogc_api_process",
        "endpoint": endpoint,
        "application": "test-process",
        "auth": {"url": "https://auth.example.org", "realm": "test"},
        "parameters": {"bands": ["green", "nir"], "epsg": "EPSG:4326"},
    }
    if properties is not None:
        data["properties"] = properties
    scenario = OGCAPIBenchmarkScenario.from_dict(data)
    assert scenario.properties == (properties or {})
    payload = create_ogc_job(scenario=scenario)
    expected = {"inputs": data["parameters"]}
    if expected_properties is not None:
        expected["properties"] = expected_properties
    assert payload == expected

    # Exercise the actual wrapper with transport mocked: no remote job is submitted.
    client = create_ogc_api_client(endpoint=endpoint, namespace="", user_token="test-token")
    client.api_client.rest_client.request = Mock()
    status = Mock(spec=StatusInfo)
    client.api_client.response_deserialize = Mock(return_value=Mock(data=status))
    assert client.execute_simple(process_id=scenario.application, execute=payload) is status
    assert client.api_client.rest_client.request.call_args.kwargs["body"] == expected
