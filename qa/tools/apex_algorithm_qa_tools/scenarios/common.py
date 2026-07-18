from __future__ import annotations

import glob
import logging
import re
from pathlib import Path
from typing import List

import requests
from apex_algorithm_qa_tools.common import (
    get_project_root,
)
from openeo.util import TimingLogger

from apex_algorithm_qa_tools.scenarios.openeo import lint_openeo_fields
from apex_algorithm_qa_tools.scenarios.ogc import OGCAPIBenchmarkScenario
from apex_algorithm_qa_tools.scenarios.scenario import BenchmarkScenario
from apex_algorithm_qa_tools.scenarios.factory import read_scenarios_file

_log = logging.getLogger(__name__)


def get_benchmark_scenarios(root=None) -> List[BenchmarkScenario]:
    # TODO: instead of flat list, keep original grouping/structure of benchmark scenario files?
    # TODO: check for uniqueness of scenario IDs? Also make this a pre-commit lint tool?
    scenarios = []
    # old style glob is used to support symlinks
    for path in glob.glob(
        str((root or get_project_root()) / "algorithm_catalog") + "/**/*benchmark_scenarios*/*.json",
        recursive=True,
    ):
        scenarios.extend(read_scenarios_file(path))
    return scenarios


def lint_common_fields(scenario: BenchmarkScenario):
    """
    Various sanity checks for scenario data.
    To be used in unit tests and pre-commit hooks.
    """
    assert re.match(r"^[a-zA-Z0-9_-]+$", scenario.id)


def lint_benchmark_scenario(scenario: BenchmarkScenario):
    """
    Various sanity checks for scenario data.
    To be used in unit tests and pre-commit hooks.
    """
    lint_common_fields(scenario=scenario)

    if scenario.type == "openeo":
        lint_openeo_fields(scenario=scenario)
    elif scenario.type == "ogc_api_process":
        lint_ogc_fields(scenario=scenario)
    else:
        raise ValueError(f"Unsupported benchmark scenario type: {scenario.type!r}")


def lint_ogc_fields(scenario: OGCAPIBenchmarkScenario):
    assert scenario.endpoint.startswith(("http://", "https://")), (
        f"Unsupported OGC endpoint: {scenario.endpoint!r}"
    )
    assert scenario.application
    assert isinstance(scenario.parameters, dict)


def download_reference_data(scenario: BenchmarkScenario, reference_dir: Path) -> Path:
    with TimingLogger(
        title=f"Downloading reference data for {scenario.id=} to {reference_dir=}",
        logger=_log.info,
    ):
        for path, source in scenario.reference_data.items():
            path = reference_dir / path
            if not path.is_relative_to(reference_dir):
                raise ValueError(f"Resolved {path=} is not relative to {reference_dir=} ({scenario.id=})")
            path.parent.mkdir(parents=True, exist_ok=True)

            with TimingLogger(title=f"Downloading {source=} to {path=}", logger=_log.info):
                # Handle file:// URLs (local files)
                if source.startswith("file://"):
                    file_path = source[7:]  # Remove "file://" prefix
                    with open(file_path, "rb") as src_file:
                        with path.open("wb") as f:
                            f.write(src_file.read())
                else:
                    # Handle HTTP(S) URLs
                    resp = requests.get(source, stream=True)
                    with path.open("wb") as f:
                        for chunk in resp.iter_content(chunk_size=128):
                            f.write(chunk)

    return reference_dir
