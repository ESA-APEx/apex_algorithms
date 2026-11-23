from __future__ import annotations

import dataclasses
import json
from pathlib import Path
import re
from typing import List

import jsonschema
import requests

from apex_algorithm_qa_tools.scenarios.scenario import BenchmarkScenario,get_benchmark_scenario_schema
from apex_algorithm_qa_tools.common import assert_no_github_feature_branch_refs


BACKEND_PATTERNS = [
    r"^(https://)?openeo\.dataspace\.copernicus\.eu(/.*)?$",
    r"^(https://)?openeofed\.dataspace\.copernicus\.eu(/.*)?$",
    r"^(https://)?openeo\.cloud(/.*)?$",
    r"^(https://)?openeo\.vito\.be(/.*)?$",
    r"^(https:\/\/)?openeo\.terrascope\.be(\/.*)?$",
    r"^(https://)?openeo\.eodc\.eu(/.*)?$",
]


@dataclasses.dataclass(kw_only=True)
class openEOBenchmarkScenario(BenchmarkScenario):
    backend: str
    process_graph: dict
    job_options: dict | None = None

    @classmethod
    def from_dict(cls, data: dict, source: str | Path | None = None) -> BenchmarkScenario:
        jsonschema.validate(instance=data, schema=get_benchmark_scenario_schema())
        # TODO: also include the `lint_benchmark_scenario` stuff here (maybe with option to toggle deep URL inspection)?

        # TODO #14 standardization of these types? What about other types and how to support them?
        assert data["type"] == "openeo"
        return cls(
            id=data["id"],
            type=data["type"],
            description=data.get("description"),
            backend=data["backend"],
            process_graph=data["process_graph"],
            job_options=data.get("job_options"),
            reference_data=data.get("reference_data", {}),
            reference_options=data.get("reference_options", {}),
            source=source,
        )

def lint_openeo_fields(scenario: BenchmarkScenario):
    lint_backend(scenario=scenario)
    lint_openeo_process_graph(scenario=scenario)


def lint_backend(scenario: BenchmarkScenario):
    assert any(re.fullmatch(pattern, scenario.backend) for pattern in BACKEND_PATTERNS), (
        f"Unsupported backend: {scenario.backend!r}"
    )


def lint_namespace_reference(namespace: str):
    if not re.match(r"^https://", namespace):
        return

    if re.match(r"https://github.com/.*/blob/.*", namespace, flags=re.IGNORECASE):
        raise ValueError(f"Invalid github.com based namespace {namespace!r}: should be a raw URL")

    assert_no_github_feature_branch_refs(namespace)


def lint_openeo_process_graph(scenario: BenchmarkScenario):
    assert isinstance(scenario.process_graph, dict)

    for node in scenario.process_graph.values():
        assert isinstance(node, dict)
        assert re.match(r"^[a-zA-Z0-9_-]+$", node["process_id"])
        assert "arguments" in node
        assert isinstance(node["arguments"], dict)

        namespace = node.get("namespace")
        if namespace is None:
            continue

        lint_namespace_reference(namespace)

        if re.match(r"^https://", namespace):
            response = requests.get(namespace)
            response.raise_for_status()
            assert response.json()["id"] == node["process_id"]
