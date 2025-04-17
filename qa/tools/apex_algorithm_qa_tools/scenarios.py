from __future__ import annotations

import dataclasses
import json
import logging
import re
import glob
from pathlib import Path
from typing import List

import jsonschema
import requests
from apex_algorithm_qa_tools.common import (
    assert_no_github_feature_branch_refs,
    get_project_root,
)
from openeo.util import TimingLogger

_log = logging.getLogger(__name__)


# TODO #15 Flatten apex_algorithm_qa_tools to a single module and push as much functionality to https://github.com/ESA-APEx/esa-apex-toolbox-python


def _get_benchmark_scenario_schema() -> dict:
    with open(get_project_root() / "schemas/benchmark_scenario.json") as f:
        return json.load(f)


@dataclasses.dataclass(kw_only=True)
class BenchmarkScenario:
    # TODO #14 need for differentiation between different types of scenarios?
    id: str
    description: str | None = None
    backend: str
    process_graph: dict
    job_options: dict | None = None
    reference_data: dict = dataclasses.field(default_factory=dict)
    reference_options: dict = dataclasses.field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> BenchmarkScenario:
        jsonschema.validate(instance=data, schema=_get_benchmark_scenario_schema())
        # TODO: also include the `lint_benchmark_scenario` stuff here (maybe with option to toggle deep URL inspection)?

        # TODO #14 standardization of these types? What about other types and how to support them?
        assert data["type"] == "openeo"
        return cls(
            id=data["id"],
            description=data.get("description"),
            backend=data["backend"],
            process_graph=data["process_graph"],
            reference_data=data.get("reference_data", {}),
            job_options=data.get("job_options"),
            reference_options=data.get("reference_options", {}),
        )


def get_benchmark_scenarios() -> List[BenchmarkScenario]:
    # TODO: instead of flat list, keep original grouping/structure of benchmark scenario files?
    # TODO: check for uniqueness of scenario IDs? Also make this a pre-commit lint tool?
    scenarios = []
    # old style glob is used to support symlinks
    for path in glob.glob(str(get_project_root() / "algorithm_catalog") + "/**/*benchmark_scenarios*/*.json", recursive=True):
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
    # TODO #17 raise descriptive exceptions instead of asserts?
    assert re.match(r"^[a-zA-Z0-9_-]+$", scenario.id)
    # TODO proper allow-list of backends or leave this freeform?
    assert scenario.backend in [
        "openeo.dataspace.copernicus.eu",
        "openeofed.dataspace.copernicus.eu",
        "openeo.cloud",
        "openeo.vito.be",
    ]
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
                assert_no_github_feature_branch_refs(namespace)
                # Inspect openEO process definition URL
                resp = requests.get(namespace)
                resp.raise_for_status()
                # TODO: also support process listings?
                assert resp.json()["id"] == node["process_id"]
                # TODO: check that github URL is a "pinned" reference
            # TODO: check that provided parameters match expected process parameters


def download_reference_data(scenario: BenchmarkScenario, reference_dir: Path) -> Path:
    with TimingLogger(
        title=f"Downloading reference data for {scenario.id=} to {reference_dir=}",
        logger=_log.info,
    ):
        for path, source in scenario.reference_data.items():
            path = reference_dir / path
            if not path.is_relative_to(reference_dir):
                raise ValueError(
                    f"Resolved {path=} is not relative to {reference_dir=} ({scenario.id=})"
                )
            path.parent.mkdir(parents=True, exist_ok=True)

            with TimingLogger(
                title=f"Downloading {source=} to {path=}", logger=_log.info
            ):
                # TODO: support other sources than HTTP?
                resp = requests.get(source, stream=True)
                with path.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=128):
                        f.write(chunk)

    return reference_dir
