from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
from pathlib import Path
from typing import List

import requests

_log = logging.getLogger(__name__)


# TODO: rename `algorithm_invocations` and `qa/tools/apex_algorithm_qa_tools/usecases.py` to more descriptive "scenarios" or "benchmark-scenarios"?


@dataclasses.dataclass(kw_only=True)
class UseCase:
    # TODO: need for differentiation between different types of use cases?
    id: str
    description: str | None = None
    backend: str
    process_graph: dict

    @classmethod
    def from_dict(cls, data: dict) -> UseCase:
        # TODO: standardization of these types? What about other types and how to support them?
        assert data["type"] == "openeo"
        return cls(
            id=data["id"],
            description=data.get("description"),
            backend=data["backend"],
            process_graph=data["process_graph"],
        )


APEX_ALGORITHM_INVOCATIONS_ROOT = "APEX_ALGORITHM_INVOCATIONS_ROOT"


def get_algorithm_invocation_root() -> Path:
    # TODO: find a better name for "algorithm invocations"?
    # First attempt: check environment variable
    if APEX_ALGORITHM_INVOCATIONS_ROOT in os.environ:
        algo_root = os.environ[APEX_ALGORITHM_INVOCATIONS_ROOT]
        _log.info(
            f"Using algorithm invocations root {algo_root!r} (from environment variable {APEX_ALGORITHM_INVOCATIONS_ROOT})"
        )
        return Path(algo_root)

    # Next attempts: try to detect project root
    for project_root_candidate in [
        # Running from project root?
        Path.cwd(),
        # Running from qa/tools, qa/benchmarks, qa/unittests?
        Path.cwd().parent.parent,
        # Search from current file
        Path(__file__).parent.parent.parent.parent,
    ]:
        if project_root_candidate.is_dir() and all(
            (project_root_candidate / p).is_dir()
            for p in ["algorithm_invocations", "qa/tools"]
        ):
            algo_root = project_root_candidate / "algorithm_invocations"
            _log.info(
                f"Using algorithm invocations root {algo_root!r} (assuming project root {project_root_candidate!r})"
            )
            return algo_root

    raise RuntimeError("Could not determine algorithm invocations root directory.")


def get_use_cases() -> List[UseCase]:
    # TODO: instead of flat list, keep original grouping/structure of "algorithm_invocations" files?
    # TODO: check for uniqueness of scenario IDs? Also make this a pre-commit lint tool?
    use_cases = []
    for path in get_algorithm_invocation_root().glob("*.json"):
        with open(path) as f:
            data = json.load(f)
        # TODO: support single use case files in addition to listings?
        assert isinstance(data, list)
        use_cases.extend(UseCase.from_dict(item) for item in data)
    return use_cases


def lint_usecase(usecase: UseCase):
    """
    Various sanity checks for use case data.
    To be used in unit tests and pre-commit hooks.
    """
    # TODO integrate this as a pre-commit hook
    # TODO raise descriptive exceptions instead of asserts?
    assert re.match(r"^[a-zA-Z0-9_-]+$", usecase.id)
    # TODO: proper allow-list of backends?
    assert usecase.backend in ["openeofed.dataspace.copernicus.eu"]
    # TODO: refactor this out to a more generic process graph validator? Or use an existing tool?
    # TODO: more advanced process graph validation?
    assert isinstance(usecase.process_graph, dict)
    for node_id, node in usecase.process_graph.items():
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
                # Inspect UDP URL
                udp_resp = requests.get(namespace)
                udp_resp.raise_for_status()
                assert udp_resp.json()["id"] == node["process_id"]
