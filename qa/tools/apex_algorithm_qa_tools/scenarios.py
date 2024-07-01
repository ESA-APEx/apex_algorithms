from __future__ import annotations

import dataclasses
import json
import logging
import re
from typing import List

import requests
from apex_algorithm_qa_tools.common import get_project_root

_log = logging.getLogger(__name__)


# TODO #15 Flatten apex_algorithm_qa_tools to a single module and push as much functionality to https://github.com/ESA-APEx/esa-apex-toolbox-python


@dataclasses.dataclass(kw_only=True)
class BenchmarkScenario:
    # TODO #14 need for differentiation between different types of scenarios?
    id: str
    description: str | None = None
    backend: str
    process_graph: dict

    @classmethod
    def from_dict(cls, data: dict) -> BenchmarkScenario:
        # TODO #14 standardization of these types? What about other types and how to support them?
        assert data["type"] == "openeo"
        return cls(
            id=data["id"],
            description=data.get("description"),
            backend=data["backend"],
            process_graph=data["process_graph"],
        )


def get_benchmark_scenarios() -> List[BenchmarkScenario]:
    # TODO: instead of flat list, keep original grouping/structure of benchmark scenario files?
    # TODO: check for uniqueness of scenario IDs? Also make this a pre-commit lint tool?
    scenarios = []
    for path in (get_project_root() / "benchmark_scenarios").glob("**/*.json"):
        with open(path) as f:
            data = json.load(f)
        # TODO: support single scenario files in addition to listings?
        assert isinstance(data, list)
        scenarios.extend(BenchmarkScenario.from_dict(item) for item in data)
    return scenarios


def lint_benchmark_scenario(scenario: BenchmarkScenario):
    """
    Various sanity checks for scenario data.
    To be used in unit tests and pre-commit hooks.
    """
    # TODO #17 use JSON Schema based validation instead of ad-hoc checks?
    # TODO integrate this as a pre-commit hook
    # TODO raise descriptive exceptions instead of asserts?
    assert re.match(r"^[a-zA-Z0-9_-]+$", scenario.id)
    # TODO: proper allow-list of backends?
    assert scenario.backend in ["openeofed.dataspace.copernicus.eu"]
    # TODO: more advanced process graph validation?
    assert isinstance(scenario.process_graph, dict)
    for node_id, node in scenario.process_graph.items():
        assert isinstance(node, dict)
        assert re.match(r"^[a-z0-9_-]+$", node["process_id"])
        assert "arguments" in node
        assert isinstance(node["arguments"], dict)

        if "namespace" in node:
            namespace = node["namespace"]
            if re.match("^https://", namespace):
                if re.match(
                    "https://github.com/.*/blob/.*", namespace, flags=re.IGNORECASE
                ):
                    raise ValueError(
                        f"Invalid github.com based namespace {namespace!r}: should be a raw URL"
                    )
                # Inspect openEO process definition URL
                resp = requests.get(namespace)
                resp.raise_for_status()
                # TODO: also support process listings?
                assert resp.json()["id"] == node["process_id"]
                # TODO: check that github URL is a "pinned" reference
            # TODO: check that provided parameters match expected process parameters
